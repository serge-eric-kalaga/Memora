from contextlib import asynccontextmanager
import os


@asynccontextmanager
async def LifeSpan(app):
    from api.configs.logging import logInfo
    from api.memora.worker import start, stop
    from api.memora.capture_awake import release_all

    external_worker = os.environ.get("MEMORA_DISABLE_WORKER") == "1"
    if external_worker:
        from api.memora import store

        store.init(recover_jobs=False)
    worker = None if external_worker else start()
    logInfo("STARTED")
    try:
        yield
    finally:
        release_all()
        stop.set()
        if worker:
            worker.join(timeout=2)
        logInfo("ENDED")
