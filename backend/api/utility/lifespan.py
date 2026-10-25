from contextlib import asynccontextmanager
import os


@asynccontextmanager
async def LifeSpan(app):
    from api.configs.logging import logInfo
    from api.memora.worker import start, stop
    from api.memora.capture_awake import release_all

    worker = start() if os.environ.get("MEMORA_DISABLE_WORKER") != "1" else None
    logInfo("STARTED")
    try:
        yield
    finally:
        release_all()
        stop.set()
        if worker:
            worker.join(timeout=2)
        logInfo("ENDED")
