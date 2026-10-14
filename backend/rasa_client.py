"""Thin client for the Rasa server's REST channel and HTTP API."""
from typing import List, Optional

import httpx

from backend.config import RASA_TIMEOUT_SECONDS, RASA_URL


class RasaUnavailableError(Exception):
    """Raised when the Rasa server cannot be reached or returns an error."""


def send_message(sender_id: str, message: str) -> List[dict]:
    """Send a user message through the REST channel and return the bot's replies."""
    try:
        response = httpx.post(
            f"{RASA_URL}/webhooks/rest/webhook",
            json={"sender": sender_id, "message": message},
            timeout=RASA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise RasaUnavailableError(str(error)) from error


def latest_intent(sender_id: str) -> Optional[str]:
    """Intent of the most recent user message, used for conversation logging."""
    try:
        response = httpx.get(
            f"{RASA_URL}/conversations/{sender_id}/tracker",
            params={"include_events": "NONE"},
            timeout=5,
        )
        response.raise_for_status()
        return response.json().get("latest_message", {}).get("intent", {}).get("name")
    except (httpx.HTTPError, ValueError):
        return None


def is_healthy() -> bool:
    try:
        return httpx.get(f"{RASA_URL}/status", timeout=5).status_code == 200
    except httpx.HTTPError:
        return False
