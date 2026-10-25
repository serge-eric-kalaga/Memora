"""Install the pinned public MLX checkpoint; verified installs are read-only.

--check-only is offline and reuses the benchmark's full-file SHA256 verification.
Never run two downloaders concurrently. This file is safe to import for tests.
"""

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "mlx-community/whisper-large-v3-turbo"
PINNED_REVISION = "a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb"
PINNED_SHA256 = "951ed3fc1203e6a62467abb2144a96ce7eafca8fa77e3704fdb8635ff3e7f8a6"
PINNED_BYTES = 1613977612
UPSTREAM_LICENSE = "MIT"
LICENSE_SOURCE = "https://github.com/openai/whisper/blob/main/LICENSE"
WEIGHTS_FILE = "weights.safetensors"
ASSET_FILES = ("config.json", "README.md")
ASSET_HASHES = {}
CHUNK = 8 * 1024 * 1024


def pinned_metadata(metadata):
    if not isinstance(metadata, dict):
        raise TypeError("Manifeste MLX invalide. Aucun téléchargement ni réécriture.")
    if (
        metadata.get("repo") != REPO
        or metadata.get("revision") != PINNED_REVISION
        or metadata.get("sha256") != PINNED_SHA256
        or metadata.get("bytes") != PINNED_BYTES
        or str(metadata.get("license", UPSTREAM_LICENSE)).casefold()
        != UPSTREAM_LICENSE.casefold()
    ):
        raise RuntimeError(
            "Provenance, taille ou empreinte incompatible avec le modèle MLX épinglé. Aucun fichier validé modifié."
        )
    return metadata


def verify_local(target):
    # Check cheap provenance first, then delegate actual full weights hashing.
    manifest = json.loads((target / "memora-model.json").read_text())
    pinned_metadata(manifest)
    path = ROOT / "scripts/memora-benchmark-mlx.py"
    spec = importlib.util.spec_from_file_location("memora_download_verifier", path)
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    return pinned_metadata(benchmark.verify_model(target))


def fetch_remote_metadata(api=None):
    from httpx import HTTPError
    from huggingface_hub.errors import HfHubHTTPError

    if api is None:
        # No networking dependency is imported in the offline check-only path.
        from huggingface_hub import HfApi

        api = HfApi()
    try:
        info = api.model_info(REPO, revision=PINNED_REVISION, files_metadata=True)
    except (HfHubHTTPError, HTTPError, OSError) as error:
        raise RuntimeError(
            f"Métadonnées officielles indisponibles ({type(error).__name__}), aucun téléchargement lancé."
        ) from None
    entry = next(
        (item for item in info.siblings if item.rfilename == WEIGHTS_FILE),
        None,
    )
    if entry is None or entry.lfs is None:
        raise RuntimeError(
            "Métadonnées officielles des poids MLX absentes. Aucun téléchargement lancé."
        )
    metadata = {
        "repo": REPO,
        "revision": info.sha,
        "sha256": entry.lfs.sha256,
        "bytes": entry.size,
        # The conversion card does not declare a separate license; retain the
        # known upstream Whisper MIT provenance rather than inventing API data.
        "license": UPSTREAM_LICENSE,
        "license_source": LICENSE_SOURCE,
    }
    return pinned_metadata(metadata)


