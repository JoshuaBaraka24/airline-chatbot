"""PostgreSQL access for the custom action server.

Connection settings come from environment variables (loaded from .env),
so no credentials are stored in source code.
"""
import logging
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)


def _config():
    return {
        "dbname": os.getenv("DB_NAME", "airline_db"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "connect_timeout": 5,
    }


@contextmanager
def get_cursor():
    """Yield a dict cursor; commit on success, roll back on error, always close."""
    conn = psycopg2.connect(**_config())
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
    finally:
        conn.close()
