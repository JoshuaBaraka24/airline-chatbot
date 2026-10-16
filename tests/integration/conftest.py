"""Integration-test fixtures backed by a dedicated PostgreSQL database.

The database named by TEST_DB_NAME (default airline_db_test) is created if
missing and rebuilt from schema.sql + seed.sql before every test, so tests
never touch the demo data in airline_db. Tests are skipped when PostgreSQL
is not reachable.
"""
import os

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2 import sql

from backend import auth, config, rasa_client
from database import init_db

TEST_DB = os.getenv("TEST_DB_NAME", "airline_db_test")
PASSENGER_PASSWORD = init_db.DEFAULT_PASSENGER_PASSWORD
ADMIN_PASSWORD = init_db.DEFAULT_ADMIN_PASSWORD


def _ensure_database():
    conn = init_db.connect("postgres")
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
            if not cur.fetchone():
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB)))
    finally:
        conn.close()


@pytest.fixture(scope="session")
def test_database():
    try:
        _ensure_database()
    except psycopg2.OperationalError as error:
        pytest.skip(f"PostgreSQL not available: {error}")
    return TEST_DB


@pytest.fixture
def db(test_database, monkeypatch):
    """Fresh seeded test database, used by both the gateway and the action server code."""
    os.environ.pop("DEMO_PASSWORD", None)
    os.environ.pop("DEMO_ADMIN_PASSWORD", None)
    init_db.initialise(dbname=test_database)
    monkeypatch.setitem(config.DB_SETTINGS, "dbname", test_database)  # backend
    monkeypatch.setenv("DB_NAME", test_database)                      # actions/db.py
    auth.login_throttle._failures.clear()
    return test_database


@pytest.fixture
def client(db):
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def fake_rasa(monkeypatch):
    """Stub the Rasa server and record what the gateway sends it."""
    sent = []

    def send_message(sender_id, message, metadata=None):
        sent.append({"sender_id": sender_id, "message": message, "metadata": metadata})
        return [{"recipient_id": sender_id, "text": "ok"}]

    monkeypatch.setattr(rasa_client, "send_message", send_message)
    monkeypatch.setattr(rasa_client, "latest_intent", lambda sender_id: "greet")
    return sent


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.fixture
def passenger(client):
    """Client logged in as John Mwangi (booking BK001)."""
    assert login(client, "john@email.com", PASSENGER_PASSWORD).status_code == 200
    return client


@pytest.fixture
def admin(client):
    assert login(client, "admin@kq-demo.local", ADMIN_PASSWORD).status_code == 200
    return client
