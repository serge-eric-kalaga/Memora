"""Prepare pinned Resemblyzer weights from installed PyPI package, fully offline."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA256 = "39373b86598fa3da9fcddee6142382efe09777e8d37dc9c0561f41f0070f134e"
BYTES = 17090379


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    target = Path(
        os.environ.get(
            "MEMORA_DIARIZATION_MODEL_DIR", ROOT / ".memora/models/resemblyzer-0.1.4"
        )
    )
    weights = target / "pretrained.pt"
    if weights.exists() and (target / "manifest.json").exists():
        manifest = json.loads((target / "manifest.json").read_text())
        if (
            weights.stat().st_size == BYTES
            and hashlib.sha256(weights.read_bytes()).hexdigest() == SHA256
            and manifest.get("sha256") == SHA256
        ):
            print("Local diarization weights verified SHA256; no files changed.")
            return
        raise ValueError(
            "Existing diarization weights are invalid; refusing overwrite."
        )
    if args.check_only:
        raise ValueError("Pinned local diarization weights not prepared.")
    package = importlib.metadata.distribution("Resemblyzer")
    if package.version != "0.1.4":
        raise ValueError("Expected pinned Resemblyzer0.1.4 package.")
    source = package.locate_file("resemblyzer/pretrained.pt")
    if (
        source.stat().st_size != BYTES
        or hashlib.sha256(source.read_bytes()).hexdigest() != SHA256
    ):
        raise ValueError(
            "Installed model does not match pinned official package weights."
        )
    target.mkdir(parents=True, exist_ok=True)
    if weights.exists():
        raise ValueError("Refusing overwrite of partial/existing model.")
    temporary = target / "pretrained.pt.tmp"
    shutil.copyfile(source, temporary)
    temporary.replace(weights)
    (target / "manifest.json").write_text(
        json.dumps(
            {
                "package": "Resemblyzer",
                "package_version": "0.1.4",
                "sha256": SHA256,
                "bytes": BYTES,
                "license": "Apache-2.0",
                "source": "https://pypi.org/project/Resemblyzer/0.1.4/",
                "upstream": "https://github.com/resemble-ai/Resemblyzer",
            },
            indent=2,
        )
    )
    print(
        "Pinned local diarization model prepared offline;17,090,379bytes;SHA256verified."
    )


if __name__ == "__main__":
    main()
