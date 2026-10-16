"""Unit tests for the FastAPI gateway. Rasa and the database are stubbed out."""
import pytest
from fastapi.testclient import TestClient

from backend import conversation_log, main, rasa_client

SENDER = "123e4567-e89b-42d3-a456-426614174000"


@pytest.fixture
def calls(monkeypatch):
    """Stub Rasa and the conversation log, recording what the API sends them."""
    recorded = {"sent": [], "turns": [], "closed": []}

    def fake_send(sender_id, message, metadata=None):
        recorded["sent"].append((sender_id, message))
        recorded["metadata"] = metadata
        return [
            {"recipient_id": sender_id, "text": "Please provide your flight number (e.g. KQ101)."},
            {"recipient_id": sender_id, "text": "Choose one", "buttons": [{"title": "Yes", "payload": "/affirm"}]},
            {"recipient_id": sender_id, "image": "ignored.png"},
        ]

    monkeypatch.setattr(rasa_client, "send_message", fake_send)
    monkeypatch.setattr(rasa_client, "latest_intent", lambda sender_id: "check_flight_status")
    monkeypatch.setattr(rasa_client, "is_healthy", lambda: True)
    monkeypatch.setattr(conversation_log, "record_turn", lambda s, i, u=None: recorded["turns"].append((s, i)))
    monkeypatch.setattr(conversation_log, "close_conversation", lambda s: recorded["closed"].append(s))
    monkeypatch.setattr(conversation_log, "check_database", lambda: None)
    return recorded


@pytest.fixture
def client():
    return TestClient(main.app)


def test_first_message_issues_session_id_and_returns_replies(client, calls):
    response = client.post("/api/chat", json={"message": "  is my flight delayed?  "})

    assert response.status_code == 200
    body = response.json()
    assert len(body["sender_id"]) == 36
    assert [m["text"] for m in body["messages"]] == ["Please provide your flight number (e.g. KQ101).", "Choose one"]
    assert body["messages"][1]["buttons"] == [{"title": "Yes", "payload": "/affirm"}]
    assert body["response_time_ms"] >= 0
    assert calls["sent"] == [(body["sender_id"], "is my flight delayed?")]
    assert calls["turns"] == [(body["sender_id"], "check_flight_status")]


def test_existing_session_id_is_reused(client, calls):
    response = client.post("/api/chat", json={"message": "KQ101", "sender_id": SENDER})

    assert response.json()["sender_id"] == SENDER
    assert calls["sent"] == [(SENDER, "KQ101")]


@pytest.mark.parametrize("payload", [
    {"message": ""},
    {"message": "   "},
    {"message": "x" * 501},
    {"message": "hi", "sender_id": "not-a-uuid"},
    {},
])
def test_invalid_requests_are_rejected(client, calls, payload):
    assert client.post("/api/chat", json=payload).status_code == 422
    assert calls["sent"] == []


def test_rasa_outage_returns_503(client, calls, monkeypatch):
    def unavailable(sender_id, message, metadata=None):
        raise rasa_client.RasaUnavailableError("connection refused")

    monkeypatch.setattr(rasa_client, "send_message", unavailable)
    response = client.post("/api/chat", json={"message": "hello"})

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]


def test_logging_failure_does_not_break_chat(client, calls, monkeypatch):
    def broken_log(sender_id, intent, user_id=None):
        raise RuntimeError("database down")

    monkeypatch.setattr(conversation_log, "record_turn", broken_log)
    assert client.post("/api/chat", json={"message": "hello"}).status_code == 200


def test_end_chat_closes_conversation(client, calls):
    assert client.post(f"/api/chat/{SENDER}/end").status_code == 204
    assert calls["closed"] == [SENDER]


def test_end_chat_rejects_invalid_session_id(client, calls):
    assert client.post("/api/chat/abc/end").status_code == 422


def test_health_reports_components(client, calls, monkeypatch):
    assert client.get("/api/health").json() == {"status": "ok", "rasa": "up", "database": "up"}

    monkeypatch.setattr(rasa_client, "is_healthy", lambda: False)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["rasa"] == "down"


def test_widget_is_served_with_security_headers(client):
    response = client.get("/")

    assert response.status_code == 200
    assert '<script src="chat.js"></script>' in response.text
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    for asset in ("/chat.js", "/voice.js", "/styles.css", "/site.css", "/site.js", "/api.js"):
        assert client.get(asset).status_code == 200


@pytest.mark.parametrize("page, script", [
    ("/login.html", "login.js"),
    ("/account.html", "account.js"),
    ("/admin.html", "admin.js"),
])
def test_portal_pages_are_served(client, page, script):
    response = client.get(page)

    assert response.status_code == 200
    assert f'<script src="{script}"></script>' in response.text
    assert client.get(f"/{script}").status_code == 200


def test_api_routes_take_precedence_over_static_files(client, calls):
    assert client.get("/api/health").json()["status"] == "ok"


def test_api_docs_are_not_restricted_by_widget_csp(client):
    response = client.get("/docs")

    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
