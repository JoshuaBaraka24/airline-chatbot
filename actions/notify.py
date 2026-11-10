"""Booking confirmation emails, sent through an SMTP server (FR-03).

Settings come from environment variables (see .env.example). A failure to send never
affects the booking: send_email returns False, so the assistant can tell the passenger.
"""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

from actions.parsing import format_datetime

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 10
SMTPS_PORT = 465
# Addresses in the seed data and tests look real but are not ours, so they are never mailed
SAMPLE_DOMAINS = {"email.com", "example.com", "kq-demo.local"}

PROTOTYPE_NOTICE = (
    "This message comes from a student prototype of the Kenya Airways Virtual Assistant "
    "(Strathmore University, ICS Project II). Flights and bookings are sample data, so this is not a ticket."
)
HEADLINES = {
    "booked": "Your booking is confirmed.",
    "changed": "Your booking has been changed.",
    "cancelled": "Your booking has been cancelled. Any refund will be processed within 7 business days.",
    "checked_in": "You're checked in. Show your booking reference and your passport or ID at the airport.",
}


def _recipient(address):
    """Where a message goes: EMAIL_REDIRECT_TO if set (demos), else the address unless it is sample data."""
    redirect = os.getenv("EMAIL_REDIRECT_TO")
    if redirect:
        return redirect
    return None if address.rsplit("@", 1)[-1].lower() in SAMPLE_DOMAINS else address


def _connect(host):
    port = int(os.getenv("SMTP_PORT", "587"))
    if port == SMTPS_PORT:
        return smtplib.SMTP_SSL(host, port, timeout=SMTP_TIMEOUT_SECONDS, context=ssl.create_default_context())
    server = smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_SECONDS)
    if os.getenv("SMTP_STARTTLS", "true").lower() == "true":
        server.starttls(context=ssl.create_default_context())
    return server


def send_email(to, subject, body):
    """Sends a plain-text email. Returns True only if the SMTP server accepted it."""
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    sender = os.getenv("SMTP_FROM") or user
    recipient = _recipient(to)
    if not host or not sender or not recipient:
        return False
    try:
        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        with _connect(host) as server:
            if user:
                server.login(user, os.getenv("SMTP_PASSWORD", ""))
            server.send_message(message)
    except (OSError, ValueError, smtplib.SMTPException):
        logger.exception("Could not send the email: %s", subject)
        return False
    return True


def send_booking_email(kind, booking):
    """Tells the account holder that a booking was booked, changed or cancelled."""
    ref = booking["booking_ref"]
    body = "\n".join([
        f"Dear {booking['passenger_name']},",
        "",
        HEADLINES[kind],
        "",
        f"Booking reference: {ref}",
        f"Flight: {booking['flight_number']} {booking['origin']} to {booking['destination']}",
        f"Departs: {format_datetime(booking['departure_time'])}",
        f"Arrives: {format_datetime(booking['arrival_time'])}",
        f"Passenger: {booking['passenger_name']}",
        "",
        PROTOTYPE_NOTICE,
    ])
    return send_email(booking["account_email"], f"[Prototype] Booking {ref}: {kind}", body)
