"""Who may see and change a booking: its owner when logged in, or a guest who gives its email."""
import asyncio

import pytest
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions import forms
from actions import repository as repo
from actions.actions import NOT_THEIRS, ActionCancelBooking, ActionChangeBooking, ActionCheckInStatus
from actions.db import get_cursor
from actions.forms import (
    ActionAskConfirmCancel,
    ActionAskConfirmChange,
    ActionAskConfirmCheckIn,
    ValidateCancelBookingForm,
    ValidateChangeBookingForm,
    ValidateCheckInStatusForm,
)

JOHN = {"user_id": 1, "name": "John Mwangi"}  # owns BK001
SLOTS = ["booking_reference", "booking_email", "confirm_cancel"]
PRIVATE = ["Amina", "Dubai", "KQ202", "amina@email.com"]  # what BK002's owner sees


def tracker(slots, text="", metadata=None, sender="guest", intent="inform"):
    return Tracker(
        sender_id=sender, slots=slots,
        latest_message={"text": text, "entities": [], "metadata": metadata, "intent": {"name": intent}},
        events=[], paused=False, followup_action=None, active_loop={"name": "cancel_booking_form"},
        latest_action_name=None,
    )


def give_reference(ref, metadata=None, email=None, form=ValidateCancelBookingForm, requested="booking_reference"):
    out = CollectingDispatcher()
    slots = {"booking_email": email, "requested_slot": requested}
    result = form().validate_booking_reference(ref, out, tracker(slots, ref, metadata), {})
    return result, " ".join(m.get("text") or "" for m in out.messages)


def give_email(text, ref="BK002", metadata=None, sender="guest", form=ValidateCancelBookingForm):
    out = CollectingDispatcher()
    slots = {"booking_reference": ref, "requested_slot": "booking_email"}
    result = form().validate_booking_email(text, out, tracker(slots, text, metadata, sender), {})
    return result, " ".join(m.get("text") or "" for m in out.messages)


# --- logged-in passengers ---

def test_logged_in_passengers_can_use_their_own_booking_without_an_email(db):
    assert give_reference("BK001", JOHN)[0] == {"booking_reference": "BK001"}
    needed = asyncio.run(ValidateCancelBookingForm().required_slots(
        SLOTS, CollectingDispatcher(), tracker({"booking_reference": "BK001"}, metadata=JOHN), {}))
    assert needed == ["booking_reference", "confirm_cancel"]


def test_logged_in_passengers_cannot_use_someone_elses_booking(db):
    others, message = give_reference("BK002", JOHN)
    assert others == {"booking_reference": None}
    assert message.startswith("I couldn't find booking BK002 on your account.")
    # ... and a reference that doesn't exist gets the same answer
    assert give_reference("BK900", JOHN)[1] == message.replace("BK002", "BK900")


def test_knowing_the_email_does_not_help_a_logged_in_passenger(db):
    result, message = give_email("amina@email.com", metadata=JOHN)
    assert result == {"booking_reference": None, "booking_email": None}
    assert "on your account" in message


# --- guests ---

def test_guests_are_asked_for_an_email_and_told_nothing_before_it(db):
    result, message = give_reference("BK002")
    assert result == {"booking_reference": "BK002"} and message == ""
    assert give_reference("BK900") == ({"booking_reference": "BK900"}, "")  # looks no different
    assert give_reference("BK006") == ({"booking_reference": "BK006"}, "")  # cancelled: not said yet
    needed = asyncio.run(ValidateCancelBookingForm().required_slots(
        SLOTS, CollectingDispatcher(), tracker({"booking_reference": "BK002"}), {}))
    assert needed == SLOTS


@pytest.mark.parametrize("text", ["amina@email.com", "AMINA@email.com", "it's Amina@Email.com thanks"])
def test_the_right_email_unlocks_a_booking(db, text):
    assert give_email(text) == ({"booking_email": "amina@email.com"}, "")


def test_a_wrong_email_is_refused_without_revealing_the_booking(db):
    result, message = give_email("john@email.com")
    assert result == {"booking_email": None}
    assert not any(word in message for word in PRIVATE)
    missing = give_email("john@email.com", ref="BK900", sender="other")[1]
    assert missing == message.replace("BK002", "BK900")  # a real reference can't be told from a made-up one


def test_the_email_of_a_booking_made_in_the_chat_unlocks_it(db):
    flight = repo.next_flights_on_route("Nairobi", "Dubai")[0]["flight_id"]
    ref = repo.create_booking(flight, passenger_name="Faith Njeri", email="Faith@safari.test")
    assert give_email("faith@safari.test", ref=ref)[0] == {"booking_email": "faith@safari.test"}


def test_text_that_is_not_an_email_is_asked_again(db):
    result, message = give_email("I don't remember")
    assert result == {"booking_email": None} and "doesn't look like an email" in message


