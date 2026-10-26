"""Synthetic arrays/mocked inference; these tests make no accuracy claims."""

import contextlib
import hashlib
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from api.memora import diarization as d
from api.memora import diarization_segmented as s


def active(local=0):
    result = np.zeros((s.FRAME_COUNT, 3), dtype=bool)
    result[:, local] = True
    return result


def probabilities(kind=1):
    result = np.zeros((1, s.FRAME_COUNT, 7), dtype=np.float32)
    result[:, :, kind] = 1
    return result


def test_powerset_decodes_overlap():
    result = s.decode_activity(probabilities(4))
    assert result[:, :2].all() and not result[:, 2].any()


@pytest.mark.parametrize(
    "values", [np.zeros((1, 20, 7)), np.full((1, s.FRAME_COUNT, 7), np.nan)]
)
def test_invalid_inference_shape_fails(values):
    with pytest.raises(d.DiarizationError):
        s.decode_activity(values)


def test_exclusive_masks_exclude_other_voice_and_padded_samples():
    mask = active()
    mask[0:20, 1] = True
    signal = np.arange(s.WINDOW, dtype=np.float32)
    speech = s.exclusive_speech(signal, 16000, mask, 0)
    assert speech.size > 0
    assert speech.min() >= 20 * 270 + 495 - 135
    assert speech.max() < 16000
    assert s.exclusive_speech(signal, 16000, mask, 2).size == 0


def test_windows_keep_silence_in_denominator_and_ignore_short_embedding():
    session = SimpleNamespace(run=lambda *args: [probabilities(0)])
    encoder = SimpleNamespace(embed_utterance=lambda speech: pytest.fail("No voice"))
    windows, embeddings = s.infer_windows(
        session, encoder, np.zeros(s.HOP + 8000, dtype=np.float32)
    )
    assert len(windows) == 2 and embeddings == []
    assert windows[0][3] == windows[1][3] == {}


def test_invalid_embedding_rejected():
    session = SimpleNamespace(run=lambda *args: [probabilities()])
    encoder = SimpleNamespace(embed_utterance=lambda speech: np.array([np.nan]))
    with pytest.raises(d.DiarizationError, match="empreinte"):
        s.infer_windows(session, encoder, np.zeros(s.WINDOW, dtype=np.float32))


def test_projection_counts_windows_without_embedding():
    # One positive window and two uncovered windows: 1/3 must not pass 0.5.
    windows = [
        (0, 16000, active(), {0: 0}),
        (0, 16000, active(), {}),
        (0, 16000, active(), {}),
    ]
    turns, count = s.project_turns(windows, [0], 1, 16000)
    assert turns == [] and count == 0


def test_overlap_preserved_and_same_cluster_not_double_counted():
    mask = active()
    mask[:, 1] = True
    turns, count = s.project_turns([(0, 16000, mask, {0: 0, 1: 1})], [0, 1], 2, 16000)
    assert count == 2 and {x["speaker_id"] for x in turns} == {
        "speaker_00",
        "speaker_01",
    }
    assert all(x["start"] == 0 and x["end"] == 1 for x in turns)
    # Two streams of same group must be one vote, not 2/3 acceptance.
    turns, _ = s.project_turns(
        [(0, 16000, mask, {0: 0, 1: 1}), (0, 16000, mask, {}), (0, 16000, mask, {})],
        [0, 0],
        1,
        16000,
    )
    assert not turns


def test_labels_follow_first_occurrence_and_turn_bounds():
    turns, count = s.project_turns(
        [(0, 16000, active(), {0: 0}), (16000, 8000, active(), {0: 1})],
        [1, 0],
        2,
        24000,
    )
    assert count == 2
    assert turns == [
        {"start": 0, "end": 1, "speaker_id": "speaker_00"},
        {"start": 1, "end": 1.5, "speaker_id": "speaker_01"},
    ]


def test_invalid_projection_bounds_fail_closed():
    with pytest.raises(d.DiarizationError, match="limites"):
        s.project_turns([(-1, 10, active(), {})], [], 0, 16000)


def test_asset_verified_without_network(tmp_path, monkeypatch):
    data = b"synthetic ONNX"
    (tmp_path / "model.onnx").write_bytes(data)
    monkeypatch.setenv("MEMORA_SEGMENTATION_MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(s, "SEGMENTATION_BYTES", len(data))
    monkeypatch.setattr(s, "SEGMENTATION_SHA256", hashlib.sha256(data).hexdigest())
    assert s.verified_segmentation()[0] == tmp_path / "model.onnx"
    (tmp_path / "model.onnx").write_bytes(b"X" + data[1:])
    with pytest.raises(d.DiarizationError, match="intégrité"):
        s.verified_segmentation()


@pytest.fixture
def inference(monkeypatch):
    monkeypatch.setattr(
        s, "verified_segmentation", lambda: ("model.onnx", "segmentation-sha")
    )
    monkeypatch.setattr(s.e, "verified_weights", lambda: ("weights", "embedding-sha"))
    monkeypatch.setattr(s.d, "_decode", lambda path: np.zeros(16000, dtype=np.float32))
    monkeypatch.setattr(s.d, "_cpu_threads", lambda: contextlib.nullcontext(2))
    monkeypatch.setattr(s.e, "Encoder", lambda path: object())
    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(
            disable_telemetry_events=lambda: None,
            SessionOptions=lambda: SimpleNamespace(),
            InferenceSession=lambda *a, **kw: object(),
        ),
    )
    monkeypatch.setattr(
        s, "infer_windows", lambda *args: ([(0, 16000, active(), {0: 0})], [np.ones(3)])
    )


