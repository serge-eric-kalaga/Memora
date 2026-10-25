"""Contrôles HTTP sans réseau ; le backend Redis sera aussi vérifié en recette isolée."""

import time
from types import SimpleNamespace
import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from redis_fastapi import RateLimitResult
import redis_fastapi.ratelimit as sdk
from api.services import rate_limiting as limits
from api.services.authorization import current_user


class FakeBackend:
    """Compteur déterministe pour vérifier le branchement, pas l’algorithme Redis."""

    def __init__(self):
        self.counts = {}
        self.degraded = False

    async def hit(self, identity, *, limit, window, scope, cost, fail_closed):
        key = (identity, scope, limit, window)
        self.counts[key] = self.counts.get(key, 0) + cost
        count = self.counts[key]
        return RateLimitResult(
            allowed=(not fail_closed if self.degraded else count <= limit),
            limit=limit,
            remaining=max(0, limit - count),
            reset_after=window,
            reset_at=int(time.time()) + window,
            retry_after=window if count > limit else 0,
            backend="fake",
            degraded=self.degraded,
        )


@pytest.fixture
def setup(monkeypatch):
    """Configurer l’application avec le SDK réel et un backend de test explicite."""
    backend = FakeBackend()

    async def get_backend(request):
        return backend

    monkeypatch.setattr(sdk, "get_rate_limit_backend", get_backend)
    monkeypatch.setattr(limits, "get_rate_limit_backend", get_backend)

    def build(global_limit=0, enabled=True, fail_closed=True):
        app = FastAPI()
        app.state.config = SimpleNamespace(
            RATE_LIMIT_ENABLED=enabled,
            RATE_LIMIT_GLOBAL_LIMIT=global_limit,
            RATE_LIMIT_GLOBAL_WINDOW_SECONDS=60,
            RATE_LIMIT_FAIL_CLOSED=fail_closed,
            SECRET_KEY="test-key",
        )
        limits.configure_rate_limiting(app, app.state.config)
        return app

    return build, backend


def test_route_scope_and_untrusted_forwarded_ip(setup):
    """Les paramètres de chemin et X-Forwarded-For ne permettent pas de contourner le quota."""
    build, _ = setup
    app = build()

    @app.get("/items/{id}", dependencies=[Depends(limits.rate_limit(2))])
    def item(id: int):
        return {"id": id}

    @app.get("/other", dependencies=[Depends(limits.rate_limit(2))])
    def other():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/items/1").status_code == 200
    assert client.get("/items/2").status_code == 200
    response = client.get("/items/3", headers={"X-Forwarded-For": "other-client"})
    assert response.status_code == 429
    assert response.json()["status_code"] == 429
    assert int(response.headers["Retry-After"]) > 0
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert client.get("/other").status_code == 200


def test_global_limit_and_exclusions(setup):
    """Le quota global est partagé entre routes ; les sondes restent accessibles."""
    build, _ = setup
    app = build(global_limit=2)

    @app.get("/{path:path}")
    def route(path: str):
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/one").status_code == 200
    assert client.get("/two").status_code == 200
    assert client.get("/three").status_code == 429
    for path in ("/metrics", "/api/healthcheck/", "/ws/socket.io/"):
        assert client.get(path).status_code == 200
    assert client.options("/one").status_code != 429
    assert client.get("/ws-admin").status_code == 429


def test_user_quotas_and_shared_scopes(setup):
    """Deux comptes derrière la même IP ont des quotas distincts et un scope commun."""
    build, _ = setup
    app = build()

    async def test_user(request: Request):
        name = request.headers.get("X-Test-User")
        if not name:
            raise HTTPException(401)
        return SimpleNamespace(id=name)

    app.dependency_overrides[current_user] = test_user

    @app.get("/a", dependencies=[Depends(limits.user_rate_limit(1, scope="exports"))])
    def first():
        return {"ok": True}

    @app.get("/b", dependencies=[Depends(limits.user_rate_limit(1, scope="exports"))])
    def second():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/a").status_code == 401
    assert client.get("/a", headers={"X-Test-User": "one"}).status_code == 200
    assert client.get("/b", headers={"X-Test-User": "one"}).status_code == 429
    assert client.get("/a", headers={"X-Test-User": "two"}).status_code == 200


def test_disabled_and_redis_outage(setup):
    """Sans activation, aucun backend n’est requis ; une panne peut refuser ou autoriser."""
    build, backend = setup
    for enabled, closed, status in (
        (False, True, 200),
        (True, True, 503),
        (True, False, 200),
    ):
        app = build(enabled=enabled, fail_closed=closed)

        @app.get("/", dependencies=[Depends(limits.rate_limit(1))])
        def route():
            return {"ok": True}

        backend.degraded = True
        assert TestClient(app).get("/").status_code == status
    assert len(backend.counts) == 1


def test_invalid_configuration():
    """Refuser une limite inutilisable dès la déclaration de route."""
    for limit, seconds in ((0, 60), (2, 0), (-1, 60)):
        with pytest.raises(ValueError):
            limits.rate_limit(limit, seconds)
