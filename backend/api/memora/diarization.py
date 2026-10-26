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
_VALIDATION_WINDOW_SECONDS = 3.2
_HOP_SECONDS = 0.4
_CLUSTER_DISTANCE = 0.30
_LOCK = threading.Lock()
_UNKNOWN = "Intervenant non identifié"
_MODEL_SHA256 = "39373b86598fa3da9fcddee6142382efe09777e8d37dc9c0561f41f0070f134e"


def engine_name():
    return os.environ.get("MEMORA_DIARIZATION_ENGINE", "resemblyzer")


class DiarizationError(ValueError):
    """Safe operator-facing failure without paths, audio text or secrets."""


class UncertainSpeakerCount(DiarizationError):
    """Acoustic grouping is unstable; a separately verified strategy may retry."""


def model_dir():
    return Path(
        os.environ.get(
            "MEMORA_DIARIZATION_MODEL_DIR",
            Path(__file__).resolve().parents[3] / ".memora/models/resemblyzer-0.1.4",
        )
    )


def availability():
    from . import inference_bridge

    if inference_bridge.configured():
        return inference_bridge.availability()
    if engine_name() in {"ecapa-tdnn", "ecapa-segmented"}:
        from . import diarization_ecapa

        if engine_name() == "ecapa-segmented":
            from . import diarization_segmented

            try:
                diarization_segmented.verified_segmentation()
            except DiarizationError as exc:
                return {"available": False, "reason": str(exc)}
        return diarization_ecapa.availability()
    if engine_name() != "resemblyzer":
        return {
            "available": False,
            "reason": "Le moteur de séparation configuré n’est pas reconnu.",
        }
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
    if engine_name() in {"ecapa-tdnn", "ecapa-segmented"}:
        from . import diarization_ecapa

        try:
            return diarization_ecapa.verified_weights()
        except ValueError as exc:
            raise DiarizationError(str(exc)) from None
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


def _cells(regions, window_seconds=None):
    window_seconds = _WINDOW_SECONDS if window_seconds is None else window_seconds
    hop = int(_HOP_SECONDS * _RATE)
    for region in regions:
        for start in range(region["start"], region["end"], hop):
            end = min(start + hop, region["end"])
            center = (start + end) // 2
            context_start = max(
                region["start"], center - int(window_seconds * _RATE / 2)
            )
            context_end = min(
                region["end"], context_start + int(window_seconds * _RATE)
            )
            context_start = max(
                region["start"], context_end - int(window_seconds * _RATE)
            )
            yield start, end, context_start, context_end


