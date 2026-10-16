"""Custom actions that read the logged-in passenger from message metadata."""
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions.forms import ActionAskBookingReference


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
