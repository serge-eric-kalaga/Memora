"""No network/GPU; synthetic Parakeet provenance and auxiliary integrity tests."""

import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "parakeet_download_test",
    Path(__file__).resolve().parents[1] / "memora-download-parakeet.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_license_is_not_inherited_from_whisper():
    assert module.transfer.UPSTREAM_LICENSE == "CC-BY-4.0"
    assert module.TARGET.name == "parakeet-v3"
    assert module.transfer.WEIGHTS_FILE == "model.safetensors"
    with pytest.raises(RuntimeError):
        module.transfer.pinned_metadata(
            {
                "repo": module.transfer.REPO,
                "revision": module.transfer.PINNED_REVISION,
                "bytes": module.transfer.PINNED_BYTES,
                "sha256": module.transfer.PINNED_SHA256,
                "license": "MIT",
            }
        )


def test_assets_are_pinned_without_python_code():
    assert set(module.transfer.ASSET_FILES) == {
        "config.json",
        "README.md",
        "tokenizer.model",
        "tokenizer.vocab",
        "vocab.txt",
    }
    assert all(
        len(item["sha256"]) == 64 and item["bytes"] > 0
        for item in module.transfer.ASSET_HASHES.values()
    )


def test_offline_checks_full_weights_and_auxiliary_assets(tmp_path):
    weights = b"synthetic parakeet"
    config = b"{}"
    digest = hashlib.sha256(weights).hexdigest()
    asset = {
        "config.json": {
            "bytes": len(config),
            "sha256": hashlib.sha256(config).hexdigest(),
        }
    }
    meta = {
        "repo": module.transfer.REPO,
        "revision": module.transfer.PINNED_REVISION,
        "bytes": len(weights),
        "sha256": digest,
        "license": "CC-BY-4.0",
    }
    (tmp_path / "model.safetensors").write_bytes(weights)
    (tmp_path / "config.json").write_bytes(config)
    (tmp_path / "memora-model.json").write_text(json.dumps(meta))
    with (
        patch.object(module.transfer, "PINNED_BYTES", len(weights)),
        patch.object(module.transfer, "PINNED_SHA256", digest),
        patch.object(module.transfer, "ASSET_HASHES", asset),
    ):
        assert module.verify_local(tmp_path) == meta
        (tmp_path / "config.json").write_bytes(b"[]")
        with pytest.raises(RuntimeError, match="auxiliaire"):
            module.verify_local(tmp_path)


def test_other_repo_target_is_not_overwritten(tmp_path):
    manifest = tmp_path / "memora-model.json"
    original = '{"repo":"mlx-community/whisper-large-v3-mlx"}'
    manifest.write_text(original)
    with patch.object(module.transfer, "run") as run:
        assert module.main(["--target", str(tmp_path)]) == 2
        run.assert_not_called()
    assert manifest.read_text() == original
