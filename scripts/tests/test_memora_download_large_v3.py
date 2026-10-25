"""Synthetic local integrity checks; no networking or real model writes."""

import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "large_v3_download_test",
    Path(__file__).resolve().parents[1] / "memora-download-large-v3.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_pinned_comparison_target_is_separate():
    assert module.TARGET.name == "mlx-large-v3"
    assert module.transfer.WEIGHTS_FILE == "weights.npz"
    assert module.transfer.PINNED_BYTES == 3083520416
    assert module.transfer.PINNED_REVISION == "49e6aa286ad60c14352c404340ded53710378a11"


def test_offline_integrity_and_corruption(tmp_path):
    payload = b"synthetic full model"
    digest = hashlib.sha256(payload).hexdigest()
    metadata = {
        "repo": module.transfer.REPO,
        "revision": module.transfer.PINNED_REVISION,
        "sha256": digest,
        "bytes": len(payload),
        "license": "MIT",
    }
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "weights.npz").write_bytes(payload)
    (tmp_path / "memora-model.json").write_text(json.dumps(metadata))
    with (
        patch.object(module.transfer, "PINNED_BYTES", len(payload)),
        patch.object(module.transfer, "PINNED_SHA256", digest),
    ):
        assert module.verify_local(tmp_path) == metadata
        (tmp_path / "weights.npz").write_bytes(b"x" * len(payload))
        with pytest.raises(RuntimeError, match="SHA256"):
            module.verify_local(tmp_path)


def test_check_only_never_downloads(tmp_path):
    with (
        patch.object(module, "TARGET", tmp_path),
        patch.object(module.transfer, "download_pinned") as download,
    ):
        assert module.main(["--check-only"]) == 2
        download.assert_not_called()
        assert list(tmp_path.iterdir()) == []


def test_explicit_target_with_spaces_is_forwarded(tmp_path):
    target = tmp_path / "separate model"
    with patch.object(module.transfer, "run") as run:
        assert module.main(["--target", str(target), "--check-only"]) == 0
        run.assert_called_once_with(target.resolve(), check_only=True)
        assert not target.exists()


def test_environment_optional_target_is_forwarded(tmp_path):
    with (
        patch.dict("os.environ", {"MEMORA_MLX_FR_MODEL_PATH": str(tmp_path)}),
        patch.object(module.transfer, "run") as run,
    ):
        assert module.main(["--check-only"]) == 0
        run.assert_called_once_with(tmp_path.resolve(), check_only=True)


def test_rejects_turbo_path_before_any_transfer(tmp_path):
    with (
        patch.dict("os.environ", {"MEMORA_MLX_MODEL_PATH": str(tmp_path)}),
        patch.object(module.transfer, "run") as run,
    ):
        assert module.main(["--target", str(tmp_path)]) == 2
        run.assert_not_called()
        assert list(tmp_path.iterdir()) == []


def test_other_model_manifest_is_preserved(tmp_path):
    marker = tmp_path / "memora-model.json"
    original = json.dumps({"repo": "other/model"})
    marker.write_text(original)
    with patch.object(module.transfer, "run") as run:
        assert module.main(["--target", str(tmp_path)]) == 2
        run.assert_not_called()
    assert marker.read_text() == original


def test_unmanifested_weights_are_preserved(tmp_path):
    for name in ["weights.npz", "weights.safetensors"]:
        weights = tmp_path / name
        weights.write_bytes(b"existing synthetic model")
        with patch.object(module.transfer, "run") as run:
            assert module.main(["--target", str(tmp_path)]) == 2
            run.assert_not_called()
        assert weights.read_bytes() == b"existing synthetic model"
        weights.unlink()
