"""Conversation logging to the conversations table (FR-07).

Logging must never break a chat, so callers treat failures as non-fatal.
"""
from typing import List, Optional

from backend.db import get_cursor


def record_turn(sender_id: str, intent: Optional[str], user_id: Optional[int] = None) -> None:
    """Create the conversation on its first turn, then count turns and track the last intent.

    A conversation becomes linked to a passenger as soon as they chat while logged in.
    """
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO conversations (sender_id, turn_count, last_intent, user_id)
               VALUES (%s, 1, %s, %s)
               ON CONFLICT (sender_id) DO UPDATE
               SET turn_count = conversations.turn_count + 1,
                   last_intent = EXCLUDED.last_intent,
                   user_id = COALESCE(EXCLUDED.user_id, conversations.user_id)""",
            (sender_id, intent, user_id),
        )


def close_conversation(sender_id: str) -> None:
    """Mark a conversation closed unless it was escalated to an agent."""
    with get_cursor() as cur:
        cur.execute(
            """UPDATE conversations
               SET status = CASE WHEN status = 'escalated' THEN status ELSE 'closed' END,
                   end_time = NOW()
               WHERE sender_id = %s""",
            (sender_id,),
        )


def check_database() -> None:
    with get_cursor() as cur:
        cur.execute("SELECT 1")


# ---------- admin dashboard (FR-06) ----------

def list_conversations(status: Optional[str] = None, limit: int = 50) -> List[dict]:
    with get_cursor() as cur:
        cur.execute(
            """SELECT c.conversation_id, c.sender_id, c.start_time, c.end_time, c.turn_count,
                      c.last_intent, c.status, u.name AS passenger_name, u.email AS passenger_email
               FROM conversations c LEFT JOIN users u USING (user_id)
               WHERE %(status)s IS NULL OR c.status = %(status)s
               ORDER BY c.start_time DESC
               LIMIT %(limit)s""",
            {"status": status, "limit": limit},
        )
        return cur.fetchall()


def resolve_conversation(conversation_id: int) -> bool:
    """Close an escalated conversation once an agent has handled it."""
    with get_cursor() as cur:
        cur.execute(
            """UPDATE conversations SET status = 'closed', end_time = COALESCE(end_time, NOW())
               WHERE conversation_id = %s AND status = 'escalated'
               RETURNING conversation_id""",
            (conversation_id,),
        )
        return cur.fetchone() is not None


def get_conversation(conversation_id: int) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM conversations WHERE conversation_id = %s", (conversation_id,))
        return cur.fetchone()


def dashboard_stats() -> dict:
    with get_cursor() as cur:
        cur.execute(
            """SELECT COUNT(*) AS total,
                      COUNT(*) FILTER (WHERE status = 'active') AS active,
                      COUNT(*) FILTER (WHERE status = 'escalated') AS escalated,
                      COUNT(*) FILTER (WHERE status = 'closed') AS closed,
                      COUNT(*) FILTER (WHERE start_time::date = CURRENT_DATE) AS today,
                      COALESCE(ROUND(AVG(turn_count), 1), 0) AS avg_turns
               FROM conversations"""
        )
        stats = dict(cur.fetchone())
        cur.execute(
            """SELECT last_intent AS intent, COUNT(*) AS count FROM conversations
               WHERE last_intent IS NOT NULL
               GROUP BY last_intent ORDER BY count DESC, intent LIMIT 6"""
        )
        stats["top_intents"] = cur.fetchall()
        cur.execute("SELECT status, COUNT(*) AS count FROM bookings GROUP BY status ORDER BY status")
        stats["bookings"] = {row["status"]: row["count"] for row in cur.fetchall()}
        stats["avg_turns"] = float(stats["avg_turns"])
        return stats
