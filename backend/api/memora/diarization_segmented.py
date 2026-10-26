"""Local overlap-aware segmentation followed by pinned ECAPA voice clustering.

The caller owns the diarization lock. This module never downloads assets or
changes ASR source boundaries. Joint voice activity is not audio source separation.
"""

import hashlib
import os
from pathlib import Path

import numpy as np

from . import diarization as d
from . import diarization_ecapa as e

SEGMENTATION_SHA256 = "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079"
SEGMENTATION_BYTES = 5992913
RATE = 16000
WINDOW = 160000
HOP = 80000
FRAME_SHIFT = 270
FRAME_CENTER = 495
FRAME_COUNT = (WINDOW - 991) // FRAME_SHIFT + 1
GRID = 320
MAX_SAMPLES = 2 * 3600 * RATE
MAX_WINDOWS = 1500
MAX_EMBEDDINGS = 4500
CLUSTER_DISTANCE = 0.45
VALIDATION_DISTANCE = 0.55
POWERSET = np.array(
    [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 0], [1, 0, 1], [0, 1, 1]],
    dtype=bool,
)


def verified_segmentation():
    """Verify the pinned local segmentation asset, with no inference download."""
    folder = Path(
        os.environ.get(
            "MEMORA_SEGMENTATION_MODEL_DIR",
            Path(__file__).resolve().parents[3] / ".memora/models/segmentation-3.0",
        )
    )
    path = folder / "model.onnx"
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size != SEGMENTATION_BYTES
    ):
        raise d.DiarizationError(
            "Le modèle local de séparation des voix doit être préparé."
        )
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != SEGMENTATION_SHA256:
            raise d.DiarizationError(
                "L’intégrité du modèle de segmentation est invalide."
            )
    return path, SEGMENTATION_SHA256


def decode_activity(probabilities):
    """Decode the seven powerset classes into three joint local voice tracks."""
    values = np.asarray(probabilities)
    if values.shape != (1, FRAME_COUNT, 7) or not np.isfinite(values).all():
        raise d.DiarizationError(
            "La segmentation locale a renvoyé un résultat invalide."
        )
    return POWERSET[values[0].argmax(axis=1)]


def exclusive_speech(signal, valid, activity, local):
    """Concatenate only single-voice 270-sample cells, excluding padded audio."""
    if activity.shape != (FRAME_COUNT, 3) or not 0 <= local < 3:
        raise d.DiarizationError("Le masque de voix est invalide.")
    centers = np.arange(FRAME_COUNT) * FRAME_SHIFT + FRAME_CENTER
    mask = activity[:, local] & (activity.sum(axis=1) == 1) & (centers < valid)
    pieces = [
        signal[max(0, int(center - 135)) : min(valid, int(center + 135))]
        for center in centers[mask]
    ]
    return np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.float32)


def infer_windows(session, encoder, audio):
    """Bounded overlapping windows; keep silent windows in the coverage ledger."""
    windows, embeddings = [], []
    for start in range(0, len(audio), HOP):
        valid = min(WINDOW, len(audio) - start)
        if valid < RATE // 2:
            break
        if len(windows) >= MAX_WINDOWS:
            raise d.DiarizationError("La limite de fenêtres audio a été atteinte.")
        signal = np.pad(audio[start : start + valid], (0, WINDOW - valid))
        try:
            probabilities = session.run(None, {"x": signal[None, None, :]})[0]
        except Exception as exc:
            raise d.DiarizationError("La segmentation locale a échoué.") from exc
        active = decode_activity(probabilities)
        streams = {}
        for local in range(3):
            speech = exclusive_speech(signal, valid, active, local)
            if len(speech) < RATE:
                continue
            if len(embeddings) >= MAX_EMBEDDINGS:
                raise d.DiarizationError(
                    "La limite d’empreintes vocales a été atteinte."
                )
            embedding = np.asarray(encoder.embed_utterance(speech), dtype=np.float32)
            if (
                embedding.ndim != 1
                or not embedding.size
                or not np.isfinite(embedding).all()
                or np.linalg.norm(embedding) <= 1e-9
            ):
                raise d.DiarizationError("Une empreinte vocale locale est invalide.")
            streams[local] = len(embeddings)
            embeddings.append(embedding)
        windows.append((start, valid, active, streams))
    return windows, embeddings


