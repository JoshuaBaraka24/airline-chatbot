"""Task actions executed when a form completes, plus fallback and escalation."""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import EventType, FollowupAction, SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions import repository as repo
from actions.parsing import format_date, format_datetime

logger = logging.getLogger(__name__)

TASK_SLOTS = [
    "flight_number", "booking_reference", "travel_date", "origin", "destination",
    "confirm_cancel", "confirm_change", "new_flight_id",
]
ONLINE_CHECK_IN_WINDOW = timedelta(hours=36)
FALLBACKS_BEFORE_ESCALATION = 2
IGNORED_ACTIONS = {"action_listen", "action_extract_slots", "action_session_start"}

DB_ERROR = "Sorry, I can't reach our booking system right now. Please try again in a moment or type 'agent'."
STATUS_TEXT = {
    "on_time": "On time",
    "delayed": "Delayed",
    "cancelled": "Cancelled",
    "departed": "Departed",
    "landed": "Landed",
}


def reset_task_slots() -> List[EventType]:
    """Clear task slots so the next request starts fresh."""
    return [SlotSet(slot, None) for slot in TASK_SLOTS]


class ActionCheckFlightStatus(Action):
    def name(self) -> Text:
        return "action_check_flight_status"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: Dict[Text, Any]) -> List[EventType]:
        flight_number = tracker.get_slot("flight_number")
        try:
            flight = repo.get_next_flight(flight_number)
        except Exception:
            logger.exception("Flight status lookup failed for %s", flight_number)
            dispatcher.utter_message(text=DB_ERROR)
            return reset_task_slots()

        if not flight:
            dispatcher.utter_message(text=f"I couldn't find flight {flight_number}. Please double-check the flight number.")
            return reset_task_slots()

        message = (f"Flight {flight['flight_number']} from {flight['origin']} to {flight['destination']}\n"
                   f"- Departure: {format_datetime(flight['departure_time'])}\n"
                   f"- Arrival: {format_datetime(flight['arrival_time'])}\n"
                   f"- Status: {STATUS_TEXT.get(flight['status'], flight['status'])}")
        if flight["status"] == "delayed":
            message += "\nWe're sorry for the delay. Please keep checking for updates before you leave for the airport."
        elif flight["status"] == "cancelled":
            message += "\nWe're sorry, this flight has been cancelled. You can change your booking to another date, or type 'agent' for help."
        dispatcher.utter_message(text=message)
        return reset_task_slots()


class ActionCheckInStatus(Action):
    def name(self) -> Text:
        return "action_check_in_status"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: Dict[Text, Any]) -> List[EventType]:
        booking_ref = tracker.get_slot("booking_reference")
        try:
            booking = repo.get_booking(booking_ref)
        except Exception:
            logger.exception("Check-in status lookup failed for %s", booking_ref)
            dispatcher.utter_message(text=DB_ERROR)
            return reset_task_slots()

        ref = booking["booking_ref"]
        flight = f"{booking['flight_number']} to {booking['destination']} on {format_datetime(booking['departure_time'])}"
        if booking["status"] == "checked_in":
            dispatcher.utter_message(text=f"Booking {ref} is checked in for {flight}. You're all set!")
        elif booking["status"] == "cancelled":
            dispatcher.utter_message(text=f"Booking {ref} has been cancelled, so there is nothing to check in.")
        else:
            opens_at = booking["departure_time"] - ONLINE_CHECK_IN_WINDOW
            if datetime.now() >= opens_at:
                when = "Online check-in is open now at kenyaairways.com."
            else:
                when = f"Online check-in opens {format_datetime(opens_at)} (36 hours before departure)."
            dispatcher.utter_message(text=f"Booking {ref} for {flight} is confirmed but not yet checked in. {when}")
        return reset_task_slots()


class ActionCancelBooking(Action):
    def name(self) -> Text:
        return "action_cancel_booking"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: Dict[Text, Any]) -> List[EventType]:
        booking_ref = tracker.get_slot("booking_reference")
        if not tracker.get_slot("confirm_cancel"):
            dispatcher.utter_message(text=f"No problem, booking {booking_ref} has not been cancelled.")
            return reset_task_slots()
        try:
            cancelled = repo.cancel_booking(booking_ref)
        except Exception:
            logger.exception("Cancellation failed for %s", booking_ref)
            dispatcher.utter_message(text=DB_ERROR)
            return reset_task_slots()

        if cancelled:
            dispatcher.utter_message(
                text=f"Booking {booking_ref} has been cancelled. Your refund will be processed within 7 business days "
                     "and a confirmation email is on its way."
            )
        else:
            dispatcher.utter_message(text=f"Booking {booking_ref} could not be cancelled because it is no longer active.")
        return reset_task_slots()


