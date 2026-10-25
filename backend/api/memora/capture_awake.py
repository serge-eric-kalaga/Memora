"""Short, local macOS idle-sleep assertion. Never prevents manual sleep/display sleep."""

import atexit
import subprocess
import sys
import threading
import time
from pathlib import Path

TTL_SECONDS = 120
_LOCK = threading.Lock()
_LEASES = {}


def supported():
    return (
        sys.platform == "darwin"
        and Path("/usr/bin/caffeinate").is_file()
        and not Path("/.dockerenv").exists()
    )


def _stop(process):
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        # The OS assertion has its own fixed120s deadline even on cleanup races.
        pass


def _expire():
    now = time.monotonic()
    for owner, lease in list(_LEASES.items()):
        if lease["expires"] <= now or lease["process"].poll() is not None:
            _stop(lease["process"])
            del _LEASES[owner]


def set_active(owner, meeting, active):
    from . import inference_bridge

    if inference_bridge.configured():
        return inference_bridge.capture_awake(owner, meeting, active)
    with _LOCK:
        _expire()
        lease = _LEASES.get(owner)
        if not active:
            if lease and lease["meeting"] == meeting:
                _stop(lease["process"])
                del _LEASES[owner]
            return {"supported": supported(), "active": False}
        if not supported():
            return {"supported": False, "active": False}
        # At most one tracked child/lease per account incarnation. A new meeting
        # replaces that owner's previous capture, never another owner's lease.
        if lease:
            _stop(lease["process"])
            del _LEASES[owner]
        try:
            process = subprocess.Popen(
                ["/usr/bin/caffeinate", "-i", "-t", str(TTL_SECONDS)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except OSError:
            return {"supported": False, "active": False}
        if process.poll() is not None:
            return {"supported": True, "active": False}
        _LEASES[owner] = {
            "meeting": meeting,
            "process": process,
            "expires": time.monotonic() + TTL_SECONDS,
        }
        return {"supported": True, "active": True}


def release_all():
    with _LOCK:
        for lease in _LEASES.values():
            _stop(lease["process"])
        _LEASES.clear()


atexit.register(release_all)
