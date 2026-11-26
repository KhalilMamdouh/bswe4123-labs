# Lab Assignment 2: Room Booking Service

This project is a small service for booking university rooms. It has rooms and bookings. The service keeps them in memory. The data is lost when the service stops.

## 1. API design

| Method | URI | Request body | Success status | Error status codes |
|---|---|---|---|---|
| `PUT` | `/rooms/{room_id}` | `{"building":"Science","capacity":20}` | `201` for a new room; `200` for an update | `422` if the room data is not valid |
| `GET` | `/rooms` | None | `200` | None |
| `GET` | `/rooms/{room_id}` | None | `200` | `404` if the room is not found |
| `DELETE` | `/rooms/{room_id}` | None | `204` | `404` if the room is not found; `409` if it still has bookings |
| `PUT` | `/bookings/{booking_id}` | `{"room_id":"B205","booking_date":"2026-12-01","start_hour":10,"end_hour":12,"purpose":"Study group"}` | `201` for a new booking; `200` for the same request again | `404` if the room is not found; `409` if the time overlaps or the id is used with different data; `422` if the booking data is not valid |
| `GET` | `/bookings` | None | `200` | None |
| `GET` | `/bookings/{booking_id}` | None | `200` | `404` if the booking is not found |
| `DELETE` | `/bookings/{booking_id}` | None | `204` | `404` if the booking is not found |

The start and end hours must be from 8 to 20. The end hour must be later than the start hour. Two bookings cannot use the same room at overlapping times on the same date. For example, 10 to 12 and 12 to 13 do not overlap.

## 2. How the service works

- A room has an id, a building, and a capacity.
- A booking has an id, a room, a date, start and end hours, and a purpose.
- Pydantic checks the data. If the end hour is before the start hour, the service returns `422`.
- The service returns `404` if a room or booking does not exist.
- The service returns `409` if a booking time overlaps another booking. It also returns `409` if a room still has bookings when someone tries to delete it.
- The service stores data in two Python dictionaries called `rooms` and `bookings`. The data is not saved after the service stops.

## 3. Sending the same booking again

The client chooses a booking id. In this example, the id is `BK-100`. The client sends the booking with `PUT /bookings/BK-100`.

The first request creates the booking and returns `201`. If the client sends the same request again with the same id and details, the service returns `200`. It does not make another booking. This helps if the client does not receive the first reply.

If the client uses `BK-100` again but sends different details, the service returns `409`.

## 4. How to run the project

Use Python 3.10 or newer. If the packages are not installed, run:

```powershell
pip install fastapi "uvicorn[standard]" httpx
```

Open two PowerShell windows in this folder.

In the first window, start the service:

```powershell
uvicorn service:app --reload --port 8000
```

Leave that window open. In the second window, run the test client:

```powershell
python test_bookings.py http://localhost:8000
```

You can also open `http://localhost:8000/docs` in a browser to try the API.

## 5. Test output

This is the output from `python test_bookings.py http://localhost:8000`:

```text
PUT new room B205                                    -> 201
PUT existing room B205                               -> 200
GET all rooms                                        -> 200
GET existing room B205                               -> 200
GET unknown room                                     -> 404
PUT invalid room (capacity zero)                     -> 422
PUT booking BK-100 (first request)                   -> 201
PUT booking BK-100 (identical retry)                 -> 200
PUT adjacent booking (12 to 13)                      -> 201
GET all bookings                                     -> 200
GET existing booking BK-100                          -> 200
GET unknown booking                                  -> 404
PUT overlapping booking (11 to 13)                   -> 409
PUT invalid booking (end before start)              -> 422
PUT booking for unknown room                         -> 404
Reuse BK-100 id with different data                  -> 409
DELETE room B205 while booked                        -> 409
DELETE booking BK-100                                -> 204
DELETE booking BK-ADJ                                -> 204
DELETE unknown booking                               -> 404
DELETE room B205                                     -> 204
DELETE unknown room                                  -> 404

All checks passed.
```

## 6. Project files

- `service.py` contains the FastAPI service.
- `test_bookings.py` sends requests with `httpx` and prints the status codes.
- `README.md` explains the API and how to run the project.

Before submitting, read the code and make sure you can explain the main parts in your own words. The assignment asks students to write their own work, so change or explain the answers in a way you understand.