def project_turns(windows, labels, count, samples):
    """Project local activity onto a 20 ms grid, one vote per window and voice."""
    frames = (samples + GRID - 1) // GRID
    votes = np.zeros((count, frames), dtype=np.float32)
    denominator = np.zeros(frames, dtype=np.float32)
    for start, valid, active, streams in windows:
        if (
            start < 0
            or valid <= 0
            or start + valid > samples
            or active.shape != (FRAME_COUNT, 3)
        ):
            raise d.DiarizationError("Les limites de segmentation sont invalides.")
        grid = np.arange(start // GRID, min(frames, (start + valid + GRID - 1) // GRID))
        nearest = np.clip(
            np.rint((grid * GRID - start - FRAME_CENTER) / FRAME_SHIFT).astype(int),
            0,
            FRAME_COUNT - 1,
        )
        denominator[grid] += 1
        combined = {}
        for local, index in streams.items():
            if not 0 <= index < len(labels) or not 0 <= int(labels[index]) < count:
                raise d.DiarizationError("Les groupes de voix sont invalides.")
            group = int(labels[index])
            combined[group] = (
                combined.get(group, np.zeros(len(grid), dtype=bool))
                | active[nearest, local]
            )
        for group, mask in combined.items():
            votes[group, grid] += mask
    activity = (denominator[None, :] > 0) & (votes / np.maximum(denominator, 1) >= 0.5)
    turns = []
    for group in range(count):
        changes = np.diff(np.pad(activity[group].astype(np.int8), (1, 1)))
        for first, last in zip(
            np.flatnonzero(changes == 1), np.flatnonzero(changes == -1), strict=True
        ):
            if (last - first) * GRID < RATE // 10:
                continue
            turns.append(
                {
                    "start": first * GRID / RATE,
                    "end": min(last * GRID / RATE, samples / RATE),
                    "speaker_id": group,
                }
            )
    # Cluster numbers are arbitrary. Assign neutral names by first occurrence.
    turns.sort(key=lambda turn: (turn["start"], turn["speaker_id"], turn["end"]))
    names = {}
    for turn in turns:
        group = turn["speaker_id"]
        names.setdefault(group, f"speaker_{len(names):02d}")
        turn["speaker_id"] = names[group]
    return turns, len(names)


def diarize(audio_path, segments, *, num_speakers=None, max_speakers=8):
    """Infer local turns and assign them conservatively to unchanged ASR segments."""
    if (
        isinstance(max_speakers, bool)
        or not isinstance(max_speakers, int)
        or not 1 <= max_speakers <= 8
        or (
            num_speakers is not None
            and (
                isinstance(num_speakers, bool)
                or not isinstance(num_speakers, int)
                or not 1 <= num_speakers <= max_speakers
            )
        )
    ):
        raise d.DiarizationError(
            "Le nombre d’intervenants doit être compris entre1 et8."
        )
    for segment in segments:
        start, end = segment.get("start"), segment.get("end")
        if (
            not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
            or not np.isfinite([start, end]).all()
            or start < 0
            or end < start
        ):
            raise d.DiarizationError("Les horodatages de transcription sont invalides.")
    path, segmentation_hash = verified_segmentation()
    weights, embedding_hash = e.verified_weights()
    audio = np.asarray(d._decode(audio_path), dtype=np.float32)
    if audio.ndim != 1 or not np.isfinite(audio).all() or len(audio) > MAX_SAMPLES:
        raise d.DiarizationError("L’audio doit être valide et limité à deux heures.")
    import onnxruntime as ort

    ort.disable_telemetry_events()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    try:
        session = ort.InferenceSession(
            str(path), options, providers=["CPUExecutionProvider"]
        )
    except Exception as exc:
        raise d.DiarizationError(
            "Le moteur local de segmentation est indisponible."
        ) from exc
    with d._cpu_threads() as threads:
        encoder = e.Encoder(weights)
        try:
            windows, embeddings = infer_windows(session, encoder, audio)
        finally:
            del encoder
    if embeddings:
        labels, _, _, count = d._cluster(
            embeddings, num_speakers, max_speakers, CLUSTER_DISTANCE
        )
        if num_speakers is None and count > 1:
            comparison = d._cluster(
                embeddings, None, max_speakers, VALIDATION_DISTANCE
            )[3]
            if comparison != count:
                raise d.UncertainSpeakerCount(
                    "Le nombre d’intervenants reste instable après segmentation. "
                    "Précisez le nombre connu ou vérifiez les passages avec l’audio."
                )
        turns, count = project_turns(windows, labels, count, len(audio))
    else:
        turns, count = [], 0
    metadata = {
        "engine": "pyannote-onnx-ecapa-ahc-v1",
        "package_version": "1",
        "model_sha256": segmentation_hash,
        "embedding_model_sha256": embedding_hash,
        "speaker_count": count,
        "device": "cpu",
        "cpu_threads": threads,
        "confidence_calibrated": False,
        "overlap_supported": True,
        "window_seconds": WINDOW / RATE,
        "hop_seconds": HOP / RATE,
        "cluster_distance": CLUSTER_DISTANCE,
        "count_policy": "explicit"
        if num_speakers is not None
        else "segmented-stability-v1",
        "warnings": [
            "Les étiquettes regroupent des voix, sans identifier les personnes.",
            "Les paroles simultanées sont détectées ; les pistes audio ne sont pas séparées.",
            "Les voix proches et les prises de parole courtes peuvent rester sans attribution fiable.",
        ],
    }
    provenance = {
        key: metadata[key]
        for key in (
            "engine",
            "package_version",
            "model_sha256",
            "embedding_model_sha256",
        )
    }
    return {
        "segments": d.assign_speakers(segments, turns, provenance),
        "turns": turns,
        "metadata": metadata,
    }
