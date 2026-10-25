"""Authorized SSE invalidations backed by transactional PostgreSQL NOTIFY.

No meeting content travels on this transport. Clients reload through normal
permission-checked endpoints, including after reconnect and lost notifications.
"""

import asyncio
import hashlib
import os
import threading
from collections import Counter
from contextlib import asynccontextmanager

from fastapi import HTTPException

_LIMITS = Counter()
_LOCK = threading.Lock()
HEARTBEAT_SECONDS = 15


def channel(kind, identity):
    if kind not in ("m", "u"):
        raise ValueError("Invalid event scope")
    return (
        f"memora_{kind}_"
        + hashlib.md5(identity.encode(), usedforsecurity=False).hexdigest()
    )


@asynccontextmanager
async def subscribe(scope):
    """Bound resources and establish LISTEN *before* the initial refresh."""
    url = os.environ.get("MEMORA_DATABASE_URL", "")
    if not url:
        raise HTTPException(503, "Temps réel indisponible ; actualisation de secours.")
    with _LOCK:
        if sum(_LIMITS.values()) >= 32 or _LIMITS[scope] >= 3:
            raise HTTPException(429, "Trop de connexions temps réel.")
        _LIMITS[scope] += 1
    connection = None
    try:
        import psycopg
        from psycopg import sql

        connection = await psycopg.AsyncConnection.connect(
            url, autocommit=True, connect_timeout=5
        )
        await connection.execute(sql.SQL("LISTEN {}").format(sql.Identifier(scope)))
        yield connection
    finally:
        try:
            if connection:
                await connection.close()
        finally:
            with _LOCK:
                _LIMITS[scope] -= 1
                if not _LIMITS[scope]:
                    del _LIMITS[scope]


async def events(connection, authorize, disconnected):
    """Recheck access on every event and heartbeat; never send private payloads."""
    try:
        await authorize()
        yield "event: refresh\ndata: {}\n\n"
        while not await disconnected():
            changed = False
            async for _ in connection.notifies(timeout=HEARTBEAT_SECONDS, stop_after=1):
                changed = True
            await authorize()
            yield "event: refresh\ndata: {}\n\n" if changed else ": heartbeat\n\n"
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 - close without leaking auth/database details
        yield "event: unavailable\ndata: {}\n\n"
