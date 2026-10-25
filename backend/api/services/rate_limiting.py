"""Rate limiting Redis partagé : middleware global et dépendances réutilisables."""

import hashlib
import hmac
from typing import Callable
from fastapi import Request
from fastapi.responses import JSONResponse
from redis_fastapi import (
    FastAPIRedis,
    get_rate_limit_backend,
    rate_limit as redis_rate_limit,
)
from api.services.authorization import CurrentUser


def client_identity(request: Request) -> str:
    """Identifier le pair réseau sans faire confiance aux en-têtes IP du client."""
    peer = request.client.host if request.client else "unknown"
    return hmac.new(
        request.app.state.config.SECRET_KEY.encode(), peer.encode(), hashlib.sha256
    ).hexdigest()


def limit_response(request, result):
    """Conserver l’enveloppe API ; distinguer quota épuisé et Redis indisponible."""
    status = 503 if result.degraded else 429
    message = (
        "Limitation temporairement indisponible."
        if result.degraded
        else "Trop de requêtes. Réessayez plus tard."
    )
    return JSONResponse(
        {"status": -1, "status_code": status, "message": message, "data": None},
        status_code=status,
    )


def configure_rate_limiting(app, config):
    """Activer les dépendances et, si le quota est positif, le middleware global."""
    if not config.RATE_LIMIT_ENABLED:
        return
    from redis_fastapi import get_settings

    get_settings().rate_limit_default_limit = 0
    FastAPIRedis(app).rate_limiting(
        global_rate=(
            config.RATE_LIMIT_GLOBAL_LIMIT,
            config.RATE_LIMIT_GLOBAL_WINDOW_SECONDS,
        )
        if config.RATE_LIMIT_GLOBAL_LIMIT
        else None,
        scope="application",
        identifier=client_identity,
        skip_when=lambda request: (
            request.method == "OPTIONS"
            or request.url.path in {"/metrics", "/api/healthcheck/", "/api/healthcheck"}
            or request.url.path == "/ws"
            or request.url.path.startswith("/ws/")
        ),
        on_limit_exceeded=limit_response,
        fail_closed=config.RATE_LIMIT_FAIL_CLOSED,
    )


def rate_limit(
    limit: int,
    seconds: int = 60,
    *,
    scope: str = "",
    identifier: Callable | None = None,
):
    """Limiter une route par IP ; scope explicite permet de partager un quota.

    Un identifiant personnalisé peut être sync ou async. Ne pas utiliser de
    claim JWT non vérifié ou de X-Forwarded-For fourni directement par le client.
    """
    # Le SDK valide ces paramètres dès la déclaration, même si la fonctionnalité est désactivée.
    redis_rate_limit(limit=limit, window=seconds)

    async def dependency(request: Request):
        """Refuser immédiatement le dépassement ; ne pas dormir dans la requête."""
        config = request.app.state.config
        if not config.RATE_LIMIT_ENABLED:
            return
        check = redis_rate_limit(
            limit=limit,
            window=seconds,
            scope=scope,
            identifier=identifier or client_identity,
            on_limit_exceeded=limit_response,
            fail_closed=config.RATE_LIMIT_FAIL_CLOSED,
            emit_headers=True,
        )
        await check(request, backend=await get_rate_limit_backend(request))

    return dependency


def user_rate_limit(limit: int, seconds: int = 60, *, scope: str = ""):
    """Limiter par compte authentifié ; réutiliser les contrôles de session existants."""
    rate_limit(limit, seconds)

    async def dependency(request: Request, user: CurrentUser):
        """Compter l’ID SQL validé, y compris derrière le proxy Next.js."""

        def identity(_request):
            raw = f"user:{user.id}".encode()
            return hmac.new(
                request.app.state.config.SECRET_KEY.encode(), raw, hashlib.sha256
            ).hexdigest()

        await rate_limit(limit, seconds, scope=scope, identifier=identity)(request)

    return dependency
