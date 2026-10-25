"""Exercise installer shell branches with synthetic executables, no installs/network."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parents[1] / "memora-install.sh"


@pytest.mark.parametrize(
    "primary,french,expected",
    [
        ("mlx-whisper", "", 0),
        ("mlx-whisper", "parakeet-mlx", 1),
        ("parakeet-mlx", "parakeet-mlx", 1),
        ("mlx-whisper", "mlx-whisper", 0),
        ("parakeet-mlx", "mlx-whisper", 1),
    ],
)
def test_optional_model_install_branch_and_quoted_target(
    tmp_path, primary, french, expected
):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "memora-install.sh").write_text(INSTALLER.read_text())
    binary = tmp_path / "fake-bin"
    binary.mkdir()
    python = tmp_path / "backend/.venv/bin/python"
    python.parent.mkdir(parents=True)
    (tmp_path / "frontend").mkdir()
    program = """import os,sys,json
with open(os.environ['TEST_CALLS'],'a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1:2]==['-c']:
 code=sys.argv[2]
 if 'MEMORA_FRENCH_ASR_ENGINE' in code:print(os.environ['TEST_FRENCH'])
 elif 'MEMORA_PARAKEET_MODEL_PATH' in code:print(os.environ['TEST_TARGET'])
 elif 'MEMORA_ASR_ENGINE' in code:print(os.environ['TEST_PRIMARY'])
 elif 'MEMORA_MLX_FR_MODEL_PATH' in code:print('')
 elif 'MEMORA_MLX_MODEL_PATH' in code:print(os.environ['TEST_TURBO'])
"""
    python.write_text("#!" + sys.executable + "\n" + program)
    python.chmod(0o755)
    for name in ["uv", "npm", "python3"]:
        p = binary / name
        p.write_text("#!/bin/sh\nexit 0\n")
        p.chmod(0o755)
    log = tmp_path / "calls.jsonl"
    env = {
        **os.environ,
        "PATH": str(binary) + os.pathsep + os.environ["PATH"],
        "TEST_CALLS": str(log),
        "TEST_PRIMARY": primary,
        "TEST_FRENCH": french,
        "TEST_TARGET": str(tmp_path / "model with spaces"),
        "TEST_TURBO": str(tmp_path / "turbo"),
    }
    subprocess.run(
        ["sh", str(scripts / "memora-install.sh")],
        env=env,
        check=True,
        capture_output=True,
    )
    calls = [json.loads(row) for row in log.read_text().splitlines()]
    assert [
        call for call in calls if call == ["scripts/memora-prepare-diarization.py"]
    ] == [["scripts/memora-prepare-diarization.py"]]
    downloads = [
        call
        for call in calls
        if call and call[0] == "scripts/memora-download-parakeet.py"
    ]
    assert len(downloads) == expected
    if expected:
        assert downloads[0] == [
            "scripts/memora-download-parakeet.py",
            "--target",
            env["TEST_TARGET"],
        ]

    turbo_downloads = [
        call for call in calls if call and call[0] == "scripts/memora-download-mlx.py"
    ]
    assert len(turbo_downloads) == (
        1 if primary == "mlx-whisper" or french == "mlx-whisper" else 0
    )
