"""Offline neural voice clustering; anonymous labels never establish identity.

Resemblyzer Apache-2.0 learned embeddings + existing Silero VAD, CPU only.
This baseline does not detect/separate simultaneous speakers. No network calls.
"""

import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import threading
from pathlib import Path
from contextlib import contextmanager

import numpy as np

_RATE = 16000
_WINDOW_SECONDS = 1.6
_HOP_SECONDS = 0.4
_CLUSTER_DISTANCE = 0.30
_LOCK = threading.Lock()
_UNKNOWN = "Intervenant non identifié"
_MODEL_SHA256 = "39373b86598fa3da9fcddee6142382efe09777e8d37dc9c0561f41f0070f134e"


class DiarizationError(ValueError):
    """Safe operator-facing failure without paths, audio text or secrets."""


def model_dir():
    return Path(
        os.environ.get(
            "MEMORA_DIARIZATION_MODEL_DIR",
            Path(__file__).resolve().parents[3] / ".memora/models/resemblyzer-0.1.4",
        )
    )


def availability():
    if importlib.util.find_spec("resemblyzer") is None:
        return {
            "available": False,
            "reason": "Le moteur local de séparation des voix n’est pas installé.",
        }
    if importlib.metadata.version("Resemblyzer") != "0.1.4":
        return {
            "available": False,
            "reason": "La version du moteur local de séparation des voix n’est pas compatible.",
        }
    folder = model_dir()
    try:
        manifest = json.loads((folder / "manifest.json").read_text())
        ready = (
            manifest.get("package_version") == "0.1.4"
            and manifest.get("sha256") == _MODEL_SHA256
            and (folder / "pretrained.pt").stat().st_size == manifest["bytes"]
        )
    except (OSError, ValueError, KeyError, TypeError):
        ready = False
    return {
        "available": bool(ready),
        "reason": ""
        if ready
        else "Les poids locaux de séparation des voix doivent être préparés et vérifiés.",
    }


def available():
    return availability()["available"]


