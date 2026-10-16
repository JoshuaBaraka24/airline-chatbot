"""Slot validation for the dialogue forms and custom confirmation prompts.

Each form collects its slots over several turns (FR-02). Validators
normalise what the passenger typed, check it against the database, and
either accept the value or explain the problem and ask again.
"""
import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Action, FormValidationAction, Tracker
from rasa_sdk.events import EventType
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from actions import repository as repo
from actions.parsing import (
    format_date,
    format_datetime,
    match_city,
    normalize_booking_ref,
    normalize_flight_number,
    parse_date,
)

logger = logging.getLogger(__name__)

# Questions a passenger may ask in the middle of a form. They are answered
# and the form re-asks its current question instead of treating the
# question text as a slot value.
INTERRUPTION_RESPONSES = {
    "baggage_policy": "utter_baggage_policy",
    "check_in_procedure": "utter_check_in_procedure",
    "bot_capabilities": "utter_bot_capabilities",
    "out_of_scope": "utter_out_of_scope",
    "greet": "utter_greet_in_form",
    "thank_you": "utter_you_are_welcome",
}

SLOT_ROLE = {"origin": "from", "destination": "to"}
EXPLICIT_DIRECTION_RE = re.compile(r"\b(from|to)\b", re.IGNORECASE)

DB_ERROR = "Sorry, I can't reach our booking system right now. Please try again in a moment or type 'agent'."
YES_NO_BUTTONS = [
    {"title": "Yes", "payload": "/affirm"},
    {"title": "No", "payload": "/deny"},
]


def answered_interruption(dispatcher: CollectingDispatcher, tracker: Tracker) -> bool:
    intent = tracker.latest_message.get("intent", {}).get("name")
    response = INTERRUPTION_RESPONSES.get(intent)
    if response:
        dispatcher.utter_message(response=response)
        return True
    return False


def previous_slot_value(tracker: Tracker, slot: Text) -> Any:
    """Value a slot had before the latest user message."""
    seen_user_turn = False
    for event in reversed(tracker.events):
        if event.get("event") == "user":
            seen_user_turn = True
        elif seen_user_turn and event.get("event") == "slot" and event.get("name") == slot:
            return event.get("value")
    return None


