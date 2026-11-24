"""Sliding-window limits, and the chat message limits built on them."""
import pytest
from fastapi.testclient import TestClient

from backend import conversation_log, main, rasa_client, throttle
from backend.throttle import Throttle

SENDER = "123e4567-e89b-42d3-a456-426614174000"


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(throttle.time, "monotonic", lambda: now[0])
    return now


def test_blocks_after_the_limit_and_recovers(clock):
    limit = Throttle(2, 60)
    limit.record("a")
    clock[0] += 10
    assert not limit.is_blocked("a")
    limit.record("a")
    assert limit.retry_after("a") == 50 and not limit.is_blocked("b")
    clock[0] += 50
    assert not limit.is_blocked("a")


def test_zero_switches_a_limit_off():
    limit = Throttle(0, 60)
    for _ in range(100):
        limit.record("a")
    assert not limit.is_blocked("a")


def test_idle_keys_are_forgotten(clock, monkeypatch):
    monkeypatch.setattr(throttle, "MAX_KEYS", 3)
    limit = Throttle(5, 60)
    for key in "abc":
        limit.record(key)
    clock[0] += 61
    limit.record("d")
    assert set(limit._events) == {"d"}


# --- chat ---

@pytest.fixture
def sent(monkeypatch):
    messages = []
    monkeypatch.setattr(rasa_client, "send_message", lambda s, m, metadata=None: messages.append(m) or [{"text": "ok"}])
    monkeypatch.setattr(rasa_client, "latest_intent", lambda s: "greet")
    monkeypatch.setattr(conversation_log, "record_turn", lambda *a: None)
    return messages


class AddressClient:
    """A test client whose requests come from a chosen network address."""

    def __init__(self, address="203.0.113.5"):
        async def app(scope, receive, send):
            if scope["type"] == "http":
                scope["client"] = (address, 1234)
            await main.app(scope, receive, send)
        self.http = TestClient(app)

    def say(self, sender=None):
        body = {"message": "hello", **({"sender_id": sender} if sender else {})}
        return self.http.post("/api/chat", json=body)


def test_a_conversation_is_limited_to_20_messages_a_minute(sent, clock):
    visitor = AddressClient()
    assert [visitor.say(SENDER).status_code for _ in range(20)] == [200] * 20
    refused = visitor.say(SENDER)
    assert refused.status_code == 429 and refused.headers["Retry-After"] == "60"
    assert len(sent) == 20  # the assistant never sees a refused message
    clock[0] += 60
    assert visitor.say(SENDER).status_code == 200


def test_new_conversations_do_not_avoid_the_address_limit(sent, clock):
    visitor = AddressClient()
    assert [visitor.say().status_code for _ in range(61)] == [200] * 60 + [429]
    assert AddressClient("203.0.113.9").say().status_code == 200  # someone else is not affected


def test_an_address_is_limited_to_600_messages_an_hour(sent, clock):
    visitor = AddressClient()
    for _ in range(10):
        assert {visitor.say().status_code for _ in range(60)} == {200}
        clock[0] += 61
    refused = visitor.say()
    assert refused.status_code == 429 and int(refused.headers["Retry-After"]) > 2500


def test_waiting_is_enough_however_often_it_was_refused(sent, clock):
    visitor = AddressClient()
    for _ in range(50):
        visitor.say(SENDER)
    clock[0] += 60
    assert visitor.say(SENDER).status_code == 200
