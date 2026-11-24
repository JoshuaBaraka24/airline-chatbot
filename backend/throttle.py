"""Counts recent events per key in memory, to slow down guessing and flooding (NFR-06).

Kept free of web and database imports because the gateway and the action server both use it.
"""
import math
import threading
import time
from collections import deque
from typing import Deque, Dict

MAX_KEYS = 10_000


class Throttle:
    """Blocks a key after max_events in a sliding window. max_events of 0 switches it off."""

    def __init__(self, max_events: int, window_seconds: int):
        self.max_events = max_events
        self.window = window_seconds
        self._events: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> Deque[float]:
        events = self._events.get(key, deque())
        while events and events[0] <= now - self.window:
            events.popleft()
        return events

    def retry_after(self, key: str) -> int:
        """Seconds until the key may act again; 0 if it may act now."""
        if not self.max_events:
            return 0
        now = time.monotonic()
        with self._lock:
            events = self._recent(key, now)
            if len(events) < self.max_events:
                return 0
            return max(1, math.ceil(events[0] + self.window - now))

    def is_blocked(self, key: str) -> bool:
        return self.retry_after(key) > 0

    def record(self, key: str) -> None:
        if not self.max_events:
            return
        now = time.monotonic()
        with self._lock:
            if key not in self._events and len(self._events) >= MAX_KEYS:
                self._forget_idle_keys(now)
            events = self._recent(key, now)
            events.append(now)
            self._events[key] = events

    def _forget_idle_keys(self, now: float) -> None:
        self._events = {k: e for k, e in self._events.items() if e and e[-1] > now - self.window}

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
