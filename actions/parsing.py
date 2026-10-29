"""Pure helpers for normalising user input captured by the dialogue forms.

These functions have no Rasa or database dependencies so they can be
unit-tested in isolation (see tests/test_parsing.py).
"""
import re
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

FLIGHT_NUMBER_RE = re.compile(r"\bkq\s?-?(\d{2,4})\b", re.IGNORECASE)
BOOKING_REF_RE = re.compile(r"\bbk\s?-?(\d{3})\b", re.IGNORECASE)

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

_MONTH = (r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
          r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\.?")
_ORD = r"(?:st|nd|rd|th)?"
ISO_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
NUMERIC_RE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})\b")  # day-first
DAY_MONTH_RE = re.compile(rf"\b(\d{{1,2}}){_ORD}\s+(?:of\s+)?{_MONTH}(?:,?\s+(\d{{4}}))?", re.IGNORECASE)
MONTH_DAY_RE = re.compile(rf"\b{_MONTH}\s+(\d{{1,2}}){_ORD}(?:,?\s+(\d{{4}}))?\b", re.IGNORECASE)
WEEKDAY_RE = re.compile(
    r"\b(mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:r(?:s(?:day)?)?)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b",
    re.IGNORECASE,
)
ORDINAL_DAY_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.IGNORECASE)


def normalize_flight_number(text: Optional[str]) -> Optional[str]:
    """'kq 101' -> 'KQ101'; returns None if no flight number is present."""
    if not text:
        return None
    match = FLIGHT_NUMBER_RE.search(text)
    return f"KQ{match.group(1)}" if match else None


def normalize_booking_ref(text: Optional[str]) -> Optional[str]:
    """'bk-001' -> 'BK001'; returns None if no booking reference is present."""
    if not text:
        return None
    match = BOOKING_REF_RE.search(text)
    return f"BK{match.group(1)}" if match else None


def match_city(text: Optional[str], cities: Iterable[str]) -> Optional[str]:
    """Return the known city mentioned in text (case-insensitive), preferring the longest match."""
    if not text:
        return None
    lowered = text.lower()
    for city in sorted(cities, key=len, reverse=True):
        if re.search(rf"\b{re.escape(city.lower())}\b", lowered):
            return city
    return None


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _roll_forward(year: Optional[int], month: int, day: int, today: date) -> Optional[date]:
    """Build a date; if no year was given and the date has passed, assume next year."""
    if year is not None:
        return _safe_date(year, month, day)
    candidate = _safe_date(today.year, month, day)
    if candidate and candidate < today:
        candidate = _safe_date(today.year + 1, month, day)
    return candidate


def parse_date(text: Optional[str], today: Optional[date] = None) -> Optional[date]:
    """Parse a travel date from free text.

    Supports ISO (2026-10-20), day-first numeric (20/10/2026), '20 October',
    'October 20th', 'today', 'tomorrow', 'day after tomorrow', weekday names
    ('Friday', 'next Friday') and a bare ordinal ('the 27th').
    Returns None if no date can be understood.
    """
    if not text:
        return None
    today = today or date.today()
    lowered = text.lower()

    match = ISO_RE.search(lowered)
    if match:
        return _safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    match = NUMERIC_RE.search(lowered)
    if match:
        year = int(match.group(3))
        year = year + 2000 if year < 100 else year
        return _safe_date(year, int(match.group(2)), int(match.group(1)))

    match = DAY_MONTH_RE.search(lowered)
    if match:
        year = int(match.group(3)) if match.group(3) else None
        return _roll_forward(year, MONTHS[match.group(2)[:3]], int(match.group(1)), today)

    match = MONTH_DAY_RE.search(lowered)
    if match:
        year = int(match.group(3)) if match.group(3) else None
        return _roll_forward(year, MONTHS[match.group(1)[:3]], int(match.group(2)), today)

    if "day after tomorrow" in lowered:
        return today + timedelta(days=2)
    if "tomorrow" in lowered:
        return today + timedelta(days=1)
    if "today" in lowered or "tonight" in lowered:
        return today

    match = WEEKDAY_RE.search(lowered)
    if match:
        target = [w[:3] for w in WEEKDAYS].index(match.group(1)[:3])
        days_ahead = (target - today.weekday()) % 7 or 7
        return today + timedelta(days=days_ahead)

    match = ORDINAL_DAY_RE.search(lowered)
    if match:
        day = int(match.group(1))
        candidate = _safe_date(today.year, today.month, day)
        if candidate and candidate >= today:
            return candidate
        next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        return _safe_date(next_month.year, next_month.month, day)

    return None


def format_datetime(value: datetime) -> str:
    """e.g. 'Tue 20 Oct 2026 at 08:00'"""
    return f"{value:%a %d %b %Y} at {value:%H:%M}"


def format_date(value: date) -> str:
    """e.g. 'Tue 20 Oct 2026'"""
    return f"{value:%a %d %b %Y}"


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
NAME_PREFIX_RE = re.compile(r"^\s*(?:(?:my|the passenger'?s?|his|her|their)\s+(?:full\s+)?name\s+is|i\s*'?\s*a?m|it'?s|name:?)\s+",
                            re.IGNORECASE)
NAME_RE = re.compile(r"^[^\W\d_][^\W\d_'.-]*(?:['.-][^\W\d_]+)*\.?$")
ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "last": -1}
OPTION_NUMBER_RE = re.compile(r"^\D*\b(\d)\b\D*$")


def normalize_email(text: Optional[str]) -> Optional[str]:
    """Extracts an email address, lower-cased; None if there isn't one."""
    if not text:
        return None
    match = EMAIL_RE.search(text)
    return match.group(0).lower() if match else None


def normalize_person_name(text: Optional[str]) -> Optional[str]:
    """'my name is jane wambui' -> 'Jane Wambui'.

    Needs a first and last name (2-4 words of letters); returns None otherwise.
    """
    if not text:
        return None
    words = NAME_PREFIX_RE.sub("", text.strip()).rstrip(".!").split()
    if not 2 <= len(words) <= 4 or not all(NAME_RE.match(w) for w in words):
        return None
    return " ".join(w if any(c.isupper() for c in w[1:]) else w[:1].upper() + w[1:].lower() for w in words)


def parse_option_number(text: Optional[str], count: int) -> Optional[int]:
    """'the second one' / '2' -> 1 (zero-based index into a list of `count` options)."""
    if not text:
        return None
    lowered = text.lower()
    for word, number in ORDINALS.items():
        if re.search(rf"\b{word}\b", lowered):
            index = number - 1 if number > 0 else count - 1
            return index if 0 <= index < count else None
    match = OPTION_NUMBER_RE.match(lowered)
    if match and not FLIGHT_NUMBER_RE.search(lowered):
        index = int(match.group(1)) - 1
        return index if 0 <= index < count else None
    return None


# Words that make a reply an explicit "yes". Confirmations change bookings, so a
# reply the classifier labels affirm (e.g. "erm") must also contain one of these.
YES_WORDS = {
    "yes", "yeah", "yea", "yep", "yup", "ya", "y", "sure", "ok", "okay", "k", "confirm", "confirmed",
    "correct", "right", "fine", "proceed", "absolutely", "definitely", "agreed", "alright", "perfect",
    "exactly", "affirmative", "ndio", "sawa", "please", "go", "do", "works", "good", "course",
}


def is_explicit_yes(text: Optional[str]) -> bool:
    """'yes please' / 'go ahead' -> True; 'erm' / 'blah' -> False."""
    if not text:
        return False
    return any(word in YES_WORDS for word in re.findall(r"[a-z]+", text.lower()))