def test_known_count_forwarded_and_source_immutable(inference, monkeypatch):
    calls = []

    def cluster(values, known, maximum, distance):
        calls.append((known, maximum, distance))
        return [0], [], [], 1

    monkeypatch.setattr(s.d, "_cluster", cluster)
    source = {
        "id": "s1",
        "start": 0,
        "end": 1,
        "text": "Texte synthétique.",
        "speaker": "ancien",
    }
    result = s.diarize("unused", [source], num_speakers=1)
    assert calls == [(1, 8, 0.45)]
    assert source["speaker"] == "ancien"
    assert {k: result["segments"][0][k] for k in ("id", "start", "end", "text")} == {
        k: source[k] for k in ("id", "start", "end", "text")
    }
    assert result["segments"][0]["speaker"] == "Intervenant 1"
    assert result["metadata"]["confidence_calibrated"] is False
    assert result["metadata"]["overlap_supported"] is True


def test_empty_audio_returns_unattributed(inference, monkeypatch):
    monkeypatch.setattr(s.d, "_decode", lambda path: np.zeros(0, dtype=np.float32))
    monkeypatch.setattr(s, "infer_windows", lambda *args: ([], []))
    result = s.diarize("unused", [])
    assert result["turns"] == [] and result["metadata"]["speaker_count"] == 0


def test_inconsistent_segmented_count_abstains_before_publishing(
    inference, monkeypatch
):
    def cluster(values, known, maximum, distance):
        return [0], [], [], 2 if distance == s.CLUSTER_DISTANCE else 1

    monkeypatch.setattr(s.d, "_cluster", cluster)
    source = [{"id": "s1", "start": 0, "end": 1, "text": "Synthetic only"}]
    with pytest.raises(d.UncertainSpeakerCount, match="instable"):
        s.diarize("unused", source)
    assert "speaker_id" not in source[0]


@pytest.mark.parametrize("known", [0, 9, True, 1.2])
def test_invalid_known_count_rejected_before_models(known, monkeypatch):
    monkeypatch.setattr(s, "verified_segmentation", lambda: pytest.fail("No models"))
    with pytest.raises(d.DiarizationError):
        s.diarize("unused", [], num_speakers=known)


@pytest.mark.parametrize("start,end", [(2, 1), (-1, 1), (0, float("nan"))])
def test_invalid_source_timing_rejected(start, end):
    with pytest.raises(d.DiarizationError, match="horodatages"):
        s.diarize("unused", [{"start": start, "end": end}])


def test_embedding_failure_publishes_nothing(inference, monkeypatch):
    def fail(*args):
        raise d.DiarizationError("Synthétique")

    monkeypatch.setattr(s, "infer_windows", fail)
    source = [{"id": "one", "start": 0, "end": 1, "text": "Synthétique"}]
    with pytest.raises(d.DiarizationError):
        s.diarize("unused", source)
    assert source == [{"id": "one", "start": 0, "end": 1, "text": "Synthétique"}]


def test_window_bound_is_enforced(monkeypatch):
    monkeypatch.setattr(s, "MAX_WINDOWS", 0)
    with pytest.raises(d.DiarizationError, match="fenêtres"):
        s.infer_windows(object(), object(), np.zeros(16000, dtype=np.float32))


def test_embedding_bound_is_enforced(monkeypatch):
    monkeypatch.setattr(s, "MAX_EMBEDDINGS", 0)
    session = SimpleNamespace(run=lambda *args: [probabilities()])
    with pytest.raises(d.DiarizationError, match="empreintes"):
        s.infer_windows(session, object(), np.zeros(32000, dtype=np.float32))


def test_session_failure_has_safe_message():
    def fail(*args):
        raise RuntimeError("/sensitive/internal/path")

    with pytest.raises(d.DiarizationError) as result:
        s.infer_windows(
            SimpleNamespace(run=fail), object(), np.zeros(16000, dtype=np.float32)
        )
    assert "/sensitive" not in str(result.value)


def test_audio_limit_rejected_before_inference(inference, monkeypatch):
    monkeypatch.setattr(s, "MAX_SAMPLES", 100)
    with pytest.raises(d.DiarizationError, match="deux heures"):
        s.diarize("unused", [])
