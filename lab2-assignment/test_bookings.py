"""Call the booking API and print the status code for every test.

Run the service in another terminal first, then run:
    python test_bookings.py http://localhost:8000
"""
import sys

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
DATE = "2026-12-01"


def show(client, label, response, expected):
    """Print one result and fail early if the actual status is unexpected."""
    print(f"{label:<52} -> {response.status_code}")
    if response.status_code != expected:
        raise AssertionError(
            f"{label}: expected {expected}, got {response.status_code}: {response.text}"
        )


room = {"building": "Science", "capacity": 20}
booking = {
    "room_id": "B205",
    "booking_date": DATE,
    "start_hour": 10,
    "end_hour": 12,
    "purpose": "Study group",
}

with httpx.Client(base_url=BASE_URL, timeout=5.0) as client:
    # Clean up these test ids first so this script can be run more than once.
    for booking_id in ("BK-100", "BK-ADJ", "BK-OVERLAP", "BK-NO-ROOM"):
        client.delete(f"/bookings/{booking_id}")
    for room_id in ("B205", "B999"):
        client.delete(f"/rooms/{room_id}")

    # Room successes and not-found error.
    show(client, "PUT new room B205", client.put("/rooms/B205", json=room), 201)
    updated_room = {"building": "Science", "capacity": 25}
    show(client, "PUT existing room B205", client.put("/rooms/B205", json=updated_room), 200)
    room = updated_room
    show(client, "GET all rooms", client.get("/rooms"), 200)
    show(client, "GET existing room B205", client.get("/rooms/B205"), 200)
    show(client, "GET unknown room", client.get("/rooms/NO-ROOM"), 404)
    invalid_room = {"building": "Science", "capacity": 0}
    show(client, "PUT invalid room (capacity zero)",
         client.put("/rooms/BAD", json=invalid_room), 422)

    # First request creates; the identical retry returns 200 and does not add a row.
    created = client.put("/bookings/BK-100", json=booking)
    show(client, "PUT booking BK-100 (first request)", created, 201)
    replay = client.put("/bookings/BK-100", json=booking)
    show(client, "PUT booking BK-100 (identical retry)", replay, 200)

    # Adjacent time ranges do not overlap: 10-12 and 12-13 are both allowed.
    adjacent = {**booking, "start_hour": 12, "end_hour": 13, "purpose": "Lab work"}
    show(client, "PUT adjacent booking (12 to 13)",
         client.put("/bookings/BK-ADJ", json=adjacent), 201)

    show(client, "GET all bookings", client.get("/bookings"), 200)
    show(client, "GET existing booking BK-100", client.get("/bookings/BK-100"), 200)
    show(client, "GET unknown booking", client.get("/bookings/NO-BOOKING"), 404)

    overlap = {**booking, "start_hour": 11, "end_hour": 13, "purpose": "Another group"}
    show(client, "PUT overlapping booking (11 to 13)",
         client.put("/bookings/BK-OVERLAP", json=overlap), 409)

    invalid = {**booking, "start_hour": 10, "end_hour": 9}
    show(client, "PUT invalid booking (end before start)",
         client.put("/bookings/BK-INVALID", json=invalid), 422)

    no_room = {**booking, "room_id": "B999"}
    show(client, "PUT booking for unknown room", 
         client.put("/bookings/BK-NO-ROOM", json=no_room), 404)

    changed_retry = {**booking, "purpose": "Different purpose"}
    show(client, "Reuse BK-100 id with different data",
         client.put("/bookings/BK-100", json=changed_retry), 409)

    show(client, "DELETE room B205 while booked", client.delete("/rooms/B205"), 409)
    show(client, "DELETE booking BK-100", client.delete("/bookings/BK-100"), 204)
    show(client, "DELETE booking BK-ADJ", client.delete("/bookings/BK-ADJ"), 204)
    show(client, "DELETE unknown booking", client.delete("/bookings/NO-BOOKING"), 404)
    show(client, "DELETE room B205", client.delete("/rooms/B205"), 204)
    show(client, "DELETE unknown room", client.delete("/rooms/NO-ROOM"), 404)

print("\nAll checks passed.")
