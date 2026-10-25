"""Lifecycle for the local Apple-Silicon inference companion, never a container."""

import argparse
import os
import signal
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".memora/docker"
PID = PRIVATE / "inference.pid"
SCRIPT = ROOT / "scripts/memora-inference-host.py"


def process_matches(pid):
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and str(SCRIPT) in result.stdout


def listener():
    try:
        with socket.create_connection(("127.0.0.1", 8091), timeout=1):
            return True
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"])
    action = parser.parse_args().action
    pid = int(PID.read_text().strip()) if PID.exists() else None
    if action == "status":
        if pid and process_matches(pid) and listener():
            print("IA locale native : active sur 127.0.0.1:8091.")
            return
        raise SystemExit("IA locale native : arrêtée ou non suivie par Memora.")
    if action == "stop":
        if pid and process_matches(pid):
            os.kill(pid, signal.SIGTERM)
            for _ in range(40):
                if not process_matches(pid):
                    break
                time.sleep(0.25)
            else:
                raise SystemExit("IA encore active ; aucun arrêt forcé effectué.")
        elif pid and listener():
            raise SystemExit(
                "Identité du processus non confirmée ; aucun arrêt effectué."
            )
        PID.unlink(missing_ok=True)
        return
    if pid and process_matches(pid) and listener():
        print("IA locale native déjà active.")
        return
    if listener():
        raise SystemExit(
            "Port8091 déjà occupé par un service non suivi ; aucun second processus lancé."
        )
    python = ROOT / "backend/.venv/bin/python"
    if not python.exists() or not SCRIPT.exists():
        raise SystemExit(
            "Runtime IA natif absent : installer les prérequis documentés avant le démarrage."
        )
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    logs = PRIVATE / "logs"
    logs.mkdir(exist_ok=True)
    log_path = logs / "inference.log"
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "ab") as log:
        process = subprocess.Popen(
            [
                str(python),
                str(SCRIPT),
                "--env-file",
                str(ROOT / ".memora/backend.env"),
                "--bridge-env",
                str(PRIVATE / "bridge.env"),
            ],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    PID.write_text(str(process.pid) + "\n")
    PID.chmod(0o600)
    for _ in range(120):
        if process.poll() is not None:
            PID.unlink(missing_ok=True)
            raise SystemExit(
                "Le moteur IA n’a pas démarré ; voir .memora/docker/logs/inference.log."
            )
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8091/health", timeout=1
            ) as response:
                if response.status == 200:
                    print("IA locale native prête sur 127.0.0.1:8091.")
                    return
        except OSError:
            time.sleep(0.25)
    raise SystemExit(
        "Initialisation IA encore en cours ; processus conservé et état à vérifier."
    )


if __name__ == "__main__":
    main()
