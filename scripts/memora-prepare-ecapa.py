"""Prepare official pinned Apache-2.0 ECAPA weights; never replaces existing files."""

import argparse
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ecapa_assets", ROOT / "backend/api/memora/diarization_ecapa.py"
)
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument(
        "--from-file",
        type=Path,
        help="Reuse a local copy matching the pinned official SHA256",
    )
    args = parser.parse_args()
    folder = assets.model_dir()
    if (folder / "manifest.json").exists():
        assets.verified_weights()
        print("Pinned ECAPA weights verified; no files changed.")
        return
    if args.check_only:
        raise ValueError("Pinned local ECAPA weights not prepared")
    target = folder / "embedding_model.ckpt"
    if target.exists():
        raise ValueError("Refusing overwrite of existing unverified ECAPA weights")
    source = args.from_file
    if source is None:
        from huggingface_hub import hf_hub_download

        source = Path(
            hf_hub_download(
                "speechbrain/spkrec-ecapa-voxceleb",
                "embedding_model.ckpt",
                revision=assets.REVISION,
                token=False,
            )
        )
    if (
        source.stat().st_size != assets.BYTES
        or hashlib.sha256(source.read_bytes()).hexdigest() != assets.SHA256
    ):
        raise ValueError("Official ECAPA weights failed integrity verification")
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / "embedding_model.ckpt.tmp"
    shutil.copyfile(source, temporary)
    temporary.replace(target)
    (folder / "manifest.json").write_text(
        json.dumps(
            {
                "revision": assets.REVISION,
                "sha256": assets.SHA256,
                "bytes": assets.BYTES,
                "license": "Apache-2.0",
                "source": "https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb",
            },
            indent=2,
        )
    )
    print("Pinned official ECAPA weights prepared and verified.")


if __name__ == "__main__":
    main()
