"""Download the comparison-only Parakeet v3 MLX model, never activate it.

Reuses the Turbo downloader's resumable, pinned, full-SHA-verified transfer.
The default destination is separate; no existing model or runtime config is changed.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".memora/models/parakeet-v3"
spec = importlib.util.spec_from_file_location(
    "memora_parakeet_transfer", ROOT / "scripts/memora-download-mlx.py"
)
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)
transfer.REPO = "mlx-community/parakeet-tdt-0.6b-v3"
transfer.PINNED_REVISION = "ed2b7e8c15f9aaa0b5772e2efb986255eaef7e15"
transfer.PINNED_SHA256 = (
    "05e01c7f396c298cf7d23f61da7b504adeab698f0aaeafd9c82d198625464592"
)
transfer.PINNED_BYTES = 2508288736
transfer.WEIGHTS_FILE = "model.safetensors"
transfer.UPSTREAM_LICENSE = "CC-BY-4.0"
transfer.LICENSE_SOURCE = "https://creativecommons.org/licenses/by/4.0/"
transfer.ASSET_HASHES = {
    "README.md": {
        "bytes": 1081,
        "sha256": "724e3ba46903986ff6caeb8fddb7495c06b5a7a8d908f11e43cc0a7e136b5e23",
    },
    "config.json": {
        "bytes": 244093,
        "sha256": "f320f1292511f34ec47f513755fe20fd01dbfc09a925d42730e66059a6e1ef4c",
    },
    "tokenizer.model": {
        "bytes": 360916,
        "sha256": "eacec2b0a77f336d4a2ca4a25a7047575d3c2b74de47e997f4c205126ed3135e",
    },
    "tokenizer.vocab": {
        "bytes": 101024,
        "sha256": "41130ff456706304a1adec782ccc9e003c4d417e8e324353d281be958cac4e17",
    },
    "vocab.txt": {
        "bytes": 46772,
        "sha256": "3cde1409fd78783a79b29ed4d32da57c746993856f7c8263bcb905d2e5839db7",
    },
}
transfer.ASSET_FILES = tuple(transfer.ASSET_HASHES)


def verify_local(target):
    metadata = transfer.pinned_metadata(
        json.loads((target / "memora-model.json").read_text())
    )
    weights = target / transfer.WEIGHTS_FILE
    if (
        not (target / "config.json").is_file()
        or weights.stat().st_size != transfer.PINNED_BYTES
    ):
        raise RuntimeError(
            "Modèle complet absent ou taille incorrecte ; aucun fichier modifié."
        )
    digest = hashlib.sha256()
    with weights.open("rb") as source:
        while block := source.read(transfer.CHUNK):
            digest.update(block)
    if digest.hexdigest() != transfer.PINNED_SHA256:
        raise RuntimeError("SHA256 complet incorrect ; aucun modèle activé.")
    for name, expected in transfer.ASSET_HASHES.items():
        asset = target / name
        if (
            not asset.is_file()
            or asset.stat().st_size != expected["bytes"]
            or hashlib.sha256(asset.read_bytes()).hexdigest() != expected["sha256"]
        ):
            raise RuntimeError(
                "Fichier auxiliaire Parakeet absent ou corrompu ; aucun chargement autorisé."
            )
    return metadata


def guarded_target(value):
    target = Path(value).expanduser().resolve()
    turbo = (
        Path(
            os.environ.get("MEMORA_MLX_MODEL_PATH")
            or ROOT / ".memora/models/mlx-large-v3-turbo"
        )
        .expanduser()
        .resolve()
    )
    if target in {turbo, (ROOT / ".memora/models/mlx-large-v3-turbo").resolve()}:
        raise RuntimeError(
            "Destination Turbo interdite ; aucun modèle existant remplacé."
        )
    manifest = target / "memora-model.json"
    if manifest.exists():
        transfer.pinned_metadata(json.loads(manifest.read_text()))
    elif target.exists() and (
        any(target.glob("*.safetensors")) or (target / "weights.npz").exists()
    ):
        raise RuntimeError(
            "Destination occupée par un autre modèle ; aucun fichier modifié."
        )
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only", action="store_true", help="Offline full SHA256 check"
    )
    parser.add_argument(
        "--target",
        default=TARGET,
        help="Separate full-model directory (never the Turbo directory)",
    )
    args = parser.parse_args(argv)
    transfer.verify_local = verify_local
    try:
        target = guarded_target(args.target)
        transfer.run(target, check_only=args.check_only)
        if not args.check_only:
            attribution = target / "ATTRIBUTION.md"
            if not attribution.exists():
                attribution.write_text(
                    "# Parakeet TDT 0.6B v3\n\nOriginal model: NVIDIA, https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3\n"
                    "MLX conversion: MLX Community, https://huggingface.co/mlx-community/parakeet-tdt-0.6b-v3\n"
                    "License: Creative Commons Attribution 4.0 International (CC-BY-4.0), https://creativecommons.org/licenses/by/4.0/\n"
                    "Local changes: none to the downloaded pinned model assets. Memora only records integrity metadata.\n"
                )
    except (RuntimeError, OSError, ValueError, TypeError) as error:
        print(
            str(error)
            if isinstance(error, RuntimeError)
            else f"Modèle non vérifié ({type(error).__name__}).",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
