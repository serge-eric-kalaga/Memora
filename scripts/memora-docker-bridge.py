"""Lifecycle for the local Apple-Silicon inference companion, never a container."""

import argparse
import json
import os
import signal
import shlex
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".memora/docker"
PID = PRIVATE / "inference.pid"
SCRIPT = ROOT / "scripts/memora-inference-host.py"


def read_pid():
    try:
        pid = int(PID.read_text().strip())
        return pid if pid > 1 else None
    except (OSError, ValueError):
        return None


def prepare_private():
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    logs = PRIVATE / "logs"
    logs.mkdir(exist_ok=True, mode=0o700)
    descriptor = os.open(
        logs / "inference.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
    )
    os.fchmod(descriptor, 0o600)
    os.close(descriptor)


def host_command():
    return [
        str(ROOT / "backend/.venv/bin/python"),
        str(SCRIPT),
        "--env-file",
        str(ROOT / ".memora/backend.env"),
        "--bridge-env",
        str(PRIVATE / "bridge.env"),
    ]


def process_matches(pid):
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    try:
        args = shlex.split(result.stdout.strip())
    except ValueError:
        return False
    return str(SCRIPT) in args and str(PRIVATE / "bridge.env") in args


def listener():
    try:
        with socket.create_connection(("127.0.0.1", 8091), timeout=1):
            return True
    except OSError:
        return False


def healthy():
    """Check the known service and an authenticated endpoint, never log credentials."""
    try:
        token = None
        for line in (PRIVATE / "bridge.env").read_text().splitlines():
            if line.startswith("MEMORA_INFERENCE_TOKEN="):
                words = shlex.split(line.partition("=")[2])
                token = words[0] if len(words) == 1 else None
        if not token:
            return False
        with urllib.request.urlopen(
            "http://127.0.0.1:8091/health", timeout=1
        ) as response:
            if json.load(response).get("service") != "memora-native-inference":
                return False
        request = urllib.request.Request(
            "http://127.0.0.1:8091/diarization/availability",
            headers={"Authorization": "Bearer " + token},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"])
    parser.add_argument(
        "--unmanaged", action="store_true", help="Lancement natif direct (défaut)."
    )
    options = parser.parse_args()
    action = options.action
    pid = read_pid()
    if action == "status":
        if pid and process_matches(pid) and healthy():
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
    if pid and process_matches(pid) and healthy():
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
    prepare_private()
    log_path = PRIVATE / "logs/inference.log"
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "ab") as log:
        process = subprocess.Popen(
            host_command(),
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
        if healthy():
            print("IA locale native prête sur 127.0.0.1:8091.")
            return
        time.sleep(0.25)
    raise SystemExit(
        "Initialisation IA encore en cours ; processus conservé et état à vérifier."
    )


if __name__ == "__main__":
    main()
