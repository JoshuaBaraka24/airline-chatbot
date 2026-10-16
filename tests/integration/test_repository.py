"""Database transactions used by the dialogue actions (actions/repository.py)."""
from actions import repository as repo


def seats(flight_id):
    from actions.db import get_cursor
    with get_cursor() as cur:
        cur.execute("SELECT seats_available FROM flights WHERE flight_id = %s", (flight_id,))
        return cur.fetchone()["seats_available"]


def test_get_booking_joins_passenger_and_flight(db):
    booking = repo.get_booking("BK001")

    assert booking["passenger_name"] == "John Mwangi"
    assert (booking["flight_number"], booking["origin"], booking["destination"]) == ("KQ101", "Nairobi", "Mombasa")


def test_cancel_booking_releases_the_seat_once(db):
    flight_id = repo.get_booking("BK001")["flight_id"]
    before = seats(flight_id)

    assert repo.cancel_booking("BK001") is True
    assert repo.get_booking("BK001")["status"] == "cancelled"
    assert seats(flight_id) == before + 1
    assert repo.cancel_booking("BK001") is False       # already cancelled
    assert seats(flight_id) == before + 1


def test_checked_in_booking_cannot_be_cancelled(db):
    assert repo.cancel_booking("BK004") is False
    assert repo.get_booking("BK004")["status"] == "checked_in"


def test_change_booking_moves_the_seat_between_flights(db):
    booking = repo.get_booking("BK002")
    new_flight = [f for f in repo.upcoming_departures("KQ202") if f["flight_id"] != booking["flight_id"]][0]
    old_before, new_before = seats(booking["flight_id"]), seats(new_flight["flight_id"])

    assert repo.change_booking_flight("BK002", new_flight["flight_id"]) is True
    assert repo.get_booking("BK002")["flight_id"] == new_flight["flight_id"]
    assert seats(booking["flight_id"]) == old_before + 1
    assert seats(new_flight["flight_id"]) == new_before - 1


def test_failed_change_rolls_back_the_seat(db):
    new_flight = repo.upcoming_departures("KQ101")[1]
    before = seats(new_flight["flight_id"])

    try:
        repo.change_booking_flight("BK006", new_flight["flight_id"])  # BK006 is cancelled
    except LookupError:
        pass
    assert seats(new_flight["flight_id"]) == before


def test_route_search_and_city_lists(db):
    assert "Nairobi" in repo.served_cities("origin")
    assert repo.route_exists("nairobi", "DUBAI") is True
    assert repo.route_exists("Kisumu", "London") is False
    assert repo.next_flights_on_route("Nairobi", "Johannesburg")[0]["status"] == "on_time"  # cancelled one skipped
