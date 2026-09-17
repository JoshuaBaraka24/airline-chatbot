import psycopg2
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from typing import Any, Text, Dict, List

DB_CONFIG = {
    "dbname": "airline_db",
    "user": "postgres",
    "password": "YOUR_POSTGRES_PASSWORD",  # change this
    "host": "localhost",
    "port": "5432"
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


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
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT flight_number, origin, destination, departure_time, status FROM flights WHERE UPPER(flight_number) = UPPER(%s)",
                (flight_number,)
            )
            result = cur.fetchone()
            conn.close()
            if result:
                dispatcher.utter_message(
                    text=f"Flight {result[0]} from {result[1]} to {result[2]} departs at {result[3]}. Current status: {result[4]}."
                )
            else:
                dispatcher.utter_message(text=f"I couldn't find flight {flight_number}. Please double-check the flight number.")
        except Exception as e:
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
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT booking_ref FROM bookings WHERE booking_ref = %s AND status = 'confirmed'", (booking_ref,))
            result = cur.fetchone()
            if result:
                # In a real system you'd update the flight_id; here we log the change request
                cur.execute("UPDATE bookings SET status = 'change_requested' WHERE booking_ref = %s", (booking_ref,))
                conn.commit()
                dispatcher.utter_message(text=f"Your booking {booking_ref} has been flagged for change to {new_date}. A confirmation email will be sent shortly.")
            else:
                dispatcher.utter_message(text=f"I couldn't find an active booking with reference {booking_ref}.")
            conn.close()
        except Exception as e:
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
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT booking_ref FROM bookings WHERE booking_ref = %s AND status = 'confirmed'", (booking_ref,))
            result = cur.fetchone()
            if result:
                cur.execute("UPDATE bookings SET status = 'cancelled' WHERE booking_ref = %s", (booking_ref,))
                conn.commit()
                dispatcher.utter_message(text=f"Booking {booking_ref} has been successfully cancelled. Refund will be processed within 7 business days.")
            else:
                dispatcher.utter_message(text=f"No active booking found with reference {booking_ref}.")
            conn.close()
        except Exception as e:
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
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT flight_number, departure_time FROM flights WHERE LOWER(origin) = LOWER(%s) AND LOWER(destination) = LOWER(%s) AND status = 'on_time'",
                (origin, destination)
            )
            results = cur.fetchall()
            conn.close()
            if results:
                flight_list = "\n".join([f"- {r[0]} departing {r[1]}" for r in results[:3]])
                dispatcher.utter_message(text=f"Available flights from {origin} to {destination}:\n{flight_list}\n\nPlease call +254 20 327 4747 or visit kenyaairways.com to complete your booking.")
            else:
                dispatcher.utter_message(text=f"No available flights found from {origin} to {destination} on {date}. Try different dates or call our reservations team.")
        except Exception as e:
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
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT status FROM bookings WHERE booking_ref = %s", (booking_ref,))
            result = cur.fetchone()
            conn.close()
            if result:
                status = result[0]
                if status == "checked_in":
                    dispatcher.utter_message(text=f"Booking {booking_ref} is checked in. You're all set!")
                elif status == "confirmed":
                    dispatcher.utter_message(text=f"Booking {booking_ref} is confirmed but not yet checked in. Online check-in opens 36 hours before departure.")
                else:
                    dispatcher.utter_message(text=f"Booking {booking_ref} status is: {status}.")
            else:
                dispatcher.utter_message(text=f"No booking found with reference {booking_ref}.")
        except Exception as e:
            dispatcher.utter_message(text="I couldn't retrieve your check-in status right now.")
        return []