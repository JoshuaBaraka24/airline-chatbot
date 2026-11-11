"""Logs whether this host can open a connection to the SMTP server.

Some hosts, such as Hugging Face Spaces, block outgoing email ports. Running
this at start-up shows in the logs which ports are open, so a blocked port is
not mistaken for a bug in the email code.

    SMTP_HOST         email server to check (nothing is checked without it)
    SMTP_PORT         the port the system sends on (default 587)
    SMTP_CHECK_PORTS  extra ports to try for comparison (default "587,2525")

Exits with 0 when the configured port is reachable, 1 otherwise.
"""
import os
import socket
import sys

TIMEOUT_SECONDS = 5


def can_connect(host, port, timeout=TIMEOUT_SECONDS):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ports_to_check(configured, extra):
    ports = {configured}
    ports.update(int(p) for p in extra.split(",") if p.strip())
    return sorted(ports)


def main():
    host = os.getenv("SMTP_HOST")
    if not host:
        print("Email check: SMTP_HOST is not set, so confirmation emails are off.")
        return 0
    configured = int(os.getenv("SMTP_PORT", "587"))
    results = {}
    for port in ports_to_check(configured, os.getenv("SMTP_CHECK_PORTS", "587,2525")):
        results[port] = can_connect(host, port)
        state = "reachable" if results[port] else "BLOCKED or unreachable"
        marker = " (configured)" if port == configured else ""
        print(f"Email check: {host}:{port}{marker} {state}")
    return 0 if results[configured] else 1


if __name__ == "__main__":
    sys.exit(main())
