"""Disposable local files and fake metadata only; never touch ongoing download."""

import hashlib
import importlib.util
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "memora-download-mlx.py"
spec = importlib.util.spec_from_file_location("memora_download_test", SCRIPT)
downloader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(downloader)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.target = Path(self.temporary.name) / "local-model"
        self.payload = b"tiny synthetic model weights"
        self.digest = hashlib.sha256(self.payload).hexdigest()
        for key, value in (
            ("PINNED_BYTES", len(self.payload)),
            ("PINNED_SHA256", self.digest),
        ):
            manager = patch.object(downloader, key, value)
            manager.start()
            self.addCleanup(manager.stop)

    def seed(self, license_field=False):
        self.target.mkdir()
        (self.target / "config.json").write_text("{}")
        (self.target / "weights.safetensors").write_bytes(self.payload)
        meta = {
            "repo": downloader.REPO,
            "revision": downloader.PINNED_REVISION,
            "sha256": self.digest,
            "bytes": len(self.payload),
        }
        if license_field:
            meta["license"] = "MIT"
        (self.target / "memora-model.json").write_text(json.dumps(meta))
        return meta

    def test_verified_install_is_readonly_and_offline_regular_and_check(self):
        self.seed()
        (self.target / ".parts").mkdir()
        (self.target / ".parts/00192").write_bytes(b"untouched leftover")
        before = {
            path.relative_to(self.target): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.target.rglob("*")
            if path.is_file()
        }
        with (
            patch.object(
                downloader,
                "download_pinned",
                side_effect=AssertionError("No download allowed"),
            ),
            patch.object(
                downloader,
                "fetch_remote_metadata",
                side_effect=AssertionError("No API allowed"),
            ),
        ):
            downloader.run(self.target)
            downloader.run(self.target, check_only=True)
        after = {
            path.relative_to(self.target): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.target.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after)
        self.assertNotIn(
            "license", json.loads((self.target / "memora-model.json").read_text())
        )

    def test_check_missing_is_offline_and_creates_nothing(self):
        with (
            patch.object(
                downloader,
                "download_pinned",
                side_effect=AssertionError("No download allowed"),
            ),
            self.assertRaises(FileNotFoundError),
        ):
            downloader.run(self.target, check_only=True)
        self.assertFalse(self.target.exists())

    def test_corrupted_weights_rejected_without_repair_or_network(self):
        self.seed()
        damaged = b"X" + self.payload[1:]
        (self.target / "weights.safetensors").write_bytes(damaged)
        with (
            patch.object(
                downloader,
                "download_pinned",
                side_effect=AssertionError("No download allowed"),
            ),
            self.assertRaisesRegex(RuntimeError, "SHA256"),
        ):
            downloader.run(self.target)
        self.assertEqual((self.target / "weights.safetensors").read_bytes(), damaged)

    def test_local_revision_mismatch_rejected_even_when_hash_valid(self):
        self.seed(license_field=True)
        path = self.target / "memora-model.json"
        meta = json.loads(path.read_text())
        meta["revision"] = "different-revision"
        path.write_text(json.dumps(meta))
        with self.assertRaisesRegex(RuntimeError, "incompatible"):
            downloader.run(self.target, check_only=True)

    def test_remote_api_explicitly_pinned_and_matches_size_hash(self):
        calls = []
        entry = SimpleNamespace(
            rfilename="weights.safetensors",
            size=len(self.payload),
            lfs=SimpleNamespace(sha256=self.digest),
        )

        class API:
            def model_info(self, repo, **kwargs):
                calls.append((repo, kwargs))
                return SimpleNamespace(sha=downloader.PINNED_REVISION, siblings=[entry])

        result = downloader.fetch_remote_metadata(API())
        self.assertEqual(
            calls,
            [
                (
                    downloader.REPO,
                    {"revision": downloader.PINNED_REVISION, "files_metadata": True},
                )
            ],
        )
        self.assertEqual(result["license"], "MIT")
        self.assertEqual(result["sha256"], self.digest)
        entry.size += 1
        with self.assertRaisesRegex(RuntimeError, "incompatible"):
            downloader.fetch_remote_metadata(API())
        entry.size -= 1
        entry.lfs.sha256 = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "incompatible"):
            downloader.fetch_remote_metadata(API())

    def test_bad_remote_metadata_is_rejected_before_target_created(self):
        with (
            patch.object(
                downloader,
                "fetch_remote_metadata",
                side_effect=RuntimeError("incompatible remote metadata"),
            ),
            self.assertRaisesRegex(RuntimeError, "incompatible"),
        ):
            downloader.run(self.target)
        self.assertFalse(self.target.exists())

    def test_cli_check_only_offline_missing_model(self):
        with (
            patch.dict(os.environ, {"MEMORA_MLX_MODEL_PATH": str(self.target)}),
            patch.object(
                downloader,
                "download_pinned",
                side_effect=AssertionError("No download allowed"),
            ),
        ):
            self.assertEqual(downloader.main(["--check-only"]), 2)
        self.assertFalse(self.target.exists())

    def test_cli_check_only_valid_model_uses_full_hash(self):
        self.seed(license_field=True)
        with (
            patch.dict(os.environ, {"MEMORA_MLX_MODEL_PATH": str(self.target)}),
            patch.object(
                downloader,
                "download_pinned",
                side_effect=AssertionError("No download allowed"),
            ),
        ):
            self.assertEqual(downloader.main(["--check-only"]), 0)


if __name__ == "__main__":
    unittest.main()
