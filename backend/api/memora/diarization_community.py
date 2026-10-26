"""Local Community-1 CoreML/VBx recovery; no network or downloads at inference."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from . import diarization as d

ROOT = Path(__file__).resolve().parents[3]
# Pinned installer manifest is filled from the reviewed distribution resource.
MANIFEST_SHA256 = "55fd59da5370174e59be4be021586fa216a0d0e58bee77efcd081413aa7accf6"
MAX_SAMPLES = 2 * 3600 * 16000


def enabled():
    return os.environ.get("MEMORA_DIARIZATION_RECOVERY", "") == "community-coreml"


def assets():
    models = Path(
        os.environ.get(
            "MEMORA_COMMUNITY_MODEL_DIR", ROOT / ".memora/models/community-coreml"
        )
    )
    tooling = Path(
        os.environ.get(
            "MEMORA_COMMUNITY_TOOL_DIR", ROOT / ".memora/tooling/community-coreml"
        )
    )
    try:
        manifest_path = models / "manifest.json"
        if models.is_symlink() or tooling.is_symlink() or manifest_path.is_symlink():
            raise ValueError("Unsafe assets")
        raw = manifest_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
            raise ValueError("Invalid model manifest")
        manifest = json.loads(raw)
        for item in manifest["files"]:
            relative = Path(item["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unsafe model path")
            path = models / relative
            if path.is_symlink() or not path.resolve().is_relative_to(models.resolve()):
                raise ValueError("Unsafe model path")
            if (
                path.stat().st_size != item["bytes"]
                or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]
            ):
                raise ValueError("Corrupt model")
        binary = tooling / "memora-community"
        tool_manifest = tooling / "manifest.json"
        if (
            binary.is_symlink()
            or tool_manifest.is_symlink()
            or not os.access(binary, os.X_OK)
        ):
            raise ValueError("Unsafe executable")
        build = json.loads(tool_manifest.read_text())["binary"]
        if (
            binary.stat().st_size != build["bytes"]
            or hashlib.sha256(binary.read_bytes()).hexdigest() != build["sha256"]
        ):
            raise ValueError("Corrupt executable")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise d.DiarizationError(
            "Le moteur complet de séparation des voix doit être préparé et vérifié."
        ) from exc
    return models, binary


def parse_turns(result, duration, max_speakers):
    if (
        not isinstance(result, dict)
        or not isinstance(result.get("turns"), list)
        or len(result["turns"]) > 50000
    ):
        raise d.DiarizationError("Le moteur complet a renvoyé des passages invalides.")
    valid = []
    for turn in result["turns"]:
        if not isinstance(turn, dict):
            raise d.DiarizationError("Un passage vocal est invalide.")
        first, last, ident = turn.get("start"), turn.get("end"), turn.get("speaker_id")
        if (
            type(first) not in (int, float)
            or type(last) not in (int, float)
            or not np.isfinite([first, last]).all()
            or not 0 <= first < last <= duration + 0.1
            or not isinstance(ident, str)
            or not ident
            or len(ident) > 64
        ):
            raise d.DiarizationError("Les repères vocaux locaux sont invalides.")
        valid.append((first, last, ident))
    turns, labels = [], {}
    for first, last, ident in sorted(valid):
        if ident not in labels:
            labels[ident] = f"SPEAKER_{len(labels):02d}"
        stable = labels[ident]
        turns.append(
            dict(
                start=first,
                end=min(last, duration),
                speaker_id=stable,
                speaker=f"Intervenant {int(stable.rsplit('_', 1)[1]) + 1}",
                uncertain=False,
                confidence=None,
            )
        )
    if (
        type(result.get("speaker_count")) is not int
        or result["speaker_count"] != len(labels)
        or len(labels) > min(max_speakers, 8)
    ):
        raise d.UncertainSpeakerCount(
            "Le nombre de voix dépasse les limites ou ne concorde pas avec les passages."
        )
    return turns, len(labels)


def diarize(path, segments, *, num_speakers=None, max_speakers=8):
    models, binary = assets()
    audio = np.asarray(d._decode(path), dtype=np.float32)
    if (
        audio.ndim != 1
        or not 0 < len(audio) <= MAX_SAMPLES
        or not np.isfinite(audio).all()
    ):
        raise d.DiarizationError("L’audio doit être valide et limité à deux heures.")
    with tempfile.TemporaryDirectory(prefix="memora-speakers-") as folder:
        pcm, output = Path(folder) / "audio.f32", Path(folder) / "result.json"
        audio.astype("<f4").tofile(pcm)
        args = [str(binary), str(models), str(pcm), str(output)]
        if num_speakers is not None:
            if type(num_speakers) is not int or not 1 <= num_speakers <= min(
                max_speakers, 8
            ):
                raise d.DiarizationError(
                    "Le nombre d’intervenants doit être compris entre1 et8."
                )
            args.append(str(num_speakers))
        try:
            # Native diagnostics remain private; never log paths or payloads.
            subprocess.run(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=1800,
            )
            if output.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("Oversized result")
            result = json.loads(output.read_text())
            turns, count = parse_turns(result, len(audio) / 16000, max_speakers)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            if isinstance(exc, d.DiarizationError):
                raise
            raise d.DiarizationError(
                "Le traitement complet des voix a échoué ; la transcription est conservée."
            ) from None
    provenance = dict(
        engine="fluid-community1-coreml-vbx-v1",
        package_version="0.17.7",
        model_sha256=MANIFEST_SHA256,
    )
    return dict(
        segments=d.assign_speakers(segments, turns, provenance),
        turns=turns,
        metadata={
            **provenance,
            "speaker_count": count,
            "device": "coreml",
            "overlap_supported": True,
            "confidence_calibrated": False,
            "count_policy": "explicit"
            if num_speakers is not None
            else "community1-vbx",
            "warnings": [
                "Les étiquettes distinguent des voix, sans identifier les personnes. Vérifiez les prises de parole courtes et simultanées."
            ],
        },
    )
