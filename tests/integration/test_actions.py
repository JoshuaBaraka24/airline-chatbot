"""Custom actions: booking questions for logged-in passengers, and the new booking flow."""
import asyncio
from datetime import date, timedelta

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions import repository as repo
from actions.actions import ActionNewBooking
from actions.db import get_cursor
from actions.forms import (
    ActionAskBookingReference,
    ActionAskSelectedFlightId,
    ValidateCancelBookingForm,
    ValidateNewBookingForm,
)


def ask(metadata, form="cancel_booking_form"):
    tracker = Tracker(
        sender_id="test", slots={}, latest_message={"text": "cancel my booking", "metadata": metadata},
        events=[], paused=False, followup_action=None, active_loop={"name": form}, latest_action_name=None,
    )
    dispatcher = CollectingDispatcher()
    ActionAskBookingReference().run(dispatcher, tracker, {})
    return dispatcher.messages[0]


def test_logged_in_passenger_gets_their_bookings_as_buttons(db):
    message = ask({"user_id": 1, "name": "John Mwangi"})

    assert message["text"].startswith("John, which booking")
    assert [b["payload"] for b in message["buttons"]] == ['/inform{"booking_reference":"BK001"}']
    assert message["buttons"][0]["title"].startswith("BK001 · KQ101 Nairobi → Mombasa")


def test_anonymous_passenger_gets_the_standard_question(db):
    assert ask(None)["response"] == "utter_ask_booking_reference"


def test_bookings_that_the_form_cannot_act_on_are_not_offered(db):
    # Grace's only booking (BK004) is checked in: it can't be cancelled, but its status can be checked
    assert ask({"user_id": 4, "name": "Grace Wanjiku"})["response"] == "utter_ask_booking_reference"
    status = ask({"user_id": 4, "name": "Grace Wanjiku"}, form="check_in_status_form")
    assert [b["title"][:5] for b in status["buttons"]] == ["BK004"]


# --- new booking (FR-03) ---

BOOKING_SLOTS = ["origin", "destination", "travel_date", "selected_flight_id",
                 "passenger_name", "passenger_email", "confirm_booking"]


def booking_tracker(slots, text="", entities=(), metadata=None, intent="inform"):
    return Tracker(
        sender_id="test", slots=slots,
        latest_message={"text": text, "entities": list(entities), "metadata": metadata,
                        "intent": {"name": intent, "confidence": 0.9}},
        events=[], paused=False, followup_action=None,
        active_loop={"name": "new_booking_form"}, latest_action_name=None,
    )


def dubai_flights():
    flights = repo.next_flights_on_route("Nairobi", "Dubai")
    route = {"origin": "Nairobi", "destination": "Dubai",
             "travel_date": flights[0]["departure_time"].date().isoformat()}
    return flights, route


def test_logged_in_passengers_are_not_asked_for_name_and_email(db):
    form = ValidateNewBookingForm()
    required = lambda metadata: asyncio.run(form.required_slots(
        BOOKING_SLOTS, CollectingDispatcher(), booking_tracker({}, metadata=metadata), {}))

    assert required({"user_id": 1, "name": "John Mwangi"}) == [
        "origin", "destination", "travel_date", "selected_flight_id", "confirm_booking"]
    assert required(None) == BOOKING_SLOTS


def test_flights_are_offered_as_numbered_buttons(db):
    flights, route = dubai_flights()
    dispatcher = CollectingDispatcher()

    ActionAskSelectedFlightId().run(dispatcher, booking_tracker(route), {})

    message = dispatcher.messages[0]
    assert "1. KQ202" in message["text"]
    assert [b["payload"] for b in message["buttons"]] == [
        f'/inform{{"flight_option":"{f["flight_id"]}"}}' for f in flights]


def test_flight_is_chosen_by_button_or_number(db):
    flights, route = dubai_flights()
    form = ValidateNewBookingForm()

    button = booking_tracker(route, entities=[{"entity": "flight_option", "value": str(flights[1]["flight_id"])}])
    assert form.validate_selected_flight_id("x", CollectingDispatcher(), button, {}) == {
        "selected_flight_id": str(flights[1]["flight_id"])}

    typed = booking_tracker(route, text="the first one")
    assert form.validate_selected_flight_id("the first one", CollectingDispatcher(), typed, {}) == {
        "selected_flight_id": str(flights[0]["flight_id"])}

    dispatcher = CollectingDispatcher()
    assert form.validate_selected_flight_id("9", dispatcher, booking_tracker(route, text="9"), {}) == {
        "selected_flight_id": None}
    assert "choose one of the flights" in dispatcher.messages[0]["text"]


def test_a_date_with_no_flights_on_the_route_is_rejected(db):
    form = ValidateNewBookingForm()
    route = {"origin": "Nairobi", "destination": "Johannesburg"}
    with get_cursor() as cur:
        cur.execute("UPDATE flights SET seats_available = 0 WHERE destination = 'Johannesburg'")
    dispatcher = CollectingDispatcher()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    assert form.validate_travel_date(tomorrow, dispatcher, booking_tracker(route), {}) == {"travel_date": None}
    assert "no flights with seats" in dispatcher.messages[0]["text"]


def test_confirmed_guest_booking_is_saved(db):
    flights, route = dubai_flights()
    slots = dict(route, selected_flight_id=str(flights[0]["flight_id"]), passenger_name="Faith Njeri",
                 passenger_email="faith@example.com", confirm_booking=True)
    dispatcher = CollectingDispatcher()

    ActionNewBooking().run(dispatcher, booking_tracker(slots, intent="affirm"), {})

    assert dispatcher.messages[0]["text"].startswith("Booked! Your booking reference is BK007.")
    assert "faith@example.com" in dispatcher.messages[0]["text"]
    assert repo.get_booking("BK007")["passenger_name"] == "Faith Njeri"


def test_declined_booking_saves_nothing(db):
    flights, route = dubai_flights()
    slots = dict(route, selected_flight_id=str(flights[0]["flight_id"]), confirm_booking=False)
    dispatcher = CollectingDispatcher()

    ActionNewBooking().run(dispatcher, booking_tracker(slots, metadata={"user_id": 1}, intent="deny"), {})

    assert "haven't booked anything" in dispatcher.messages[0]["text"]
    assert repo.get_booking("BK007") is None


def test_a_hesitation_does_not_confirm_a_cancellation(db):
    form = ValidateCancelBookingForm()
    confirm = lambda text, value=True: form.validate_confirm_cancel(
        value, CollectingDispatcher(), booking_tracker({}, text=text, intent="affirm"), {})

    assert confirm("erm") == {"confirm_cancel": None}           # asked again
    assert confirm("yes please") == {"confirm_cancel": True}
    assert confirm("/affirm") == {"confirm_cancel": True}      # the Yes button
    assert confirm("no", value=False) == {"confirm_cancel": False}
