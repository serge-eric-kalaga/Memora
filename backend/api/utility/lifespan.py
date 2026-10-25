from contextlib import asynccontextmanager
import os


@asynccontextmanager
async def LifeSpan(app):
    from api.configs.logging import logInfo
    from api.memora.worker import start, stop

    worker = start() if os.environ.get("MEMORA_DISABLE_WORKER") != "1" else None
    logInfo("STARTED")
    yield
    stop.set()
    if worker:
        worker.join(timeout=2)
    logInfo("ENDED")
