"""Dedicated durable worker: python -m api.memora.worker_main [--healthcheck]."""

import argparse
import logging
import os
import signal
import threading
import time

from . import store, worker


def heartbeat_path():
    return store.ROOT / "worker.heartbeat"


def healthy():
    try:
        return time.time() - heartbeat_path().stat().st_mtime < 30
    except OSError:
        return False


def heartbeat():
    while not worker.stop.is_set():
        try:
            heartbeat_path().touch()
        except OSError as exc:
            worker.maintenance_failure("heartbeat", exc)
        if worker.stop.wait(5):
            break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--healthcheck", action="store_true")
    args = parser.parse_args()
    if args.healthcheck:
        return 0 if healthy() else 1
    logging.basicConfig(level=logging.INFO)
    # Prevent a future incidental API import from launching a second worker.
    os.environ["MEMORA_DISABLE_WORKER"] = "1"
    worker.acquire_worker_lock()
    worker.stop.clear()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_args: worker.stop.set())
    monitor = None
    try:
        # Recovery runs only under the shared lifetime lock. Database startup
        # failure exits nonzero and Docker restarts this independent process.
        store.init()
        monitor = threading.Thread(target=heartbeat, daemon=True)
        monitor.start()
        worker.loop()
        return 0
    finally:
        worker.stop.set()
        if monitor:
            monitor.join(timeout=6)
        heartbeat_path().unlink(missing_ok=True)
        worker.release_worker_lock()


if __name__ == "__main__":
    raise SystemExit(main())