def download_pinned(target):
    import httpx

    # Validate remote immutable revision/size/hash before writing config or data.
    metadata = fetch_remote_metadata()
    if ASSET_HASHES:
        metadata["assets"] = ASSET_HASHES
    target.mkdir(parents=True, exist_ok=True)
    size, expected = metadata["bytes"], metadata["sha256"]
    revision = metadata["revision"]
    try:
        with httpx.Client(
            follow_redirects=True, timeout=httpx.Timeout(60, connect=15)
        ) as client:
            for filename in ASSET_FILES:
                response = client.get(
                    f"https://huggingface.co/{REPO}/resolve/{revision}/{filename}"
                )
                response.raise_for_status()
                expected_asset = ASSET_HASHES.get(filename)
                if expected_asset and (
                    len(response.content) != expected_asset["bytes"]
                    or hashlib.sha256(response.content).hexdigest()
                    != expected_asset["sha256"]
                ):
                    raise RuntimeError(
                        "Intégrité d’un fichier auxiliaire incorrecte ; installation interrompue."
                    )
                temporary = target / (filename + ".tmp")
                temporary.write_bytes(response.content)
                temporary.replace(target / filename)
            parts = target / ".parts"
            parts.mkdir(exist_ok=True)
            count = (size + CHUNK - 1) // CHUNK
            lock = threading.Lock()
            progress = [0]

            def download(index):
                start, end = index * CHUNK, min(size, (index + 1) * CHUNK) - 1
                part = parts / f"{index:05d}"
                if not part.exists() or part.stat().st_size != end - start + 1:
                    for attempt in range(5):
                        try:
                            temp = part.with_suffix(".tmp")
                            received = temp.stat().st_size if temp.exists() else 0
                            if received > end - start + 1:
                                temp.unlink()
                                received = 0
                            if received == end - start + 1:
                                temp.replace(part)
                                break
                            resume = start + received
                            with client.stream(
                                "GET",
                                f"https://huggingface.co/{REPO}/resolve/{revision}/{WEIGHTS_FILE}?download=true",
                                headers={"Range": f"bytes={resume}-{end}"},
                            ) as response:
                                response.raise_for_status()
                                if (
                                    response.status_code != 206
                                    or response.headers.get("content-range")
                                    != f"bytes {resume}-{end}/{size}"
                                ):
                                    raise ValueError("Réponse Range inattendue")
                                with temp.open("ab") as output:
                                    for block in response.iter_bytes(1024 * 1024):
                                        output.write(block)
                            if temp.stat().st_size != end - start + 1:
                                raise ValueError("Fragment incomplet")
                            temp.replace(part)
                            break
                        except (httpx.HTTPError, OSError, ValueError):
                            print(
                                f"Fragment {index} : reprise {attempt + 1}/5 (octets conservés)",
                                flush=True,
                            )
                            if attempt == 4:
                                raise RuntimeError(
                                    f"Échec du fragment {index}, reprise possible"
                                ) from None
                with lock:
                    progress[0] += 1
                    if progress[0] % 10 == 0 or progress[0] == count:
                        print(
                            f"Modèle : {progress[0]}/{count} fragments vérifiés en taille",
                            flush=True,
                        )

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(download, range(count)))
            staged = target / (WEIGHTS_FILE + ".verified")
            digest = hashlib.sha256()
            with staged.open("wb") as output:
                for index in range(count):
                    with (parts / f"{index:05d}").open("rb") as source:
                        while block := source.read(CHUNK):
                            digest.update(block)
                            output.write(block)
            if digest.hexdigest() != expected:
                raise RuntimeError(
                    "Intégrité SHA256 du modèle incorrecte ; modèle non publié."
                )
            staged.replace(target / WEIGHTS_FILE)
            manifest = target / "memora-model.json.tmp"
            manifest.write_text(json.dumps(metadata, indent=2) + "\n")
            manifest.replace(target / "memora-model.json")
            for part in parts.iterdir():
                part.unlink()
            parts.rmdir()
    except httpx.HTTPError as error:
        # HTTP errors may contain signed redirect URLs; never print their text.
        raise RuntimeError(
            f"Téléchargement officiel interrompu ({type(error).__name__}), reprise possible."
        ) from None
    return metadata


def run(target, check_only=False):
    target = Path(target).expanduser().resolve()
    if check_only or (target / "memora-model.json").exists():
        metadata = verify_local(target)
        print(
            "Modèle MLX épinglé déjà présent : SHA256 complet vérifié, aucun fichier réécrit ni téléchargement.",
            flush=True,
        )
        return metadata
    metadata = download_pinned(target)
    print(
        f"Modèle MLX épinglé disponible, SHA256 officiel vérifié ; provenance {UPSTREAM_LICENSE} enregistrée.",
        flush=True,
    )
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Offline full-SHA check; no creation, write or download",
    )
    args = parser.parse_args(argv)
    target = Path(
        os.environ.get(
            "MEMORA_MLX_MODEL_PATH", ROOT / ".memora/models/mlx-large-v3-turbo"
        )
    )
    try:
        run(target, check_only=args.check_only)
    except (RuntimeError, OSError, ValueError, TypeError) as error:
        print(
            str(error)
            if isinstance(error, RuntimeError)
            else f"Installation MLX non vérifiée ({type(error).__name__}) ; aucun modèle validé remplacé.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
