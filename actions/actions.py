import logging
from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions.db import get_cursor

logger = logging.getLogger(__name__)


class ActionCheckFlightStatus(Action):
    def name(self) -> Text:
        return "action_check_flight_status"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        flight_number = tracker.get_slot("flight_number")
        if not flight_number:
            dispatcher.utter_message(response="utter_ask_flight_number")
            return []
        try:
            with get_cursor() as cur:
                cur.execute(
                    "SELECT flight_number, origin, destination, departure_time, status FROM flights "
                    "WHERE flight_number = UPPER(REPLACE(%s, ' ', '')) "
                    "ORDER BY departure_time LIMIT 1",
                    (flight_number,)
                )
                result = cur.fetchone()
            if result:
                dispatcher.utter_message(
                    text=f"Flight {result['flight_number']} from {result['origin']} to {result['destination']} "
                         f"departs at {result['departure_time']:%d %b %Y %H:%M}. Current status: {result['status']}."
                )
            else:
                dispatcher.utter_message(text=f"I couldn't find flight {flight_number}. Please double-check the flight number.")
        except Exception:
            logger.exception("Flight status lookup failed for %s", flight_number)
            dispatcher.utter_message(text="I'm having trouble accessing flight information right now. Please try again.")
        return []


class ActionChangeBooking(Action):
    def name(self) -> Text:
        return "action_change_booking"

    def run(self, dispatcher, tracker, domain):
        booking_ref = tracker.get_slot("booking_reference")
        new_date = tracker.get_slot("date")
        if not booking_ref or not new_date:
            dispatcher.utter_message(text="I need both your booking reference and new date to make changes.")
            return []
        try:
            with get_cursor() as cur:
                cur.execute(
                    "SELECT b.booking_ref, f.flight_number FROM bookings b JOIN flights f USING (flight_id) "
                    "WHERE b.booking_ref = UPPER(%s) AND b.status = 'confirmed'",
                    (booking_ref,)
                )
                booking = cur.fetchone()
                if not booking:
                    dispatcher.utter_message(text=f"I couldn't find an active booking with reference {booking_ref}.")
                    return []
                # Move the booking to the same flight number on the requested date
                cur.execute(
                    "SELECT flight_id, departure_time FROM flights "
                    "WHERE flight_number = %s AND departure_time::date = %s::date "
                    "AND status <> 'cancelled' AND seats_available > 0",
                    (booking["flight_number"], new_date)
                )
                new_flight = cur.fetchone()
                if not new_flight:
                    dispatcher.utter_message(text=f"There is no available {booking['flight_number']} flight on {new_date}. Please try another date.")
                    return []
                cur.execute(
                    "UPDATE bookings SET flight_id = %s, updated_at = NOW() WHERE booking_ref = %s",
                    (new_flight["flight_id"], booking["booking_ref"])
                )
            dispatcher.utter_message(
                text=f"Your booking {booking['booking_ref']} has been moved to {booking['flight_number']} "
                     f"departing {new_flight['departure_time']:%d %b %Y %H:%M}. A confirmation email will be sent shortly."
            )
        except Exception:
            logger.exception("Booking change failed for %s", booking_ref)
            dispatcher.utter_message(text="I couldn't process the change right now. Please try again or speak to an agent.")
        return []


class ActionCancelBooking(Action):
    def name(self) -> Text:
        return "action_cancel_booking"

    def run(self, dispatcher, tracker, domain):
        booking_ref = tracker.get_slot("booking_reference")
        if not booking_ref:
            dispatcher.utter_message(response="utter_ask_booking_ref")
            return []
        try:
            with get_cursor() as cur:
                cur.execute(
                    "UPDATE bookings SET status = 'cancelled', updated_at = NOW() "
                    "WHERE booking_ref = UPPER(%s) AND status = 'confirmed' RETURNING booking_ref",
                    (booking_ref,)
                )
                result = cur.fetchone()
            if result:
                dispatcher.utter_message(text=f"Booking {result['booking_ref']} has been successfully cancelled. Refund will be processed within 7 business days.")
            else:
                dispatcher.utter_message(text=f"No active booking found with reference {booking_ref}.")
        except Exception:
            logger.exception("Cancellation failed for %s", booking_ref)
            dispatcher.utter_message(text="I couldn't process the cancellation right now. Please try again.")
        return []


class ActionNewBooking(Action):
    def name(self) -> Text:
        return "action_new_booking"

    def run(self, dispatcher, tracker, domain):
        origin = tracker.get_slot("origin")
        destination = tracker.get_slot("destination")
        date = tracker.get_slot("date")
        if not all([origin, destination, date]):
            dispatcher.utter_message(text="I need your origin, destination, and travel date to search for flights.")
            return []
        try:
            with get_cursor() as cur:
                cur.execute(
                    "SELECT flight_number, departure_time FROM flights "
                    "WHERE LOWER(origin) = LOWER(%s) AND LOWER(destination) = LOWER(%s) "
                    "AND status <> 'cancelled' AND seats_available > 0 AND departure_time > NOW() "
                    "ORDER BY departure_time LIMIT 3",
                    (origin, destination)
                )
                results = cur.fetchall()
            if results:
                flight_list = "\n".join(f"- {r['flight_number']} departing {r['departure_time']:%d %b %Y %H:%M}" for r in results)
                dispatcher.utter_message(text=f"Available flights from {origin} to {destination}:\n{flight_list}\n\nPlease call +254 20 327 4747 or visit kenyaairways.com to complete your booking.")
            else:
                dispatcher.utter_message(text=f"No available flights found from {origin} to {destination} on {date}. Try different dates or call our reservations team.")
        except Exception:
            logger.exception("Flight search failed for %s -> %s", origin, destination)
            dispatcher.utter_message(text="I couldn't search for flights right now. Please try again.")
        return []


class ActionCheckInStatus(Action):
    def name(self) -> Text:
        return "action_check_in_status"

    def run(self, dispatcher, tracker, domain):
        booking_ref = tracker.get_slot("booking_reference")
        if not booking_ref:
            dispatcher.utter_message(response="utter_ask_booking_ref")
            return []
        try:
            with get_cursor() as cur:
                cur.execute("SELECT booking_ref, status FROM bookings WHERE booking_ref = UPPER(%s)", (booking_ref,))
                result = cur.fetchone()
            if result:
                status = result["status"]
                if status == "checked_in":
                    dispatcher.utter_message(text=f"Booking {result['booking_ref']} is checked in. You're all set!")
                elif status == "confirmed":
                    dispatcher.utter_message(text=f"Booking {result['booking_ref']} is confirmed but not yet checked in. Online check-in opens 36 hours before departure.")
                else:
                    dispatcher.utter_message(text=f"Booking {result['booking_ref']} status is: {status}.")
            else:
                dispatcher.utter_message(text=f"No booking found with reference {booking_ref}.")
        except Exception:
            logger.exception("Check-in status lookup failed for %s", booking_ref)
            dispatcher.utter_message(text="I couldn't retrieve your check-in status right now.")
        return []
