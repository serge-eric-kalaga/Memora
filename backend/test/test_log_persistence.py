"""Le chargement du point d’entrée ne doit jamais tronquer un journal existant."""

import os
from pathlib import Path
import subprocess
import sys


def test_log_survives_repeated_startup(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    journal = logs / "app.log"
    marker = "historique à conserver\n"
    journal.write_text(marker)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    env["DATABASE_URL"] = f"sqlite:///{tmp_path / 'startup.db'}"
    for _ in range(2):
        subprocess.run([sys.executable, "-c", "import run"], cwd=tmp_path,
                       env=env, check=True, capture_output=True, text=True)
        assert marker in journal.read_text()
