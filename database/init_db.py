"""Create the airline_db tables and load sample data.

Usage (from the project root, with the venv active):
    python database/init_db.py            # schema + seed data + demo passwords
    python database/init_db.py --no-seed  # schema only

Connection settings are read from .env (see .env.example). Demo account
passwords default to the values below and can be overridden with the
DEMO_PASSWORD and DEMO_ADMIN_PASSWORD environment variables.
"""
import argparse
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

DB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DB_DIR.parent))
load_dotenv(DB_DIR.parent / ".env")

from backend.security import hash_password  # noqa: E402  (needs the project root on sys.path)

DEFAULT_PASSENGER_PASSWORD = "Passenger@2026"
DEFAULT_ADMIN_PASSWORD = "Admin@2026"


def connect(dbname=None):
    return psycopg2.connect(
        dbname=dbname or os.getenv("DB_NAME", "airline_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )


def run_sql_file(conn, filename):
    sql = (DB_DIR / filename).read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    print(f"Applied {filename}")


def set_demo_passwords(conn):
    passenger = hash_password(os.getenv("DEMO_PASSWORD", DEFAULT_PASSENGER_PASSWORD))
    admin = hash_password(os.getenv("DEMO_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD))
    with conn.cursor() as cur:
        # Every demo passenger shares one hash; acceptable for sample data only
        cur.execute("UPDATE users SET password_hash = %s WHERE role = 'passenger'", (passenger,))
        cur.execute("UPDATE users SET password_hash = %s WHERE role = 'admin'", (admin,))
    print("Set demo account passwords")


def initialise(dbname=None, seed=True):
    conn = connect(dbname)
    try:
        with conn:
            run_sql_file(conn, "schema.sql")
            if seed:
                run_sql_file(conn, "seed.sql")
                set_demo_passwords(conn)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-seed", action="store_true", help="create tables without sample data")
    args = parser.parse_args()
    initialise(seed=not args.no_seed)


if __name__ == "__main__":
    main()
