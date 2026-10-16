"""PostgreSQL access for the gateway."""
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from backend.config import DB_SETTINGS


@contextmanager
def get_cursor():
    """Yield a dict cursor; commit on success, roll back on error, always close.

    DB_SETTINGS is read at call time so tests can point it at a test database.
    """
    conn = psycopg2.connect(**DB_SETTINGS)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
    finally:
        conn.close()
