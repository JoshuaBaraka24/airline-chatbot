"""Backend settings, read once from environment variables / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

RASA_URL = os.getenv("RASA_URL", "http://127.0.0.1:5005").rstrip("/")
RASA_TIMEOUT_SECONDS = float(os.getenv("RASA_TIMEOUT_SECONDS", "30"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    if origin.strip()
]
MAX_MESSAGE_LENGTH = 500
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

DB_SETTINGS = {
    "dbname": os.getenv("DB_NAME", "airline_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "connect_timeout": 5,
}
