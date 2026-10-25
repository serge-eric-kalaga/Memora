"""Vérifier les destinataires et les erreurs sans envoyer d’e-mail réel."""

from unittest.mock import MagicMock
from email import message_from_string
import pytest
from api.services import mail


@pytest.fixture
def smtp(monkeypatch):
    server = MagicMock()
    server.sendmail.return_value = {}
    connection = MagicMock()
    connection.return_value.__enter__.return_value = server
    monkeypatch.setattr(mail.smtplib, "SMTP", connection)
    return connection, server


@pytest.mark.parametrize("recipients, expected", [
    ("alice@example.invalid", ["alice@example.invalid"]),
    ([" alice@example.invalid ", "bob@example.invalid", "alice@example.invalid"],
     ["alice@example.invalid", "bob@example.invalid"]),
])
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
    assert mail.send_email(["alice@example.invalid", "bob@example.invalid"], "Test", "Test") is False


def test_admin_email_reports_failure(monkeypatch):
    send = MagicMock(side_effect=[False, True])
    monkeypatch.setattr(mail, "send_email", send)
    assert mail.send_app_exception_to_admin(["alice@example.invalid", "bob@example.invalid"]) is False
    assert send.call_count == 2
