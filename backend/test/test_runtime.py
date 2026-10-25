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


def test_socketio_polling_handshake(client):
    response = client.get("/ws/socket.io/?EIO=4&transport=polling")
    assert response.status_code == 200
    assert response.text.startswith("0{")


def test_socketio_websocket_handshake(client):
    with client.websocket_connect(
        "/ws/socket.io/?EIO=4&transport=websocket",
        headers={"connection": "Upgrade", "upgrade": "websocket"},
    ) as websocket:
        assert websocket.receive_text().startswith("0{")


def test_validation_response(client):
    assert client.post("/api/auth/login", json={}).status_code == 400
