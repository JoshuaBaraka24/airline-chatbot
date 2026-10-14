"""Create the airline_db tables and load sample data.

Usage (from the project root, with the venv active):
    python database/init_db.py            # schema + seed data
    python database/init_db.py --no-seed  # schema only

Connection settings are read from .env (see .env.example).
"""
import argparse
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

DB_DIR = Path(__file__).resolve().parent
load_dotenv(DB_DIR.parent / ".env")


def connect():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "airline_db"),
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


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-seed", action="store_true", help="create tables without sample data")
    args = parser.parse_args()

    conn = connect()
    try:
        with conn:
            run_sql_file(conn, "schema.sql")
            if not args.no_seed:
                run_sql_file(conn, "seed.sql")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