def _cluster(embeddings, num_speakers=None, max_speakers=8, distance=None):
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
        labels = (
            fcluster(
                tree,
                t=_CLUSTER_DISTANCE if distance is None else distance,
                criterion="distance",
            )
            - 1
        )
    groups = sorted(set(labels))
    if len(groups) > max_speakers:
        raise UncertainSpeakerCount(
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


def _embed_cells(encoder, audio, cells, cache):
    """Reuse identical contexts without retaining audio beyond this call."""
    embeddings, included = [], []
    for cell in cells:
        _, _, first, last = cell
        if last - first < int(0.55 * _RATE):
            continue
        key = (first, last)
        if key not in cache:
            waveform = np.asarray(audio[first:last], dtype=np.float32)
            if getattr(encoder, "normalize_volume", True):
                from resemblyzer.audio import normalize_volume

                waveform = normalize_volume(waveform, -30, increase_only=True)
            cache[key] = encoder.embed_utterance(waveform)
        vector = cache[key]
        if np.isfinite(vector).all():
            embeddings.append(vector)
            included.append(cell)
    return embeddings, included


def _validate_automatic_count(
    encoder,
    audio,
    regions,
    count,
    cache,
    max_speakers=8,
    *,
    window_seconds=None,
    distance=None,
):
    """Disagreement is insufficient evidence for numbered voices, never a merge.

    Alternative contexts are a veto only: they cannot replace the primary
    assignments or establish that a disputed recording contains one person.
    """
    if count <= 1:
        return
    embeddings, _ = _embed_cells(
        encoder,
        audio,
        _cells(
            regions,
            _VALIDATION_WINDOW_SECONDS if window_seconds is None else window_seconds,
        ),
        cache,
    )
    if (
        not embeddings
        or _cluster(embeddings, max_speakers=max_speakers, distance=distance)[3]
        != count
    ):
        raise UncertainSpeakerCount(
            "Le nombre d’intervenants est incertain : les comparaisons de voix se contredisent. Précisez le nombre connu pour reprendre la séparation."
        )


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
    from . import inference_bridge

    if inference_bridge.configured():
        try:
            return inference_bridge.diarize(
                audio_path,
                segments,
                num_speakers=num_speakers,
                max_speakers=max_speakers,
            )
        except inference_bridge.BridgeError as exc:
            raise DiarizationError(str(exc)) from None
    if not 1 <= max_speakers <= 32 or (
        num_speakers is not None and not 1 <= num_speakers <= max_speakers
    ):
        raise DiarizationError(
            "Le nombre d’intervenants doit être compris entre1 et32."
        )
    with _LOCK:
        segmented = engine_name() == "ecapa-segmented"
        if segmented:
            from . import diarization_segmented

            # Missing or corrupt assets must fail, never trigger a silent fallback.
            diarization_segmented.verified_segmentation()
        try:
            result = _diarize_embeddings(
                audio_path,
                segments,
                num_speakers=num_speakers,
                max_speakers=max_speakers,
                ecapa=engine_name() in {"ecapa-tdnn", "ecapa-segmented"},
            )
        except UncertainSpeakerCount:
            if not segmented:
                raise
            result = diarization_segmented.diarize(
                audio_path,
                segments,
                num_speakers=num_speakers,
                max_speakers=max_speakers,
            )
            result["metadata"]["recovery_reason"] = "unstable_voice_clustering"
        if segmented:
            result["metadata"]["strategy"] = "validated-ecapa-then-segmentation-v1"
        return result


def _diarize_embeddings(
    audio_path, segments, *, num_speakers=None, max_speakers=8, ecapa=False
):
    weights, digest = _verified_weights()
    window_seconds = 3.2 if ecapa else _WINDOW_SECONDS
    validation_window = 1.6 if ecapa else _VALIDATION_WINDOW_SECONDS
    distance = 0.55 if ecapa else _CLUSTER_DISTANCE
    audio = _decode(audio_path)
    if len(audio) > 2 * 3600 * _RATE:
        raise DiarizationError(
            "La séparation locale des voix est limitée à deux heures par traitement."
        )
    regions = _regions(audio)
    cells = list(_cells(regions, window_seconds))
    metadata = {
        "engine": "ecapa-silero-ahc-v1" if ecapa else "resemblyzer-silero-ahc-v2",
        "package_version": "1.1.2" if ecapa else "0.1.4",
        "model_sha256": digest,
        "device": "cpu",
        "confidence_calibrated": False,
        "overlap_supported": False,
        "window_seconds": window_seconds,
        "cluster_distance": distance,
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
    with _cpu_threads() as thread_count:
        metadata["cpu_threads"] = thread_count
        if ecapa:
            from .diarization_ecapa import Encoder

            encoder = Encoder(weights)
        else:
            from resemblyzer import VoiceEncoder

            encoder = VoiceEncoder(device="cpu", verbose=False, weights_fpath=weights)
        embeddings, included = [], []
        try:
            cache = {}
            embeddings, included = _embed_cells(encoder, audio, cells, cache)
            if embeddings:
                labels, similarities, margins, count = _cluster(
                    embeddings, num_speakers, max_speakers, distance
                )
                if num_speakers is None:
                    _validate_automatic_count(
                        encoder,
                        audio,
                        regions,
                        count,
                        cache,
                        max_speakers,
                        window_seconds=validation_window,
                        distance=distance,
                    )
                metadata["count_policy"] = (
                    "explicit" if num_speakers is not None else "multiscale-veto-v1"
                )
                metadata["count_validation_windows"] = (
                    [window_seconds, validation_window]
                    if num_speakers is None and count > 1
                    else []
                )
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
            turns[-1]["similarity"] = min(turns[-1]["similarity"], turn["similarity"])
        else:
            turns.append(turn)
    metadata["speaker_count"] = count
    metadata["anchor_clustering_limit"] = 600
    return {
        "segments": assign_speakers(segments, turns, provenance),
        "turns": turns,
        "metadata": metadata,
    }
