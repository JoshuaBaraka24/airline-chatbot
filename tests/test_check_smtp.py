"""Tests for the start-up email port check (deploy/check_smtp.py)."""
import importlib.util
import socket
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "check_smtp", Path(__file__).resolve().parent.parent / "deploy" / "check_smtp.py"
)
check_smtp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_smtp)


@pytest.fixture
def listening_port():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    yield server.getsockname()[1]
    server.close()


def closed_port():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def test_ports_to_check_merges_and_sorts():
    assert check_smtp.ports_to_check(587, "2525, 587,") == [587, 2525]


def test_open_port_is_reachable(listening_port):
    assert check_smtp.can_connect("127.0.0.1", listening_port, timeout=1)


def test_closed_port_is_not_reachable():
    assert not check_smtp.can_connect("127.0.0.1", closed_port(), timeout=1)


def test_no_host_means_email_off(monkeypatch, capsys):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert check_smtp.main() == 0
    assert "emails are off" in capsys.readouterr().out


def test_reports_configured_port(monkeypatch, capsys, listening_port):
    blocked = closed_port()
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", str(listening_port))
    monkeypatch.setenv("SMTP_CHECK_PORTS", str(blocked))
    assert check_smtp.main() == 0
    out = capsys.readouterr().out
    assert f"127.0.0.1:{listening_port} (configured) reachable" in out
    assert f"127.0.0.1:{blocked} BLOCKED" in out


def test_fails_when_configured_port_blocked(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", str(closed_port()))
    monkeypatch.setenv("SMTP_CHECK_PORTS", "")
    assert check_smtp.main() == 1
