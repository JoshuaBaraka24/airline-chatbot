"""All SQL used by the dialogue actions, kept in one place.

Every query is parameterised (NFR-06). Functions return plain dicts
(RealDictCursor rows) or simple values so callers stay free of SQL.
"""
from datetime import date
from typing import List, Optional

from actions.db import get_cursor

_BOOKING_SELECT = """
    SELECT b.booking_ref, b.status, b.flight_id,
           u.name AS passenger_name,
           f.flight_number, f.origin, f.destination,
           f.departure_time, f.arrival_time, f.status AS flight_status
    FROM bookings b
    JOIN users u USING (user_id)
    JOIN flights f USING (flight_id)
"""


def get_next_flight(flight_number: str) -> Optional[dict]:
    """The next upcoming departure of a flight number, or the latest past one."""
    with get_cursor() as cur:
        cur.execute(
            """SELECT * FROM flights WHERE flight_number = %s
               ORDER BY departure_time < NOW(), ABS(EXTRACT(EPOCH FROM departure_time - NOW()))
               LIMIT 1""",
            (flight_number,),
        )
        return cur.fetchone()


def get_booking(booking_ref: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute(_BOOKING_SELECT + " WHERE b.booking_ref = %s", (booking_ref,))
        return cur.fetchone()


def find_available_flight(flight_number: str, on_date: date) -> Optional[dict]:
    """An operating flight with seats left for this flight number on the given date."""
    with get_cursor() as cur:
        cur.execute(
            """SELECT * FROM flights
               WHERE flight_number = %s AND departure_time::date = %s
                 AND status <> 'cancelled' AND seats_available > 0
                 AND departure_time > NOW()
               ORDER BY departure_time LIMIT 1""",
            (flight_number, on_date),
        )
        return cur.fetchone()


def upcoming_departures(flight_number: str, limit: int = 3) -> List[dict]:
    with get_cursor() as cur:
        cur.execute(
            """SELECT * FROM flights
               WHERE flight_number = %s AND status <> 'cancelled'
                 AND seats_available > 0 AND departure_time > NOW()
               ORDER BY departure_time LIMIT %s""",
            (flight_number, limit),
        )
        return cur.fetchall()


def served_cities(column: str) -> List[str]:
    """Distinct origins or destinations in the schedule."""
    if column not in ("origin", "destination"):
        raise ValueError(f"unexpected column {column!r}")
    with get_cursor() as cur:
        cur.execute(f"SELECT DISTINCT {column} AS city FROM flights ORDER BY 1")
        return [row["city"] for row in cur.fetchall()]


def route_exists(origin: str, destination: str) -> bool:
    with get_cursor() as cur:
        cur.execute(
            "SELECT 1 FROM flights WHERE LOWER(origin) = LOWER(%s) AND LOWER(destination) = LOWER(%s) LIMIT 1",
            (origin, destination),
        )
        return cur.fetchone() is not None


def search_flights(origin: str, destination: str, from_date: date, days: int = 3, limit: int = 3) -> List[dict]:
    """Operating flights with seats on a route within `days` of from_date."""
    with get_cursor() as cur:
        cur.execute(
            """SELECT * FROM flights
               WHERE LOWER(origin) = LOWER(%s) AND LOWER(destination) = LOWER(%s)
                 AND status <> 'cancelled' AND seats_available > 0
                 AND departure_time > NOW()
                 AND departure_time::date BETWEEN %s AND %s::date + %s
               ORDER BY departure_time LIMIT %s""",
            (origin, destination, from_date, from_date, days, limit),
        )
        return cur.fetchall()


def next_flights_on_route(origin: str, destination: str, limit: int = 3) -> List[dict]:
    with get_cursor() as cur:
        cur.execute(
            """SELECT * FROM flights
               WHERE LOWER(origin) = LOWER(%s) AND LOWER(destination) = LOWER(%s)
                 AND status <> 'cancelled' AND seats_available > 0
                 AND departure_time > NOW()
               ORDER BY departure_time LIMIT %s""",
            (origin, destination, limit),
        )
        return cur.fetchall()


def cancel_booking(booking_ref: str) -> bool:
    """Cancel a confirmed booking and release its seat. Returns False if nothing changed."""
    with get_cursor() as cur:
        cur.execute(
            """UPDATE bookings SET status = 'cancelled', updated_at = NOW()
               WHERE booking_ref = %s AND status = 'confirmed'
               RETURNING flight_id""",
            (booking_ref,),
        )
        row = cur.fetchone()
        if not row:
            return False
        cur.execute(
            "UPDATE flights SET seats_available = seats_available + 1 WHERE flight_id = %s",
            (row["flight_id"],),
        )
        return True


def change_booking_flight(booking_ref: str, new_flight_id: int) -> bool:
    """Move a confirmed booking to another flight, transferring the seat atomically."""
    with get_cursor() as cur:
        cur.execute(
            "UPDATE flights SET seats_available = seats_available - 1 "
            "WHERE flight_id = %s AND seats_available > 0 AND status <> 'cancelled' RETURNING flight_id",
            (new_flight_id,),
        )
        if not cur.fetchone():
            return False
        cur.execute(
            """UPDATE bookings b SET flight_id = %s, updated_at = NOW()
               FROM bookings old
               WHERE b.booking_ref = old.booking_ref AND b.booking_ref = %s AND b.status = 'confirmed'
               RETURNING old.flight_id AS old_flight_id""",
            (new_flight_id, booking_ref),
        )
        row = cur.fetchone()
        if not row:
            # Booking no longer changeable: raising rolls back the seat decrement above
            raise LookupError(f"booking {booking_ref} is not confirmed")
        cur.execute(
            "UPDATE flights SET seats_available = seats_available + 1 WHERE flight_id = %s",
            (row["old_flight_id"],),
        )
        return True


def mark_conversation_escalated(sender_id: str) -> None:
    """Flag the logged conversation for human follow-up (FR-04, FR-07)."""
    with get_cursor() as cur:
        cur.execute(
            "UPDATE conversations SET status = 'escalated' WHERE sender_id = %s",
            (sender_id,),
        )


def bookings_for_user(user_id: int, statuses: tuple = ("confirmed", "checked_in")) -> List[dict]:
    """A logged-in passenger's bookings, soonest first, for quick-reply buttons."""
    with get_cursor() as cur:
        cur.execute(
            _BOOKING_SELECT + """ WHERE b.user_id = %s AND b.status = ANY(%s)
                                  ORDER BY f.departure_time LIMIT 5""",
            (user_id, list(statuses)),
        )
        return cur.fetchall()