class BookingReferenceMixin:
    """Shared booking-reference validation.

    allowed_statuses: booking statuses the form can act on.
    """

    allowed_statuses = ("confirmed", "checked_in", "cancelled")

    def validate_booking_reference(
        self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        if answered_interruption(dispatcher, tracker):
            return {"booking_reference": None}

        booking_ref = normalize_booking_ref(slot_value)
        if not booking_ref:
            dispatcher.utter_message(
                text="That doesn't look like a booking reference. It should look like BK001."
            )
            return {"booking_reference": None}
        try:
            booking = repo.get_booking(booking_ref)
        except Exception:
            logger.exception("Booking lookup failed for %s", booking_ref)
            dispatcher.utter_message(text=DB_ERROR)
            return {"booking_reference": None}

        if not booking:
            dispatcher.utter_message(
                text=f"I couldn't find a booking with reference {booking_ref}. Please check it and try again, "
                     "or say 'never mind' to stop."
            )
            return {"booking_reference": None}
        if booking["status"] not in self.allowed_statuses:
            dispatcher.utter_message(text=self.status_not_allowed_message(booking))
            return {"booking_reference": None}
        return {"booking_reference": booking_ref}

    def status_not_allowed_message(self, booking: dict) -> Text:
        return f"Booking {booking['booking_ref']} can't be used for this request."


def _confirmed_only_message(action: Text):
    def message(booking: dict) -> Text:
        ref = booking["booking_ref"]
        if booking["status"] == "cancelled":
            return f"Booking {ref} has already been cancelled. Please give a different reference, or say 'never mind'."
        return (f"Booking {ref} is already checked in, so I can't {action} it here. "
                "Please give a different reference, or type 'agent' to speak to a person.")
    return message


class ValidateFlightStatusForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_flight_status_form"

    def validate_flight_number(
        self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        if answered_interruption(dispatcher, tracker):
            return {"flight_number": None}
        flight_number = normalize_flight_number(slot_value)
        if not flight_number:
            dispatcher.utter_message(text="That doesn't look like a Kenya Airways flight number. It should look like KQ101.")
            return {"flight_number": None}
        return {"flight_number": flight_number}


class ValidateCheckInStatusForm(BookingReferenceMixin, FormValidationAction):
    def name(self) -> Text:
        return "validate_check_in_status_form"


class ValidateCancelBookingForm(BookingReferenceMixin, FormValidationAction):
    allowed_statuses = ("confirmed",)

    def name(self) -> Text:
        return "validate_cancel_booking_form"

    def status_not_allowed_message(self, booking: dict) -> Text:
        return _confirmed_only_message("cancel")(booking)


class ValidateChangeBookingForm(BookingReferenceMixin, FormValidationAction):
    allowed_statuses = ("confirmed",)

    def name(self) -> Text:
        return "validate_change_booking_form"

    def status_not_allowed_message(self, booking: dict) -> Text:
        return _confirmed_only_message("change")(booking)

    def validate_travel_date(
        self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        if answered_interruption(dispatcher, tracker):
            return {"travel_date": None}

        booking_ref = tracker.get_slot("booking_reference")
        if not booking_ref:
            # The date will be asked again once a valid booking is known
            return {"travel_date": None}

        new_date = parse_date(slot_value)
        if not new_date:
            dispatcher.utter_message(text="Sorry, I didn't understand that date. Try something like '25 October' or 'next Friday'.")
            return {"travel_date": None}
        if new_date < date.today():
            dispatcher.utter_message(text=f"{format_date(new_date)} is in the past. Please choose a future date.")
            return {"travel_date": None}

        try:
            booking = repo.get_booking(booking_ref)
            if booking["departure_time"].date() == new_date:
                dispatcher.utter_message(text=f"Your booking is already on {format_date(new_date)}. Please choose a different date.")
                return {"travel_date": None}
            flight = repo.find_available_flight(booking["flight_number"], new_date)
            if not flight:
                alternatives = [
                    f["departure_time"] for f in repo.upcoming_departures(booking["flight_number"])
                    if f["flight_id"] != booking["flight_id"]
                ]
                message = f"There's no available {booking['flight_number']} flight on {format_date(new_date)}."
                if alternatives:
                    options = ", ".join(format_date(d) for d in alternatives)
                    message += f" It operates on: {options}. Which date would you like?"
                else:
                    message += " There are no other dates with seats right now; type 'agent' for more options."
                dispatcher.utter_message(text=message)
                return {"travel_date": None}
        except Exception:
            logger.exception("Date validation failed for %s", booking_ref)
            dispatcher.utter_message(text=DB_ERROR)
            return {"travel_date": None}

        return {"travel_date": new_date.isoformat(), "new_flight_id": flight["flight_id"]}


class ValidateNewBookingForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_new_booking_form"

    def _validate_city(
        self, slot: Text, other_slot: Text, slot_value: Any,
        dispatcher: CollectingDispatcher, tracker: Tracker,
    ) -> Dict[Text, Any]:
        if answered_interruption(dispatcher, tracker):
            return {slot: None}

        requested = tracker.get_slot("requested_slot")
        message = tracker.latest_message.get("text") or ""
        city_entities = [e for e in tracker.latest_message.get("entities", []) if e.get("entity") == "city"]
        explicit = EXPLICIT_DIRECTION_RE.search(message) is not None

        if requested == other_slot and not explicit and len(city_entities) <= 1:
            # A bare city answering the *other* question belongs to that slot, even
            # if NLU tagged it with this slot's role; keep this slot's earlier value.
            return {slot: previous_slot_value(tracker, slot)}
        if requested == slot and explicit and city_entities and all(
            e.get("role") and e.get("role") != SLOT_ROLE[slot] for e in city_entities
        ):
            # e.g. "to Dubai" when asked where from: that city fills the other slot,
            # and this question is simply asked again.
            return {slot: None}
        if requested == slot and not city_entities and tracker.latest_message.get("entities"):
            # The reply carried other information (e.g. a date) but no city; re-ask quietly.
            return {slot: None}

        column = "origin" if slot == "origin" else "destination"
        try:
            cities = repo.served_cities(column)
        except Exception:
            logger.exception("City lookup failed")
            dispatcher.utter_message(text=DB_ERROR)
            return {slot: None}

        city = match_city(slot_value, cities)
        if not city:
            label = "from" if slot == "origin" else "to"
            dispatcher.utter_message(
                text=f"Sorry, we don't currently fly {label} {slot_value}. "
                     f"We fly {label}: {', '.join(cities)}."
            )
            return {slot: None}

        other = tracker.get_slot(other_slot)
        if other and other.lower() == city.lower() and requested == slot:
            dispatcher.utter_message(text="The departure and arrival cities can't be the same.")
            return {slot: None}
        return {slot: city}

    def validate_origin(self, slot_value, dispatcher, tracker, domain) -> Dict[Text, Any]:
        return self._validate_city("origin", "destination", slot_value, dispatcher, tracker)

    def validate_destination(self, slot_value, dispatcher, tracker, domain) -> Dict[Text, Any]:
        result = self._validate_city("destination", "origin", slot_value, dispatcher, tracker)
        origin = tracker.get_slot("origin")
        destination = result.get("destination")
        if origin and destination and destination != previous_slot_value(tracker, "destination"):
            try:
                if not repo.route_exists(origin, destination):
                    dispatcher.utter_message(text=f"Sorry, we don't have direct flights from {origin} to {destination}.")
                    return {"destination": None}
            except Exception:
                logger.exception("Route lookup failed")
        return result

    def validate_travel_date(self, slot_value, dispatcher, tracker, domain) -> Dict[Text, Any]:
        if answered_interruption(dispatcher, tracker):
            return {"travel_date": None}
        travel_date = parse_date(slot_value)
        if not travel_date:
            dispatcher.utter_message(text="Sorry, I didn't understand that date. Try something like '25 October' or 'next Friday'.")
            return {"travel_date": None}
        if travel_date < date.today():
            dispatcher.utter_message(text=f"{format_date(travel_date)} is in the past. Please choose a future date.")
            return {"travel_date": None}
        return {"travel_date": travel_date.isoformat()}


class ActionAskConfirmCancel(Action):
    """Shows the booking that will be cancelled and asks for a yes/no."""

    def name(self) -> Text:
        return "action_ask_confirm_cancel"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[EventType]:
        booking_ref = tracker.get_slot("booking_reference")
        try:
            b = repo.get_booking(booking_ref)
            dispatcher.utter_message(
                text=f"I found booking {b['booking_ref']} for {b['passenger_name']}: {b['flight_number']} "
                     f"{b['origin']} to {b['destination']}, {format_datetime(b['departure_time'])}.\n"
                     "Are you sure you want to cancel it? A refund will be processed within 7 business days.",
                buttons=YES_NO_BUTTONS,
            )
        except Exception:
            logger.exception("Could not load booking %s for confirmation", booking_ref)
            dispatcher.utter_message(text=f"Do you want to cancel booking {booking_ref}?", buttons=YES_NO_BUTTONS)
        return []


class ActionAskConfirmChange(Action):
    """Shows the current and proposed flight and asks for a yes/no."""

    def name(self) -> Text:
        return "action_ask_confirm_change"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[EventType]:
        booking_ref = tracker.get_slot("booking_reference")
        new_date = tracker.get_slot("travel_date")
        try:
            b = repo.get_booking(booking_ref)
            new_flight = repo.find_available_flight(b["flight_number"], date.fromisoformat(new_date))
            dispatcher.utter_message(
                text=f"Booking {b['booking_ref']} ({b['flight_number']} {b['origin']} to {b['destination']}):\n"
                     f"- Current: {format_datetime(b['departure_time'])}\n"
                     f"- New: {format_datetime(new_flight['departure_time'])}\n"
                     "Shall I confirm this change?",
                buttons=YES_NO_BUTTONS,
            )
        except Exception:
            logger.exception("Could not load change details for %s", booking_ref)
            dispatcher.utter_message(text=f"Shall I move booking {booking_ref} to {new_date}?", buttons=YES_NO_BUTTONS)
        return []


class ActionAskBookingReference(Action):
    """Asks for a booking reference, offering a logged-in passenger's own bookings as buttons.

    The web portal passes the passenger's user_id as message metadata.
    """

    # Bookings each form can act on
    STATUSES_BY_FORM = {
        "cancel_booking_form": ("confirmed",),
        "change_booking_form": ("confirmed",),
        "check_in_status_form": ("confirmed", "checked_in"),
    }

    def name(self) -> Text:
        return "action_ask_booking_reference"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[EventType]:
        metadata = tracker.latest_message.get("metadata") or {}
        user_id = metadata.get("user_id")
        form = (tracker.active_loop or {}).get("name")
        bookings = []
        if user_id:
            try:
                bookings = repo.bookings_for_user(int(user_id), self.STATUSES_BY_FORM.get(form, ("confirmed", "checked_in")))
            except Exception:
                logger.exception("Could not load bookings for user %s", user_id)

        if not bookings:
            dispatcher.utter_message(response="utter_ask_booking_reference")
            return []

        buttons = [
            {
                "title": f"{b['booking_ref']} · {b['flight_number']} {b['origin']} → {b['destination']}, "
                         f"{b['departure_time']:%d %b}",
                "payload": f'/inform{{"booking_reference":"{b["booking_ref"]}"}}',
            }
            for b in bookings
        ]
        name = metadata.get("name", "").split(" ")[0]
        greeting = f"{name}, which" if name else "Which"
        dispatcher.utter_message(
            text=f"{greeting} booking is this about? Choose one below or type a booking reference.",
            buttons=buttons,
        )
        return []
