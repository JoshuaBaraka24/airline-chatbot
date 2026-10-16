"""Passenger-facing portal endpoints: my bookings and public flight status."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend import auth
from backend.db import get_cursor

router = APIRouter(prefix="/api", tags=["portal"])


class Flight(BaseModel):
    flight_number: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    status: str


class Booking(BaseModel):
    booking_ref: str
    status: str
    flight: Flight


@router.get("/me/bookings", response_model=List[Booking])
def my_bookings(user: dict = Depends(auth.require_user)) -> List[dict]:
    with get_cursor() as cur:
        cur.execute(
            """SELECT b.booking_ref, b.status, f.flight_number, f.origin, f.destination,
                      f.departure_time, f.arrival_time, f.status AS flight_status
               FROM bookings b JOIN flights f USING (flight_id)
               WHERE b.user_id = %s
               ORDER BY (b.status = 'cancelled'), f.departure_time""",
            (user["user_id"],),
        )
        rows = cur.fetchall()
    return [
        {
            "booking_ref": r["booking_ref"],
            "status": r["status"],
            "flight": {
                "flight_number": r["flight_number"], "origin": r["origin"], "destination": r["destination"],
                "departure_time": r["departure_time"], "arrival_time": r["arrival_time"],
                "status": r["flight_status"],
            },
        }
        for r in rows
    ]


@router.get("/flights/status", response_model=List[Flight])
def flight_status(
    flight_number: str = Query(..., min_length=3, max_length=10, regex=r"^[A-Za-z]{2}\s?\d{2,4}$"),
    limit: Optional[int] = Query(3, ge=1, le=10),
) -> List[dict]:
    """Upcoming departures of a flight number, for the home page search box."""
    normalised = flight_number.replace(" ", "").upper()
    with get_cursor() as cur:
        cur.execute(
            """SELECT flight_number, origin, destination, departure_time, arrival_time, status
               FROM flights
               WHERE flight_number = %s AND departure_time > NOW() - INTERVAL '1 day'
               ORDER BY departure_time LIMIT %s""",
            (normalised, limit),
        )
        flights = cur.fetchall()
    if not flights:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No upcoming flights found for {normalised}.")
    return flights
