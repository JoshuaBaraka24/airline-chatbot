"""Fixtures shared by the unit and integration tests."""
import pytest

from backend import main


@pytest.fixture(autouse=True)
def fresh_chat_limits():
    """Chat limits are kept in memory, so one test's messages must not count against the next."""
    for limit in (main.conversation_limit, main.address_minute_limit, main.address_hour_limit):
        limit.clear()
