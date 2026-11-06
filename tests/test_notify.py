"""Confirmation emails: when they are sent, where they go, and what happens on failure."""
import smtplib
from datetime import datetime

import pytest

from actions import notify


class FakeSMTP:
    instances = []
    fail_with = None

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.tls = bool(context)
        self.logged_in = None
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self, context=None):
        self.tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, message):
        if FakeSMTP.fail_with:
            raise FakeSMTP.fail_with
        self.sent.append(message)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.instances, FakeSMTP.fail_with = [], None
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    for name, value in {"SMTP_HOST": "mail.test", "SMTP_PORT": "587", "SMTP_USER": "kq@mail.test",
                        "SMTP_PASSWORD": "secret", "SMTP_FROM": ""}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("SMTP_STARTTLS", raising=False)
    monkeypatch.delenv("EMAIL_REDIRECT_TO", raising=False)
    return FakeSMTP


def test_sends_over_tls_and_logs_in(smtp):
    assert notify.send_email("faith@safari.test", "Subject", "Body") is True

    server = smtp.instances[0]
    assert (server.host, server.port, server.tls) == ("mail.test", 587, True)
    assert server.logged_in == ("kq@mail.test", "secret")
    message = server.sent[0]
    assert (message["To"], message["From"], message["Subject"]) == ("faith@safari.test", "kq@mail.test", "Subject")


def test_port_465_uses_implicit_tls(smtp, monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "465")

    assert notify.send_email("faith@safari.test", "Subject", "Body") is True
    assert smtp.instances[0].tls is True


def test_nothing_is_sent_without_a_mail_server(smtp, monkeypatch):
    monkeypatch.delenv("SMTP_HOST")

    assert notify.send_email("faith@safari.test", "Subject", "Body") is False
    assert smtp.instances == []


@pytest.mark.parametrize("address", ["john@email.com", "JOHN@EMAIL.COM", "faith@example.com", "admin@kq-demo.local"])
def test_sample_addresses_are_never_mailed(smtp, address):
    assert notify.send_email(address, "Subject", "Body") is False
    assert smtp.instances == []


def test_redirect_sends_everything_to_one_inbox(smtp, monkeypatch):
    monkeypatch.setenv("EMAIL_REDIRECT_TO", "demo@safari.test")

    assert notify.send_email("john@email.com", "Subject", "Body") is True
    assert smtp.instances[0].sent[0]["To"] == "demo@safari.test"


@pytest.mark.parametrize("error", [smtplib.SMTPAuthenticationError(535, b"bad"), OSError("no route"), TimeoutError()])
def test_a_failure_returns_false_instead_of_raising(smtp, error):
    smtp.fail_with = error

    assert notify.send_email("faith@safari.test", "Subject", "Body") is False


def test_a_header_injection_attempt_is_refused(smtp):
    assert notify.send_email("faith@safari.test", "Subject\nBcc: everyone@safari.test", "Body") is False
    assert smtp.instances == []


def test_booking_email_contents(smtp):
    booking = {
        "booking_ref": "BK007", "passenger_name": "Faith Njeri", "account_email": "faith@safari.test",
        "flight_number": "KQ202", "origin": "Nairobi", "destination": "Dubai",
        "departure_time": datetime(2026, 11, 13, 22, 0), "arrival_time": datetime(2026, 11, 14, 3, 0),
    }

    assert notify.send_booking_email("cancelled", booking) is True

    message = smtp.instances[0].sent[0]
    body = message.get_content()
    assert message["Subject"] == "[Prototype] Booking BK007: cancelled"
    assert "has been cancelled" in body and "KQ202 Nairobi to Dubai" in body and "Fri 13 Nov 2026 at 22:00" in body
    assert "not a ticket" in body
