"""Contrôles de compatibilité des routes après mise à jour des dépendances."""

import pytest
from fastapi.testclient import TestClient
from api import createApp, SETTINGS


@pytest.fixture
def client():
    with TestClient(createApp(SETTINGS())) as test_client:
        yield test_client


@pytest.mark.parametrize("path", ["/api/healthcheck/", "/docs", "/openapi.json", "/metrics"])
def test_runtime_routes(client, path):
    assert client.get(path).status_code == 200


def test_validation_response(client):
    assert client.post("/api/auth/login", json={}).status_code == 400
