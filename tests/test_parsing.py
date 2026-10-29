from datetime import date, datetime

import pytest

from actions.parsing import (
    format_date,
    format_datetime,
    is_explicit_yes,
    match_city,
    normalize_booking_ref,
    normalize_email,
    normalize_flight_number,
    normalize_person_name,
    parse_date,
    parse_option_number,
)

TODAY = date(2026, 10, 14)  # a Wednesday


@pytest.mark.parametrize("text, expected", [
    ("KQ101", "KQ101"),
    ("kq 202", "KQ202"),
    ("my flight is Kq-305 thanks", "KQ305"),
    ("flight 101", None),
    ("", None),
    (None, None),
])
def test_normalize_flight_number(text, expected):
    assert normalize_flight_number(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("BK001", "BK001"),
    ("bk 004", "BK004"),
    ("the reference is bk-006", "BK006"),
    ("booking 001", None),
    (None, None),
])
def test_normalize_booking_ref(text, expected):
    assert normalize_booking_ref(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("2026-10-20", date(2026, 10, 20)),
    ("20/10/2026", date(2026, 10, 20)),
    ("20.10.26", date(2026, 10, 20)),
    ("20 October", date(2026, 10, 20)),
    ("the 20th of October 2026", date(2026, 10, 20)),
    ("October 28th", date(2026, 10, 28)),
    ("oct 28", date(2026, 10, 28)),
    ("Sept 3", date(2027, 9, 3)),           # already passed this year -> next year
    ("today", TODAY),
    ("tomorrow please", date(2026, 10, 15)),
    ("the day after tomorrow", date(2026, 10, 16)),
    ("Friday", date(2026, 10, 16)),
    ("next fri", date(2026, 10, 16)),
    ("on Wednesday", date(2026, 10, 21)),   # same weekday -> following week
    ("the 27th", date(2026, 10, 27)),
    ("the 5th", date(2026, 11, 5)),         # already passed this month -> next month
])
def test_parse_date(text, expected):
    assert parse_date(text, today=TODAY) == expected


@pytest.mark.parametrize("text", [
    "next week",
    "my friend is travelling",              # 'fri' inside a word is not a weekday
    "I have money",                         # 'mon' inside a word is not a weekday
    "31/02/2026",                           # invalid calendar date
    "",
    None,
])
def test_parse_date_rejects(text):
    assert parse_date(text, today=TODAY) is None


def test_match_city_prefers_longest_and_ignores_case():
    cities = ["Nairobi", "Mombasa", "Cape Town", "Cape"]
    assert match_city("flying from nairobi", cities) == "Nairobi"
    assert match_city("to Cape Town please", cities) == "Cape Town"
    assert match_city("Kampala", cities) is None
    assert match_city(None, cities) is None


def test_formatting():
    assert format_datetime(datetime(2026, 10, 20, 8, 0)) == "Tue 20 Oct 2026 at 08:00"
    assert format_date(date(2026, 10, 20)) == "Tue 20 Oct 2026"


@pytest.mark.parametrize("text, expected", [
    ("Brian Otieno", "Brian Otieno"),
    ("my name is jane wambui", "Jane Wambui"),
    ("I'm John McDonald", "John McDonald"),
    ("it's Amina Hassan.", "Amina Hassan"),
    ("O'Brien Mary-Jane", "O'Brien Mary-Jane"),
    ("Jane", None),                         # a last name is needed too
    ("kq101 yes", None),
    ("1234 5678", None),
    (None, None),
])
def test_normalize_person_name(text, expected):
    assert normalize_person_name(text) == expected


def test_normalize_email():
    assert normalize_email("Jane.W@Gmail.com") == "jane.w@gmail.com"
    assert normalize_email("my email is a@b.co.ke") == "a@b.co.ke"
    assert normalize_email("jane at gmail") is None


@pytest.mark.parametrize("text, expected", [
    ("1", 0), ("option 2", 1), ("the second one", 1), ("first", 0), ("the last one", 2),
    ("4", None),                            # only three options
    ("KQ101", None),                        # a flight number, not an option number
    ("the 8am one", None),
])
def test_parse_option_number(text, expected):
    assert parse_option_number(text, 3) == expected


@pytest.mark.parametrize("text", ["yes", "Yes, do it", "go ahead", "sure thing", "of course", "ndio", "ok book it"])
def test_explicit_yes(text):
    assert is_explicit_yes(text)


@pytest.mark.parametrize("text", ["erm", "uhh", "blah", "mmm", "", None])
def test_hesitation_is_not_a_yes(text):
    assert not is_explicit_yes(text)
