"""Dépendances de cache Redis réutilisables et invalidation par groupe métier."""

from typing import Annotated, Any
from contextlib import asynccontextmanager
from hashlib import sha256

from fastapi import Depends, HTTPException, Request
from redis_fastapi import (
    FastAPIRedis,
    cache,
    cache_evict,
    default_key_builder,
    get_settings,
)
from redis_fastapi.deps import get_async_redis

from api.services.jwt import getPayload


def configure_cache(app, config):
    """Configurer le SDK et conserver le lifespan existant de l’application."""
    app.state.config = config
    sdk = FastAPIRedis(app).caching()
    from api.services.rate_limiting import configure_rate_limiting

    configure_rate_limiting(app, config)
    if config.CACHE_ENABLED or config.RATE_LIMIT_ENABLED:
        settings = get_settings()
        settings.url = config.REDIS_URL or config.REDIS_DATABASE_URL
        settings.prefix = config.REDIS_PREFIX
        settings.default_ttl = config.CACHE_TTL_SECONDS
        sdk.lifespan()


async def get_cache_client(request: Request):
    """Fournir le client SDK ; remplaçable via app.dependency_overrides pour les tests."""
    if not request.app.state.config.CACHE_ENABLED:
        return None
    return await get_async_redis(request)


def _user_key(request: Request, eviction_group: str = "", prefix: str = "") -> str:
    """Séparer les entrées Redis par utilisateur sans stocker son JWT dans la clé."""
    identity = getattr(request.state, "cache_identity", None)
    if not identity:
        raise HTTPException(
            status_code=401, detail="Authentification requise pour ce cache"
        )
    base = default_key_builder(request, eviction_group=eviction_group, prefix=prefix)
    return f"{base}:user:{sha256(identity.encode()).hexdigest()}"


def cached_response(group: str, ttl: int | None = None, *, authenticated: bool = True):
    """Créer une dépendance GET avec TTL, groupe d’invalidation et authentification.

    À utiliser via Depends(cached_response("products", ttl=60)). Les routes
    publiques doivent demander explicitement authenticated=False. Les réponses
    privées ne sont pas conservées dans les caches HTTP des navigateurs/proxies.
    """
    if not group or (ttl is not None and ttl <= 0):
        raise ValueError("Un groupe non vide et un TTL strictement positif sont requis")
    guard = getPayload if authenticated else lambda: None

    async def dependency(
        request: Request,
        payload: Annotated[Any, Depends(guard)],
        redis: Annotated[Any, Depends(get_cache_client)],
    ):
        config = request.app.state.config
        if not config.CACHE_ENABLED:
            yield
            return
        if authenticated:
            request.state.cache_identity = str(payload.get("username", ""))
        # Le SDK reste responsable du HIT/MISS, des ETag et de la capture du corps.
        factory = cache(
            ttl=ttl if ttl is not None else config.CACHE_TTL_SECONDS,
            eviction_group=group,
            key_builder=_user_key if authenticated else default_key_builder,
            private=authenticated,
            no_store=authenticated,
        )
        async with asynccontextmanager(factory)(request=request, redis=redis):
            yield

    return dependency


def invalidate_cache(group: str):
    """Invalider un groupe après une écriture réussie, jamais après une exception."""
    if not group:
        raise ValueError("Le groupe d’invalidation ne peut pas être vide")

    async def dependency(
        request: Request, redis: Annotated[Any, Depends(get_cache_client)]
    ):
        if not request.app.state.config.CACHE_ENABLED:
            yield
            return
        async with asynccontextmanager(cache_evict(eviction_group=group))(
            request=request, redis=redis
        ):
            yield

    return dependency
