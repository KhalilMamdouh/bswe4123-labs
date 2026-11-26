# Lab Assignment 3: Exam Scheduler Service

This project has two services. The Room Booking Service stores rooms and bookings. The Exam Scheduler asks it for information, finds a free room, and books that room for an exam.

The data is kept in memory. If the Room Booking Service stops, its rooms and bookings are cleared. Add the rooms again after restarting it.

## 1. How to run the services

Use Python 3.10 or newer. Install the packages if they are not already installed:

```powershell
pip install fastapi "uvicorn[standard]" httpx
```

Open two PowerShell windows in the `lab3-assignment` folder.

### Terminal 1: Room Booking Service

Set the delay to zero for normal use, then start the service on port 8001:

```powershell
$env:ROOM_SERVICE_DELAY = "0"
uvicorn room_service:app --host 127.0.0.1 --port 8001 --reload
```

Open `http://127.0.0.1:8001/docs`. Create these two rooms using `PUT /rooms/{room_id}`:

- Room id: `B205`; body: `{"building":"Science","capacity":40}`
- Room id: `B206`; body: `{"building":"Engineering","capacity":90}`

### Terminal 2: Exam Scheduler Service

Set its environment variables, then start it on port 8002:

```powershell
$env:ROOM_SERVICE_URL = "http://127.0.0.1:8001"
$env:ROOM_SERVICE_TIMEOUT = "2"
$env:MAX_RETRIES = "3"
uvicorn scheduler_service:app --host 127.0.0.1 --port 8002 --reload
```

Open `http://127.0.0.1:8002/docs` and send this example to `POST /exams`:

```json
{
  "exam_id": "EX-101",
  "course_code": "BSWE4123",
  "day": "2026-12-01",
  "start_hour": 10,
  "end_hour": 12,
  "students": 25
}
```

The service should choose room `B205`, because it is the smallest room that fits 25 students and is free at that time. Try the same request again. It returns the same room and does not make another booking. If you change `students` to `1000`, the service returns `409` because no room is large enough.

The scheduler's `GET /config` shows its Room Booking Service address, timeout, and maximum retries. The Room Booking Service's `GET /config` shows its delay.

## 2. Retry settings

The scheduler reads these environment variables when it starts:

- `ROOM_SERVICE_URL`: address of the Room Booking Service.
- `ROOM_SERVICE_TIMEOUT`: how long to wait for one answer, in seconds.
- `MAX_RETRIES`: how many extra tries to make after the first try.

When there is a timeout, a connection problem, or a `5xx` response, the scheduler waits and tries again. The default waits are 0.5 seconds, then 1 second, then 2 seconds. It does not retry a `404` or `409` response.

## 3. Why retrying a booking is safe

The office gives each exam an id, such as `EX-101`. The scheduler uses a matching booking id, `EXAM-EX-101`, every time it tries to book that exam. It sends the same room and booking information on each retry.

The Room Booking Service uses `PUT` for this booking. If it already has that id with the same information, it returns `200` and keeps only one booking. If a reply is lost, the scheduler can safely try again. The scheduler also checks for that booking id before choosing a room. If the same exam id is sent with different information, it returns `409`.

## 4. Retry test: stop and restart the Room Booking Service

Test steps: create the rooms, stop the Room Booking Service, and send a `POST /exams` request while it is stopped. While the scheduler is waiting between retries, start the Room Booking Service again and create the rooms again. In a test run of this solution, the request then finished successfully.

Example lines from the scheduler terminal during that test:

```text
Room service ConnectError on GET /bookings/EXAM-EX-RETRY-1; retry 1/3 in 0.5s
Room service ConnectError on GET /bookings/EXAM-EX-RETRY-1; retry 2/3 in 1.0s
Room service answered on attempt 3: GET /bookings/EXAM-EX-RETRY-1 -> 404
POST /exams -> 201 Created
```

The `404` means this exam did not have a booking yet. The scheduler did not retry the `404`; it continued and made the booking. The final response was `201`, with room `B205`. A follow-up `GET /bookings/EXAM-EX-RETRY-1` returned the saved booking.

To try this yourself, keep the Exam Scheduler running. Stop the Room Booking Service, send a new exam request from another terminal, then start the Room Booking Service again and create the rooms before the scheduler runs out of retries. The Room Booking Service stores data in memory, so restarting it clears the rooms and bookings.

## 5. Delay and timeout test

These values were measured in a test run of this solution. The response time is for `POST /exams`. The test used `MAX_RETRIES = 1` and created the rooms before each measured request. Your times may be different on your computer, so run the tests and record your own results.

| Room Service delay | Scheduler timeout | Status | Response time |
|---:|---:|---:|---:|
| 0.05 seconds | 0.50 seconds | `201` | 0.38 seconds |
| 0.30 seconds | 0.10 seconds | `503` | 0.81 seconds |
| 0.30 seconds | 0.80 seconds | `201` | 1.39 seconds |

When the timeout was shorter than the Room Service delay, the scheduler did not get an answer in time. It made its one retry and then returned `503`. With a longer timeout, it waited long enough and returned `201`, but the whole request took longer. A short timeout gives a faster failure; a longer timeout gives a slow service more time to answer.

To change the Room Service delay in PowerShell, set the variable before starting it. For example:

```powershell
$env:ROOM_SERVICE_DELAY = "0.30"
```

Settings are read when each service starts. Stop and start the service after changing a setting. Use three terminals when testing: one for the Room Booking Service, one for the Exam Scheduler, and one for requests if you need to stop and restart a service while a request is waiting.

## 6. Project files

- `room_service.py` is the Room Booking Service. It has the delay setting.
- `scheduler_service.py` is the Exam Scheduler. It selects a room and retries temporary failures.
- `README.md` has the API example, run commands, retry test, and delay/timeout results.

Read the code and make sure you can explain it in your own words before submitting. The assignment asks students to write their own work, so update the explanations to match what you understand and what you observe when you run it.