class ActionChangeBooking(Action):
    def name(self) -> Text:
        return "action_change_booking"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: Dict[Text, Any]) -> List[EventType]:
        booking_ref = tracker.get_slot("booking_reference")
        if not tracker.get_slot("confirm_change"):
            dispatcher.utter_message(text=f"Okay, I've left booking {booking_ref} unchanged.")
            return reset_task_slots()
        try:
            changed = repo.change_booking_flight(booking_ref, int(tracker.get_slot("new_flight_id")))
            booking = repo.get_booking(booking_ref) if changed else None
        except Exception:
            logger.exception("Booking change failed for %s", booking_ref)
            dispatcher.utter_message(text=DB_ERROR)
            return reset_task_slots()

        if changed:
            dispatcher.utter_message(
                text=f"Done! Booking {booking_ref} is now on {booking['flight_number']} departing "
                     f"{format_datetime(booking['departure_time'])}. A confirmation email is on its way."
            )
        else:
            dispatcher.utter_message(text="Sorry, that flight has just sold out. Please try another date.")
        return reset_task_slots()


class ActionNewBooking(Action):
    """Searches the schedule for the requested route and date."""

    def name(self) -> Text:
        return "action_new_booking"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: Dict[Text, Any]) -> List[EventType]:
        origin = tracker.get_slot("origin")
        destination = tracker.get_slot("destination")
        travel_date = date.fromisoformat(tracker.get_slot("travel_date"))
        try:
            flights = repo.search_flights(origin, destination, travel_date)
            nearby = False
            if not flights:
                flights = repo.next_flights_on_route(origin, destination)
                nearby = True
        except Exception:
            logger.exception("Flight search failed for %s -> %s", origin, destination)
            dispatcher.utter_message(text=DB_ERROR)
            return reset_task_slots()

        if not flights:
            dispatcher.utter_message(
                text=f"There are no flights with seats from {origin} to {destination} at the moment. "
                     "Please call +254 20 327 4747 for more options."
            )
            return reset_task_slots()

        lines = "\n".join(
            f"- {f['flight_number']}: {format_datetime(f['departure_time'])} ({f['seats_available']} seats left)"
            for f in flights
        )
        heading = (f"There are no flights from {origin} to {destination} around {format_date(travel_date)}. "
                   "The next available ones are:" if nearby
                   else f"Flights from {origin} to {destination} from {format_date(travel_date)}:")
        dispatcher.utter_message(
            text=f"{heading}\n{lines}\n\nTo complete your booking, visit kenyaairways.com or call +254 20 327 4747."
        )
        return reset_task_slots()


class ActionEscalateToAgent(Action):
    """Hands the conversation to a human agent (FR-04)."""

    def name(self) -> Text:
        return "action_escalate_to_agent"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: Dict[Text, Any]) -> List[EventType]:
        dispatcher.utter_message(response="utter_escalate")
        try:
            repo.mark_conversation_escalated(tracker.sender_id)
        except Exception:
            logger.exception("Could not flag conversation %s as escalated", tracker.sender_id)
        return reset_task_slots()


class ActionHandleFallback(Action):
    """Asks the passenger to rephrase; escalates after repeated misunderstandings."""

    def name(self) -> Text:
        return "action_handle_fallback"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: Dict[Text, Any]) -> List[EventType]:
        # Count this fallback plus any immediately preceding ones. Both NLU fallbacks
        # (low intent confidence) and core fallbacks (no confident next action) run
        # this action, so counting its executions covers both.
        consecutive = 1
        for event in reversed(tracker.events):
            if event.get("event") != "action" or event.get("name") in IGNORED_ACTIONS:
                continue
            if event.get("name") != self.name():
                break
            consecutive += 1

        if consecutive >= FALLBACKS_BEFORE_ESCALATION:
            dispatcher.utter_message(text="I'm sorry I'm having trouble understanding.")
            return ActionEscalateToAgent().run(dispatcher, tracker, domain) + [FollowupAction("action_listen")]
        dispatcher.utter_message(response="utter_default")
        # Core fallbacks are not followed by a rule, so hand the turn back explicitly
        return [FollowupAction("action_listen")]


class ActionStopTask(Action):
    """Confirms that the current request was abandoned and clears its slots."""

    def name(self) -> Text:
        return "action_stop_task"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: Dict[Text, Any]) -> List[EventType]:
        dispatcher.utter_message(response="utter_task_stopped")
        return reset_task_slots()
