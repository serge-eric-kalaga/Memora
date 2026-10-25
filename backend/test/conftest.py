"""Garde de la suite de tests : aucun accès à un serveur SMTP réel."""

from unittest.mock import MagicMock
import pytest


@pytest.fixture(autouse=True)
def isolated_smtp(monkeypatch):
    """Les tests peuvent remplacer ce mock ; le transport réel reste toujours neutralisé."""
    from api.services import mail

    connection = MagicMock()
    connection.return_value.__enter__.return_value.sendmail.return_value = {}
    monkeypatch.setattr(mail.smtplib, "SMTP", connection)
