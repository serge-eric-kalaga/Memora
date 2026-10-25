"""Detach one local service and verify its listener without printing its environment."""

import socket
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
name, port, *command = sys.argv[1:]
if name not in {"backend", "frontend", "mail"} or not command:
    raise SystemExit("Service Memora invalide.")
log = root / "agents/logs" / f"{name}.log"
pidfile = root / ".memora/pids" / name
with log.open("ab") as output:
    process = subprocess.Popen(
        command,
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=output,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
pidfile.write_text(str(process.pid) + "\n")
for _ in range(40):
    if process.poll() is not None:
        pidfile.unlink(missing_ok=True)
        raise SystemExit(f"{name} n’a pas démarré ; voir {log.relative_to(root)}.")
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.25):
            print(f"{name} écoute sur 127.0.0.1:{port}.")
            break
    except OSError:
        time.sleep(0.25)
else:
    raise SystemExit(
        f"{name} n’a pas encore ouvert son port ; processus conservé, voir {log.relative_to(root)}."
    )