def _verified_weights():
    state = availability()
    if not state["available"]:
        raise DiarizationError(state["reason"])
    folder = model_dir()
    weights = folder / "pretrained.pt"
    manifest = json.loads((folder / "manifest.json").read_text())
    digest = hashlib.sha256(weights.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise DiarizationError(
            "L’intégrité des poids locaux de séparation des voix est invalide."
        )
    return weights, digest


def _decode(path):
    from faster_whisper.audio import decode_audio

    return decode_audio(str(path), sampling_rate=_RATE)


def _regions(audio):
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    return get_speech_timestamps(
        audio,
        vad_options=VadOptions(min_silence_duration_ms=180, speech_pad_ms=0),
        sampling_rate=_RATE,
    )


def _cells(regions):
    hop = int(_HOP_SECONDS * _RATE)
    for region in regions:
        for start in range(region["start"], region["end"], hop):
            end = min(start + hop, region["end"])
            center = (start + end) // 2
            context_start = max(
                region["start"], center - int(_WINDOW_SECONDS * _RATE / 2)
            )
            context_end = min(
                region["end"], context_start + int(_WINDOW_SECONDS * _RATE)
            )
            context_start = max(
                region["start"], context_end - int(_WINDOW_SECONDS * _RATE)
            )
            yield start, end, context_start, context_end


def _cluster(embeddings, num_speakers=None, max_speakers=8):
    """Bound quadratic clustering to600 evenly distributed anchors, then assign."""
    from scipy.cluster.hierarchy import cut_tree, fcluster, linkage
    from scipy.spatial.distance import pdist

    values = np.asarray(embeddings, dtype=np.float64)
    values /= np.maximum(np.linalg.norm(values, axis=1, keepdims=True), 1e-12)
    if len(values) == 1:
        return np.zeros(1, dtype=int), np.ones(1), np.ones(1), 1
    anchors = values[
        np.unique(np.linspace(0, len(values) - 1, min(600, len(values)), dtype=int))
    ]
    tree = linkage(pdist(anchors, metric="cosine"), method="average")
    if num_speakers is not None:
        count = min(num_speakers, len(anchors))
        labels = cut_tree(tree, n_clusters=[count]).ravel()
    else:
        labels = fcluster(tree, t=_CLUSTER_DISTANCE, criterion="distance") - 1
    groups = sorted(set(labels))
    if len(groups) > max_speakers:
        raise DiarizationError(
            "Trop de groupes vocaux incertains ont été détectés ; vérifiez l’audio ou précisez le nombre d’intervenants."
        )
    centers = np.stack([anchors[labels == group].mean(axis=0) for group in groups])
    centers /= np.maximum(np.linalg.norm(centers, axis=1, keepdims=True), 1e-12)
    scores = values @ centers.T
    assigned = np.argmax(scores, axis=1)
    similarity = scores[np.arange(len(values)), assigned]
    if len(groups) > 1:
        sorted_scores = np.sort(scores, axis=1)
        margin = sorted_scores[:, -1] - sorted_scores[:, -2]
    else:
        margin = np.ones(len(values))
    return assigned, similarity, margin, len(groups)


def assign_speakers(segments, turns, provenance):
    """Preserve source IDs/times/text; abstain on mixed or insufficient coverage."""
    output = []
    for segment in segments:
        copied = dict(segment)
        start, end = float(segment["start"]), float(segment["end"])
        coverage = {}
        uncertain = False
        for turn in turns:
            amount = max(0.0, min(end, turn["end"]) - max(start, turn["start"]))
            if amount and turn.get("speaker_id"):
                ident = turn["speaker_id"]
                coverage[ident] = coverage.get(ident, 0.0) + amount
                uncertain |= bool(turn.get("uncertain"))
        ordered = sorted(coverage, key=coverage.get, reverse=True)
        total = sum(coverage.values())
        winner = ordered[0] if ordered else None
        fraction = coverage.get(winner, 0) / max(total, 1e-9)
        temporal_coverage = total / max(end - start, 1e-9)
        accepted = bool(
            winner
            and len(ordered) == 1
            and fraction >= 0.75
            and temporal_coverage >= 0.35
            and not uncertain
        )
        copied.update(
            speaker=f"Intervenant {int(winner.rsplit('_', 1)[1]) + 1}"
            if accepted
            else _UNKNOWN,
            speaker_id=winner if accepted else None,
            speaker_confidence=None,
            speaker_uncertain=not accepted,
            speaker_provenance=dict(provenance),
            speaker_candidates=[
                {
                    "speaker_id": ident,
                    "speech_fraction": round(coverage[ident] / max(total, 1e-9), 4),
                }
                for ident in ordered
            ],
        )
        output.append(copied)
    return output


@contextmanager
def _cpu_threads():
    """Process-global PyTorch knob, temporarily bounded under heavy-call locks."""
    import torch

    try:
        count = int(os.environ.get("MEMORA_DIARIZATION_CPU_THREADS", "2"))
    except ValueError:
        raise DiarizationError(
            "Le nombre de threads CPU doit être un entier entre1 et8."
        ) from None
    if not 1 <= count <= 8:
        raise DiarizationError("Le nombre de threads CPU doit être compris entre1 et8.")
    previous = torch.get_num_threads()
    torch.set_num_threads(count)
    try:
        yield count
    finally:
        torch.set_num_threads(previous)


def diarize(audio_path, segments, *, num_speakers=None, max_speakers=8):
    """Return {segments, turns, metadata}; caller serializes shared heavy engines.

    Neutral labels are ordered by first acoustic occurrence in this file, not
    globally stable people IDs. ASR text/timestamps are never changed or split.
    """
    if not 1 <= max_speakers <= 32 or (
        num_speakers is not None and not 1 <= num_speakers <= max_speakers
    ):
        raise DiarizationError(
            "Le nombre d’intervenants doit être compris entre1 et32."
        )
    with _LOCK:
        weights, digest = _verified_weights()
        audio = _decode(audio_path)
        if len(audio) > 2 * 3600 * _RATE:
            raise DiarizationError(
                "La séparation locale des voix est limitée à deux heures par traitement."
            )
        cells = list(_cells(_regions(audio)))
        metadata = {
            "engine": "resemblyzer-silero-ahc-v1",
            "package_version": "0.1.4",
            "model_sha256": digest,
            "device": "cpu",
            "confidence_calibrated": False,
            "overlap_supported": False,
            "window_seconds": _WINDOW_SECONDS,
            "hop_seconds": _HOP_SECONDS,
            "warnings": [
                "Les étiquettes distinguent des groupes de voix, pas des identités. Les paroles simultanées ne sont pas séparées.",
                "Les voix proches, passages courts et bruits peuvent entraîner fusion ou fragmentation ; vérification humaine nécessaire.",
            ],
        }
        provenance = {
            key: metadata[key] for key in ("engine", "package_version", "model_sha256")
        }
        if not cells:
            metadata["speaker_count"] = 0
            return {
                "segments": assign_speakers(segments, [], provenance),
                "turns": [],
                "metadata": metadata,
            }
        from resemblyzer import VoiceEncoder
        from resemblyzer.audio import normalize_volume

        with _cpu_threads() as thread_count:
            metadata["cpu_threads"] = thread_count
            encoder = VoiceEncoder(device="cpu", verbose=False, weights_fpath=weights)
            embeddings, included = [], []
            try:
                for cell in cells:
                    _, _, first, last = cell
                    if last - first < int(0.55 * _RATE):
                        continue
                    waveform = np.asarray(audio[first:last], dtype=np.float32)
                    waveform = normalize_volume(waveform, -30, increase_only=True)
                    vector = encoder.embed_utterance(waveform)
                    if not np.isfinite(vector).all():
                        continue
                    embeddings.append(vector)
                    included.append(cell)
            finally:
                del encoder
                gc.collect()
        if not embeddings:
            metadata["speaker_count"] = 0
            return {
                "segments": assign_speakers(segments, [], provenance),
                "turns": [],
                "metadata": metadata,
            }
        labels, similarities, margins, count = _cluster(
            embeddings, num_speakers, max_speakers
        )
        stable = {}
        turns = []
        for cell, label, similarity, margin in zip(
            included, labels, similarities, margins, strict=True
        ):
            if int(label) not in stable:
                stable[int(label)] = f"SPEAKER_{len(stable):02d}"
            uncertain = bool(similarity < 0.65 or margin < 0.025)
            ident = None if uncertain else stable[int(label)]
            turn = {
                "start": round(cell[0] / _RATE, 4),
                "end": round(cell[1] / _RATE, 4),
                "speaker_id": ident,
                "speaker": f"Intervenant {int(ident.rsplit('_', 1)[1]) + 1}"
                if ident
                else _UNKNOWN,
                "uncertain": uncertain,
                "similarity": round(float(similarity), 4),
                "confidence": None,
            }
            if (
                turns
                and turns[-1]["speaker_id"] == ident
                and abs(turns[-1]["end"] - turn["start"]) < 0.002
                and turns[-1]["uncertain"] == uncertain
            ):
                turns[-1]["end"] = turn["end"]
                turns[-1]["similarity"] = min(
                    turns[-1]["similarity"], turn["similarity"]
                )
            else:
                turns.append(turn)
        metadata["speaker_count"] = count
        metadata["anchor_clustering_limit"] = 600
        return {
            "segments": assign_speakers(segments, turns, provenance),
            "turns": turns,
            "metadata": metadata,
        }
