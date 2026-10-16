from backend import conversation_log
from backend.db import get_cursor

from .conftest import login


def test_my_bookings_requires_login(client):
    assert client.get("/api/me/bookings").status_code == 401


def test_passenger_sees_only_their_own_bookings(passenger):
    bookings = passenger.get("/api/me/bookings").json()

    assert [b["booking_ref"] for b in bookings] == ["BK001"]
    assert bookings[0]["flight"]["flight_number"] == "KQ101"
    assert bookings[0]["flight"]["origin"] == "Nairobi"


def test_flight_status_search(client):
    flights = client.get("/api/flights/status", params={"flight_number": "kq 202"}).json()

    assert [f["flight_number"] for f in flights] == ["KQ202", "KQ202"]
    assert flights[0]["status"] == "delayed"
    assert client.get("/api/flights/status", params={"flight_number": "KQ999"}).status_code == 404
    assert client.get("/api/flights/status", params={"flight_number": "drop table"}).status_code == 422


def test_chat_tells_the_assistant_who_is_logged_in(passenger, fake_rasa):
    response = passenger.post("/api/chat", json={"message": "cancel my booking"})

    assert response.status_code == 200
    assert fake_rasa[0]["metadata"] == {"user_id": 1, "name": "John Mwangi"}
    with get_cursor() as cur:
        cur.execute("SELECT user_id, turn_count FROM conversations WHERE sender_id = %s", (response.json()["sender_id"],))
        assert dict(cur.fetchone()) == {"user_id": 1, "turn_count": 1}


def test_anonymous_chat_sends_no_identity(client, fake_rasa):
    client.post("/api/chat", json={"message": "hello"})
    assert fake_rasa[0]["metadata"] is None


def test_admin_endpoints_reject_anonymous_users_and_passengers(client):
    assert client.get("/api/admin/stats").status_code == 401
    login(client, "john@email.com", "Passenger@2026")
    assert client.get("/api/admin/stats").status_code == 403
    assert client.get("/api/admin/conversations").status_code == 403


def test_admin_dashboard_statistics_and_filtering(admin):
    conversation_log.record_turn("11111111-1111-4111-8111-111111111111", "greet", 1)
    conversation_log.record_turn("11111111-1111-4111-8111-111111111111", "cancel_booking", 1)
    conversation_log.record_turn("22222222-2222-4222-8222-222222222222", "escalate_to_agent")
    with get_cursor() as cur:
        cur.execute("UPDATE conversations SET status = 'escalated' WHERE sender_id LIKE '2222%'")

    stats = admin.get("/api/admin/stats").json()
    assert (stats["total"], stats["active"], stats["escalated"]) == (2, 1, 1)
    assert stats["avg_turns"] == 1.5
    assert stats["bookings"] == {"cancelled": 1, "checked_in": 1, "confirmed": 4}

    escalated = admin.get("/api/admin/conversations", params={"status": "escalated"}).json()
    assert [c["sender_id"][:4] for c in escalated] == ["2222"]
    everyone = admin.get("/api/admin/conversations").json()
    assert {c["passenger_name"] for c in everyone} == {"John Mwangi", None}
    assert admin.get("/api/admin/conversations", params={"status": "bogus"}).status_code == 422


def test_admin_resolves_only_escalated_conversations(admin):
    conversation_log.record_turn("33333333-3333-4333-8333-333333333333", "escalate_to_agent")
    conversation_log.record_turn("44444444-4444-4444-8444-444444444444", "greet")
    with get_cursor() as cur:
        cur.execute("UPDATE conversations SET status = 'escalated' WHERE sender_id LIKE '3333%'")
        cur.execute("SELECT conversation_id, sender_id FROM conversations ORDER BY conversation_id")
        escalated_id, active_id = [row["conversation_id"] for row in cur.fetchall()]

    assert admin.post(f"/api/admin/conversations/{escalated_id}/resolve").status_code == 204
    assert admin.post(f"/api/admin/conversations/{escalated_id}/resolve").status_code == 409
    assert admin.post(f"/api/admin/conversations/{active_id}/resolve").status_code == 409
    assert conversation_log.get_conversation(escalated_id)["status"] == "closed"


def test_transcript_of_unknown_conversation_is_404(admin):
    assert admin.get("/api/admin/conversations/999/transcript").status_code == 404
