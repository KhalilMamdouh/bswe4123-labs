"""Exam Scheduler Service for BSWE4123 Lab Assignment 3."""
import os
import time
from datetime import date
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field, root_validator

ROOM_SERVICE_URL = os.getenv(
    "ROOM_SERVICE_URL", "http://127.0.0.1:8001"
).rstrip("/")
ROOM_SERVICE_TIMEOUT = float(os.getenv("ROOM_SERVICE_TIMEOUT", "2.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
BACKOFF_START_SECONDS = 0.5

app = FastAPI(title="Exam Scheduler Service")


class ExamRequest(BaseModel):
    """Information sent by the exams office."""
    exam_id: str = Field(min_length=1, max_length=60, examples=["EX-101"])
    course_code: str = Field(min_length=1, examples=["BSWE4123"])
    day: date = Field(examples=["2026-12-01"])
    start_hour: int = Field(ge=8, le=20, examples=[10])
    end_hour: int = Field(ge=8, le=20, examples=[12])
    students: int = Field(ge=1, examples=[25])

    @root_validator(skip_on_failure=True)
    def end_must_be_after_start(cls, values):
        if values.get("end_hour", 0) <= values.get("start_hour", 0):
            raise ValueError("end_hour must be later than start_hour")
        return values


def call_room_service(method: str, path: str, body: dict | None = None) -> httpx.Response:
    """Call the room service and retry only network errors and 5xx responses."""
    url = f"{ROOM_SERVICE_URL}{path}"
    last_problem = "unknown error"

    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=ROOM_SERVICE_TIMEOUT) as client:
                if body is None:
                    reply = client.request(method, url)
                else:
                    reply = client.request(method, url, json=body)
        except httpx.RequestError as error:
            last_problem = type(error).__name__
        else:
            if reply.status_code < 500:
                # This includes 404 and 409: neither status is retried.
                if attempt > 0:
                    print(
                        f"Room service answered on attempt {attempt + 1}: "
                        f"{method} {path} -> {reply.status_code}",
                        flush=True,
                    )
                return reply
            last_problem = f"HTTP {reply.status_code}"

        if attempt == MAX_RETRIES:
            print(
                f"Room service request failed after {attempt + 1} attempts: "
                f"{method} {path} ({last_problem})",
                flush=True,
            )
            raise HTTPException(
                status_code=503,
                detail="Room Booking Service is unavailable",
            )

        wait_seconds = BACKOFF_START_SECONDS * (2 ** attempt)
        print(
            f"Room service {last_problem} on {method} {path}; "
            f"retry {attempt + 1}/{MAX_RETRIES} in {wait_seconds:.1f}s",
            flush=True,
        )
        time.sleep(wait_seconds)

    # This line is only here to make the return type clear to Python tools.
    raise HTTPException(status_code=503, detail="Room Booking Service is unavailable")


def read_list(path: str) -> list[dict]:
    """Get a list from the room service and turn bad answers into 503."""
    reply = call_room_service("GET", path)
    if reply.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail=f"Room Booking Service returned {reply.status_code}",
        )
    return reply.json()


def exam_result(exam: ExamRequest, booking: dict, room: dict) -> dict:
    """Make the response for a scheduled exam."""
    return {
        "exam_id": exam.exam_id,
        "course_code": exam.course_code,
        "day": exam.day.isoformat(),
        "start_hour": exam.start_hour,
        "end_hour": exam.end_hour,
        "students": exam.students,
        "booking_id": booking["id"],
        "room": {
            "id": room["id"],
            "building": room["building"],
            "capacity": room["capacity"],
        },
    }


def make_booking_data(exam: ExamRequest, room_id: str) -> dict:
    """Use a fixed booking id and fixed details for safe retries."""
    return {
        "room_id": room_id,
        "booking_date": exam.day.isoformat(),
        "start_hour": exam.start_hour,
        "end_hour": exam.end_hour,
        "purpose": (
            f"Exam {exam.exam_id}: {exam.course_code}; "
            f"{exam.students} students"
        ),
    }


def booking_matches_exam(booking: dict, exam: ExamRequest) -> bool:
    """Check whether a saved booking is for these exact exam details."""
    return (
        booking.get("booking_date") == exam.day.isoformat()
        and booking.get("start_hour") == exam.start_hour
        and booking.get("end_hour") == exam.end_hour
        and booking.get("purpose")
        == f"Exam {exam.exam_id}: {exam.course_code}; {exam.students} students"
    )


def is_busy(room_id: str, exam: ExamRequest, bookings: list[dict]) -> bool:
    """Return True if this room has a booking at an overlapping time."""
    for booking in bookings:
        if booking.get("room_id") != room_id:
            continue
        if booking.get("booking_date") != exam.day.isoformat():
            continue
        overlaps = (
            exam.start_hour < booking.get("end_hour", 0)
            and booking.get("start_hour", 0) < exam.end_hour
        )
        if overlaps:
            return True
    return False


@app.get("/config")
def config():
    """Show the settings read when this service started."""
    return {
        "room_service_url": ROOM_SERVICE_URL,
        "timeout_seconds": ROOM_SERVICE_TIMEOUT,
        "max_retries": MAX_RETRIES,
        "first_backoff_seconds": BACKOFF_START_SECONDS,
    }


@app.post("/exams", status_code=201)
def schedule_exam(exam: ExamRequest, response: Response):
    """Find the smallest free room and book it through the room service."""
    # This id is the same on every retry, including after a lost reply.
    booking_id = f"EXAM-{exam.exam_id}"
    encoded_booking_id = quote(booking_id, safe="")

    # Check first in case an earlier request succeeded but its reply was lost.
    old_reply = call_room_service("GET", f"/bookings/{encoded_booking_id}")
    if old_reply.status_code == 200:
        old_booking = old_reply.json()
        if not booking_matches_exam(old_booking, exam):
            raise HTTPException(
                status_code=409,
                detail="This exam id was already used with different details",
            )
        room_reply = call_room_service(
            "GET", f"/rooms/{quote(old_booking['room_id'], safe='')}"
        )
        if room_reply.status_code != 200:
            raise HTTPException(status_code=503, detail="The booked room is unavailable")
        response.status_code = 200
        return exam_result(exam, old_booking, room_reply.json())
    if old_reply.status_code != 404:
        raise HTTPException(
            status_code=503,
            detail=f"Room Booking Service returned {old_reply.status_code}",
        )

    rooms = read_list("/rooms")
    bookings = read_list("/bookings")

    # Keep rooms that are large enough and do not have an overlapping booking.
    available = [
        room for room in rooms
        if room["capacity"] >= exam.students
        and not is_busy(room["id"], exam, bookings)
    ]
    available.sort(key=lambda room: (room["capacity"], room["id"]))

    if not available:
        raise HTTPException(
            status_code=409,
            detail="There is no free room large enough for this exam",
        )

    chosen_room = available[0]
    booking_data = make_booking_data(exam, chosen_room["id"])
    booking_reply = call_room_service(
        "PUT",
        f"/bookings/{encoded_booking_id}",
        body=booking_data,
    )

    if booking_reply.status_code == 409:
        raise HTTPException(
            status_code=409,
            detail="The room became unavailable while scheduling the exam",
        )
    if booking_reply.status_code == 404:
        raise HTTPException(
            status_code=409,
            detail="The selected room no longer exists",
        )
    if booking_reply.status_code not in (200, 201):
        raise HTTPException(
            status_code=503,
            detail=f"Room Booking Service returned {booking_reply.status_code}",
        )

    saved_booking = booking_reply.json()
    return exam_result(exam, saved_booking, chosen_room)
