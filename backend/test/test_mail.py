"""Vérifier les destinataires et les erreurs sans envoyer d’e-mail réel."""

from unittest.mock import MagicMock
from email import message_from_string
import pytest
from api.services import mail


@pytest.fixture
def smtp(monkeypatch):
    monkeypatch.delenv("MEMORA_SMTP_CAPTURE_ONLY", raising=False)
    server = MagicMock()
    server.sendmail.return_value = {}
    connection = MagicMock()
    connection.return_value.__enter__.return_value = server
    monkeypatch.setattr(mail.smtplib, "SMTP", connection)
    return connection, server


@pytest.mark.parametrize(
    "recipients, expected",
    [
        ("alice@example.invalid", ["alice@example.invalid"]),
        (
            [" alice@example.invalid ", "bob@example.invalid", "alice@example.invalid"],
            ["alice@example.invalid", "bob@example.invalid"],
        ),
    ],
)
def test_email_recipients(smtp, recipients, expected):
    _, server = smtp
    assert mail.send_email(recipients, "<p>Test</p>", "Test") is True
    sender, envelope, content = server.sendmail.call_args.args
    assert envelope == expected
    assert message_from_string(content)["To"] == ", ".join(expected)
    server.starttls.assert_called_once()
    server.login.assert_called_once()


@pytest.mark.parametrize("recipients", [[], " ", ["", " "], None, [123]])
def test_email_without_valid_recipients(smtp, recipients):
    connection, _ = smtp
    assert mail.send_email(recipients, "Test", "Test") is False
    connection.assert_not_called()


def test_email_smtp_failure(smtp):
    _, server = smtp
    server.sendmail.side_effect = mail.smtplib.SMTPException("Simulated failure")
    assert mail.send_email("alice@example.invalid", "Test", "Test") is False


def test_email_partial_refusal(smtp):
    _, server = smtp
    server.sendmail.return_value = {"bob@example.invalid": (550, b"Refused")}
    assert (
        mail.send_email(
            ["alice@example.invalid", "bob@example.invalid"], "Test", "Test"
        )
        is False
    )


def test_admin_email_reports_failure(monkeypatch):
    send = MagicMock(side_effect=[False, True])
    monkeypatch.setattr(mail, "send_email", send)
    assert (
        mail.send_app_exception_to_admin(
            ["alice@example.invalid", "bob@example.invalid"]
        )
        is False
    )
    assert send.call_count == 2


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "mailpit"])
def test_explicit_local_capture_skips_tls_and_login(monkeypatch, smtp, host):
    monkeypatch.setenv("MEMORA_SMTP_CAPTURE_ONLY", "1")
    monkeypatch.setattr(mail.Setting, "EMAIL_HOST", host)
    connection, server = smtp
    assert mail.send_email("recipient@example.invalid", "<p>Synthetic</p>", "Test")
    connection.assert_called_once_with(host, mail.Setting.EMAIL_PORT, timeout=10)
    server.starttls.assert_not_called()
    server.login.assert_not_called()
    server.sendmail.assert_called_once()


@pytest.mark.parametrize(
    "host",
    [
        "smtp.example.invalid",
        "mailpit.evil.invalid",
        "192.0.2.1",
        "localhost:1025",
        None,
    ],
)
def test_local_capture_refuses_external_server_before_connect(monkeypatch, smtp, host):
    monkeypatch.setenv("MEMORA_SMTP_CAPTURE_ONLY", "1")
    monkeypatch.setattr(mail.Setting, "EMAIL_HOST", host)
    connection, _ = smtp
    assert mail.send_email("recipient@example.invalid", "Synthetic", "Test") is False
    connection.assert_not_called()
