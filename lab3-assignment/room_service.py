"""Room Booking Service used by the Exam Scheduler."""
import asyncio
import os
from datetime import date

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field, root_validator

app = FastAPI(title="Campus Room Booking Service")

# The delay is set when the service starts. Zero means no added delay.
ROOM_SERVICE_DELAY = float(os.getenv("ROOM_SERVICE_DELAY", "0"))


@app.middleware("http")
async def add_delay(request: Request, call_next):
    """Wait before answering, to test a slow service."""
    if ROOM_SERVICE_DELAY > 0:
        await asyncio.sleep(ROOM_SERVICE_DELAY)
    return await call_next(request)


class RoomInput(BaseModel):
    building: str = Field(min_length=1, examples=["Science"])
    capacity: int = Field(ge=1, examples=[20])


class BookingInput(BaseModel):
    room_id: str = Field(min_length=1, examples=["B205"])
    booking_date: date = Field(examples=["2026-12-01"])
    start_hour: int = Field(ge=8, le=20, examples=[10])
    end_hour: int = Field(ge=8, le=20, examples=[12])
    purpose: str = Field(min_length=1, examples=["Study group"])

    @root_validator(skip_on_failure=True)
    def end_must_be_after_start(cls, values):
        if values.get("end_hour", 0) <= values.get("start_hour", 0):
            raise ValueError("end_hour must be later than start_hour")
        return values


# Simple memory storage. It is cleared when this service is restarted.
rooms: dict[str, RoomInput] = {}
bookings: dict[str, BookingInput] = {}


def room_as_dict(room_id: str) -> dict:
    return {"id": room_id, **rooms[room_id].dict()}


def booking_as_dict(booking_id: str, booking: BookingInput) -> dict:
    return {"id": booking_id, **booking.dict()}


@app.get("/config")
def config():
    return {"room_service_delay_seconds": ROOM_SERVICE_DELAY}


@app.put("/rooms/{room_id}", status_code=200)
def save_room(room_id: str, room: RoomInput, response: Response):
    if room_id not in rooms:
        response.status_code = 201
    rooms[room_id] = room
    return room_as_dict(room_id)


@app.get("/rooms")
def list_rooms():
    return [room_as_dict(room_id) for room_id in sorted(rooms)]


@app.get("/rooms/{room_id}")
def get_room(room_id: str):
    if room_id not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    return room_as_dict(room_id)


@app.delete("/rooms/{room_id}", status_code=204)
def delete_room(room_id: str):
    if room_id not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    if any(booking.room_id == room_id for booking in bookings.values()):
        raise HTTPException(status_code=409, detail="Room still has bookings")
    del rooms[room_id]
    return Response(status_code=204)


@app.put("/bookings/{booking_id}", status_code=201)
def save_booking(booking_id: str, booking: BookingInput, response: Response):
    # The same id and same data mean this is a safe retry.
    if booking_id in bookings:
        if bookings[booking_id] == booking:
            response.status_code = 200
            return booking_as_dict(booking_id, bookings[booking_id])
        raise HTTPException(
            status_code=409,
            detail="This booking id was already used with different data",
        )

    if booking.room_id not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    for existing in bookings.values():
        same_room_and_day = (
            existing.room_id == booking.room_id
            and existing.booking_date == booking.booking_date
        )
        overlaps = (
            booking.start_hour < existing.end_hour
            and existing.start_hour < booking.end_hour
        )
        if same_room_and_day and overlaps:
            raise HTTPException(status_code=409, detail="Booking time overlaps")

    bookings[booking_id] = booking
    return booking_as_dict(booking_id, booking)


@app.get("/bookings")
def list_bookings():
    return [booking_as_dict(booking_id, bookings[booking_id])
            for booking_id in sorted(bookings)]


@app.get("/bookings/{booking_id}")
def get_booking(booking_id: str):
    if booking_id not in bookings:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking_as_dict(booking_id, bookings[booking_id])


@app.delete("/bookings/{booking_id}", status_code=204)
def delete_booking(booking_id: str):
    if booking_id not in bookings:
        raise HTTPException(status_code=404, detail="Booking not found")
    del bookings[booking_id]
    return Response(status_code=204)
