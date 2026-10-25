"""Execute a copied generator only in disposable folders; never main backend.env."""

import runpy
import shlex
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "memora-env.py"


def run_copy(tmp_path, system, machine):
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    copy = scripts / "memora-env.py"
    copy.write_text(SOURCE.read_text())
    with (
        patch("platform.system", return_value=system),
        patch("platform.machine", return_value=machine),
    ):
        runpy.run_path(str(copy), run_name="__main__")
    return tmp_path / ".memora/backend.env"


def values(path):
    return {
        key: shlex.split(value)[0] if shlex.split(value) else ""
        for key, value in (line.split("=", 1) for line in path.read_text().splitlines())
    }


def test_new_darwin_arm_uses_language_conditioned_french_route(tmp_path):
    folder = tmp_path / "project with spaces"
    folder.mkdir()
    path = run_copy(folder, "Darwin", "arm64")
    env = values(path)
    assert env["MEMORA_ASR_ENGINE"] == env["MEMORA_LIVE_ASR_ENGINE"] == "mlx-whisper"
    assert env["MEMORA_FRENCH_ASR_ENGINE"] == "mlx-whisper"
    assert env["MEMORA_DIARIZATION_ENGINE"] == "ecapa-tdnn"
    assert env["MEMORA_ECAPA_MODEL_DIR"] == str(
        folder / ".memora/models/ecapa-voxceleb"
    )
    assert env["MEMORA_PARAKEET_MODEL_PATH"] == str(
        folder / ".memora/models/parakeet-v3"
    )
    assert env["MEMORA_PARAKEET_MODEL_PATH"] != env["MEMORA_MLX_MODEL_PATH"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert (
        env["SECRET_KEY"]
        and env["JWT_SECRET"]
        and env["SECRET_KEY"] != env["JWT_SECRET"]
    )


@pytest.mark.parametrize(
    "system,machine", [("Linux", "x86_64"), ("Linux", "arm64"), ("Darwin", "x86_64")]
)
def test_new_other_platform_retains_cpu_and_no_french_mlx_route(
    tmp_path, system, machine
):
    env = values(run_copy(tmp_path, system, machine))
    assert env["MEMORA_ASR_ENGINE"] == env["MEMORA_LIVE_ASR_ENGINE"] == "faster-whisper"
    assert env["MEMORA_FRENCH_ASR_ENGINE"] == env["MEMORA_PARAKEET_MODEL_PATH"] == ""


def test_existing_configuration_secrets_bytes_and_metadata_preserved(tmp_path):
    data = tmp_path / ".memora"
    data.mkdir()
    path = data / "backend.env"
    payload = b"# synthetic existing configuration\r\nSECRET_KEY='synthetic-test-only-value'\r\nMEMORA_ASR_ENGINE=faster-whisper\r\nCUSTOM=keep-me\r\n"
    path.write_bytes(payload)
    path.chmod(0o600)
    before = path.stat()
    run_copy(tmp_path, "Darwin", "arm64")
    after = path.stat()
    assert path.read_bytes() == payload
    assert before.st_mtime_ns == after.st_mtime_ns
    assert before.st_ino == after.st_ino
    assert stat.S_IMODE(after.st_mode) == 0o600