def test_a_booking_that_cannot_be_used_is_explained_only_to_its_owner(db):
    result, message = give_email("mary@email.com", ref="BK006")
    assert result == {"booking_reference": None, "booking_email": "mary@email.com"}
    assert "already been cancelled" in message


def test_a_different_reference_can_be_given_at_the_email_question(db):
    # the typed reference lands in both slots, as in a real conversation
    out = CollectingDispatcher()
    t = tracker({"booking_reference": "BK002", "booking_email": "BK002", "requested_slot": "booking_email"}, "BK002")
    assert ValidateCancelBookingForm().validate_booking_reference("BK002", out, t, {}) == {"booking_reference": "BK002"}
    assert ValidateCancelBookingForm().validate_booking_email("BK002", out, t, {}) == {"booking_email": None}
    assert out.messages == []


def test_an_email_containing_a_reference_does_not_change_the_booking(db):
    t = tracker({"requested_slot": "booking_email"}, "bk001@email.com")
    t.events = [{"event": "slot", "name": "booking_reference", "value": "BK002"},
                {"event": "user"}, {"event": "slot", "name": "booking_reference", "value": "bk001"}]
    assert ValidateCancelBookingForm().validate_booking_reference("bk001", CollectingDispatcher(), t, {}) == {
        "booking_reference": "BK002"}


# --- switching booking after passing the check ---

def test_switching_to_another_reference_is_checked_again(db):
    result, message = give_reference("BK002", email="john@email.com", requested="confirm_cancel")
    assert result == {"booking_reference": None, "booking_email": None}
    assert not any(word in message for word in PRIVATE)


@pytest.mark.parametrize("slots, metadata", [
    ({}, None),                                  # guest, no email
    ({"booking_email": "john@email.com"}, None),  # guest, another booking's email
    ({}, JOHN),                                  # logged in, someone else's booking
    ({"booking_email": "amina@email.com"}, JOHN),  # logged in, knows the email
])
def test_nothing_is_shown_or_changed_for_someone_elses_booking(db, slots, metadata):
    flight = repo.next_flights_on_route("Nairobi", "Dubai")[-1]["flight_id"]
    slots = dict(slots, booking_reference="BK002", confirm_cancel=True, confirm_change=True, confirm_check_in=True,
                 new_flight_id=str(flight), travel_date="2030-01-01")
    with get_cursor() as cur:
        cur.execute("UPDATE flights SET departure_time = NOW() + INTERVAL '5 hours' WHERE flight_id = "
                    "(SELECT flight_id FROM bookings WHERE booking_ref = 'BK002')")  # check-in is open
    before = dict(repo.get_booking("BK002"))

    for action in (ActionCancelBooking, ActionChangeBooking, ActionCheckInStatus):
        out = CollectingDispatcher()
        action().run(out, tracker(dict(slots), metadata=metadata, intent="affirm"), {})
        assert out.messages[0]["text"] == NOT_THEIRS
    for question in (ActionAskConfirmCancel, ActionAskConfirmChange, ActionAskConfirmCheckIn):
        out = CollectingDispatcher()
        question().run(out, tracker(dict(slots), metadata=metadata), {})
        assert not any(word in out.messages[0]["text"] for word in PRIVATE)
    out = CollectingDispatcher()
    assert ValidateChangeBookingForm().validate_travel_date(
        "2030-01-01", out, tracker(dict(slots), metadata=metadata), {}) == {"travel_date": None}
    assert out.messages == []

    assert dict(repo.get_booking("BK002")) == before


def test_check_in_is_not_offered_for_someone_elses_booking(db):
    needed = asyncio.run(ValidateCheckInStatusForm().required_slots(
        ["booking_reference", "booking_email", "confirm_check_in"], CollectingDispatcher(),
        tracker({"booking_reference": "BK003", "booking_email": "john@email.com"}), {}))
    assert "confirm_check_in" not in needed


# --- guessing ---

def test_five_wrong_emails_lock_a_booking_for_guests(db):
    for i in range(5):
        assert "couldn't find booking" in give_email(f"guess{i}@email.com", sender=f"visitor{i}")[1]
    result, message = give_email("amina@email.com", sender="new visitor")  # even the right one, from anyone
    assert result == {"booking_email": None} and "too many attempts" in message
    assert give_email("john@email.com", ref="BK001", sender="john")[0] == {"booking_email": "john@email.com"}


def test_trying_one_email_on_many_references_is_also_stopped(db):
    for n in range(5):
        give_email("john@email.com", ref=f"BK80{n}", sender="scanner")
    assert "too many attempts" in give_email("john@email.com", ref="BK001", sender="scanner")[1]


def test_the_right_email_clears_earlier_mistakes(db):
    for _ in range(4):
        give_email("wrong@email.com")
    assert give_email("amina@email.com")[0] == {"booking_email": "amina@email.com"}
    assert not forms.email_guesses.is_blocked("ref:BK002")
