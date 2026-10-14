"""Conversation logging to the conversations table (FR-07).

Logging must never break a chat, so callers treat failures as non-fatal.
"""
from typing import Optional

import psycopg2

from backend.config import DB_SETTINGS


def _execute(sql: str, params: tuple) -> None:
    conn = psycopg2.connect(**DB_SETTINGS)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, params)
    finally:
        conn.close()


def record_turn(sender_id: str, intent: Optional[str]) -> None:
    """Create the conversation on its first turn, then count turns and track the last intent."""
    _execute(
        """INSERT INTO conversations (sender_id, turn_count, last_intent)
           VALUES (%s, 1, %s)
           ON CONFLICT (sender_id) DO UPDATE
           SET turn_count = conversations.turn_count + 1,
               last_intent = EXCLUDED.last_intent""",
        (sender_id, intent),
    )


def close_conversation(sender_id: str) -> None:
    """Mark a conversation closed unless it was escalated to an agent."""
    _execute(
        """UPDATE conversations
           SET status = CASE WHEN status = 'escalated' THEN status ELSE 'closed' END,
               end_time = NOW()
           WHERE sender_id = %s""",
        (sender_id,),
    )


def check_database() -> None:
    _execute("SELECT 1", ())
