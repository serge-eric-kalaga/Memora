"""Download the comparison-only full large-v3 MLX model, never activate it.

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
TARGET = ROOT / ".memora/models/mlx-large-v3"
spec = importlib.util.spec_from_file_location(
    "memora_large_v3_transfer", ROOT / "scripts/memora-download-mlx.py"
)
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)
transfer.REPO = "mlx-community/whisper-large-v3-mlx"
transfer.PINNED_REVISION = "49e6aa286ad60c14352c404340ded53710378a11"
transfer.PINNED_SHA256 = (
    "05ff791ce3630fae47e7c51004e9666204d786246ec07cac6110af768099b40d"
)
transfer.PINNED_BYTES = 3083520416
transfer.WEIGHTS_FILE = "weights.npz"


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
    elif target.exists() and any(target.glob("*.safetensors")):
        raise RuntimeError(
            "Destination occupée par un autre modèle ; aucun fichier modifié."
        )
    elif (target / "weights.npz").exists():
        raise RuntimeError(
            "Poids sans manifeste validé ; aucun fichier existant remplacé."
        )
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only", action="store_true", help="Offline full SHA256 check"
    )
    parser.add_argument(
        "--target",
        default=os.environ.get("MEMORA_MLX_FR_MODEL_PATH") or TARGET,
        help="Separate full-model directory (never the Turbo directory)",
    )
    args = parser.parse_args(argv)
    transfer.verify_local = verify_local
    try:
        transfer.run(guarded_target(args.target), check_only=args.check_only)
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
