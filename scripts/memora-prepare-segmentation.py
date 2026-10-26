"""Prepare the public MIT segmentation ONNX distribution, without an account."""

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
ARCHIVE_SHA = "24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488"
ARCHIVE_BYTES = 6958444
MODEL_SHA = "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079"
MODEL_BYTES = 5992913
LICENSE_SHA = "14d7016ad68e7394d6e6b78d96cc2ae431c905287b89674cfdf021e79e62b8ba"
PREFIX = "sherpa-onnx-pyannote-segmentation-3-0/"


def verify(path, size, digest):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
        raise ValueError("Segmentation asset size invalid")
    with path.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != digest:
            raise ValueError("Segmentation asset SHA256 invalid")


def prepare(folder, archive=None, check_only=False):
    if folder.is_symlink():
        raise ValueError("Refusing symlink destination")
    if folder.exists():
        if (folder / "manifest.json").is_symlink():
            raise ValueError("Refusing symlink manifest")
        manifest = json.loads((folder / "manifest.json").read_text())
        if manifest.get("sha256") != MODEL_SHA or manifest.get("license") != "MIT":
            raise ValueError("Existing segmentation manifest invalid")
        verify(folder / "model.onnx", MODEL_BYTES, MODEL_SHA)
        license_file = folder / "LICENSE"
        if license_file.is_symlink() or not license_file.is_file():
            raise ValueError("Missing upstream license")
        if hashlib.sha256(license_file.read_bytes()).hexdigest() != LICENSE_SHA:
            raise ValueError("Upstream license integrity invalid")
        return
    if check_only:
        raise ValueError("Local segmentation assets not prepared")
    if any(p.is_symlink() for p in (folder.parent, *folder.parent.parents)):
        raise ValueError("Refusing symlink destination parent")
    folder.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".segmentation-", dir=folder.parent) as tmp:
        temporary = Path(tmp)
        if archive is None:
            archive = temporary / "archive.tar.bz2"
            with (
                urllib.request.urlopen(SOURCE, timeout=60) as response,
                archive.open("xb") as target,
            ):
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > ARCHIVE_BYTES:
                        raise ValueError("Segmentation download exceeds pinned size")
                    target.write(chunk)
        verify(archive, ARCHIVE_BYTES, ARCHIVE_SHA)
        stage = temporary / "model"
        stage.mkdir()
        with tarfile.open(archive, "r:bz2") as handle:
            # Read only fixed members. No archive path or link is ever extracted.
            for name, limit in (("model.onnx", MODEL_BYTES), ("LICENSE", 16384)):
                matches = [m for m in handle.getmembers() if m.name == PREFIX + name]
                if (
                    len(matches) != 1
                    or not matches[0].isfile()
                    or matches[0].size > limit
                ):
                    raise ValueError("Invalid segmentation archive member")
                with (
                    handle.extractfile(matches[0]) as source,
                    (stage / name).open("xb") as target,
                ):
                    shutil.copyfileobj(source, target)
        verify(stage / "model.onnx", MODEL_BYTES, MODEL_SHA)
        if hashlib.sha256((stage / "LICENSE").read_bytes()).hexdigest() != LICENSE_SHA:
            raise ValueError("Missing upstream MIT license")
        (stage / "NOTICE.md").write_text(
            "# Segmentation 3.0 ONNX\n\n"
            "Model authors: pyannote / CNRS. License: MIT; preserve LICENSE.\n"
            "Original: https://huggingface.co/pyannote/segmentation-3.0\n"
            "Conversion and public distribution: k2-fsa/sherpa-onnx.\n"
            f"Source: {SOURCE}\nArchive SHA256: {ARCHIVE_SHA}\n"
        )
        (stage / "manifest.json").write_text(
            json.dumps(
                {
                    "sha256": MODEL_SHA,
                    "bytes": MODEL_BYTES,
                    "license": "MIT",
                    "archive_sha256": ARCHIVE_SHA,
                    "source": SOURCE,
                },
                indent=2,
            )
        )
        if folder.exists():
            raise ValueError("Concurrent installation detected")
        stage.rename(folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-archive", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    folder = Path(
        os.environ.get(
            "MEMORA_SEGMENTATION_MODEL_DIR", ROOT / ".memora/models/segmentation-3.0"
        )
    )
    prepare(folder, args.from_archive, args.check_only)
    print("Pinned MIT segmentation model verified; no network needed for inference.")


if __name__ == "__main__":
    main()
