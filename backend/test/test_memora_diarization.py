"""Offline diarization contracts and clustering tests, not neural-quality claims."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from api.memora import diarization as d


def segment(start=0, end=2):
    return dict(
        id="s1",
        start=start,
        end=end,
        text="Texte synthétique.",
        speaker="Ancien",
        uncertain=False,
    )


def test_availability_without_package_is_safe(monkeypatch):
    monkeypatch.setattr(d.importlib.util, "find_spec", lambda name: None)
    assert d.available() is False
    assert "installé" in d.availability()["reason"]


def test_integrity_failure_does_not_expose_local_path(tmp_path, monkeypatch):
    expected = hashlib.sha256(b"correct").hexdigest()
    (tmp_path / "pretrained.pt").write_bytes(b"incorre")
    (tmp_path / "manifest.json").write_text(
        json.dumps(dict(package_version="0.1.4", sha256=expected, bytes=7))
    )
    monkeypatch.setattr(d, "model_dir", lambda: tmp_path)
    monkeypatch.setattr(d, "_MODEL_SHA256", expected)
    assert d.available()
    with pytest.raises(d.DiarizationError, match="intégrité") as caught:
        d._verified_weights()
    assert str(tmp_path) not in str(caught.value)


def test_cells_preserve_source_offsets_and_silence_gaps():
    cells = list(d._cells([dict(start=16000, end=48000), dict(start=80000, end=96000)]))
    assert cells[0][0] == 16000 and cells[-1][1] == 96000
    assert all(a < b and c < e for a, b, c, e in cells)
    assert not any(a < 80000 and b > 48000 for a, b, _, _ in cells)


def test_neural_vector_clustering_follows_voice_similarity_not_alternation():
    vectors = np.array(
        [[1, 0, 0], [1, 0.01, 0], [0, 1, 0], [0, 1, 0.01], [1, 0, 0.01], [0, 1, 0]]
    )
    labels, similarities, margins, count = d._cluster(vectors)
    assert count == 2
    assert labels[0] == labels[1] == labels[4]
    assert labels[2] == labels[3] == labels[5]
    assert labels[0] != labels[2]
    assert np.all(similarities > 0.99) and np.all(margins > 0.9)


def test_known_count_is_explicit_not_inferred_identity():
    labels, _, _, count = d._cluster(
        np.array([[1, 0], [0.8, 0.2], [0, 1]]), num_speakers=2
    )
    assert count == 2 and len(labels) == 3


def test_assignment_preserves_text_times_and_abstains_on_mixed_speakers():
    original = segment()
    turns = [
        dict(start=0, end=1, speaker_id="SPEAKER_00", uncertain=False),
        dict(start=1, end=2, speaker_id="SPEAKER_01", uncertain=False),
    ]
    result = d.assign_speakers([original], turns, dict(engine="test"))[0]
    assert result["speaker_id"] is None and result["speaker_uncertain"]
    assert result["speaker_confidence"] is None
    for key in ("id", "start", "end", "text", "uncertain"):
        assert result[key] == original[key]
    assert original["speaker"] == "Ancien"


def test_assignment_neutral_label_and_no_calibrated_probability():
    result = d.assign_speakers(
        [segment()],
        [dict(start=0.1, end=1.9, speaker_id="SPEAKER_00", uncertain=False)],
        dict(engine="test"),
    )[0]
    assert result["speaker"] == "Intervenant 1" and result["speaker_id"] == "SPEAKER_00"
    assert result["speaker_confidence"] is None and not result["speaker_uncertain"]
    assert result["speaker_provenance"] == dict(engine="test")


def test_silence_does_not_load_encoder_or_invent_speaker(monkeypatch):
    monkeypatch.setattr(d, "_verified_weights", lambda: (Path("/unused"), "a" * 64))
    monkeypatch.setattr(d, "_decode", lambda path: np.zeros(16000, dtype=np.float32))
    monkeypatch.setattr(d, "_regions", lambda audio: [])
    result = d.diarize(Path("/synthetic"), [segment(0, 1)])
    assert result["turns"] == [] and result["metadata"]["speaker_count"] == 0
    assert result["segments"][0]["speaker_id"] is None
    assert result["metadata"]["overlap_supported"] is False


def test_speaker_count_bounds_before_any_io():
    with pytest.raises(d.DiarizationError):
        d.diarize(Path("/unused"), [], num_speakers=0)
    with pytest.raises(d.DiarizationError):
        d.diarize(Path("/unused"), [], max_speakers=33)


def test_even_ninety_percent_majority_abstains_if_two_voices_present():
    turns = [
        dict(start=0, end=1.8, speaker_id="SPEAKER_00", uncertain=False),
        dict(start=1.8, end=2, speaker_id="SPEAKER_01", uncertain=False),
    ]
    result = d.assign_speakers([segment()], turns, {})[0]
    assert result["speaker_id"] is None and result["speaker_uncertain"]
    assert len(result["speaker_candidates"]) == 2


@pytest.mark.parametrize("fails", [False, True])
def test_cpu_thread_bound_and_restoration_even_on_failure(monkeypatch, fails):
    import torch

    state = {"threads": 7}
    monkeypatch.setattr(torch, "get_num_threads", lambda: state["threads"])
    monkeypatch.setattr(
        torch, "set_num_threads", lambda count: state.update(threads=count)
    )
    monkeypatch.delenv("MEMORA_DIARIZATION_CPU_THREADS", raising=False)

    def run():
        with d._cpu_threads() as count:
            assert count == 2 and state["threads"] == 2
            if fails:
                raise RuntimeError("synthetic failure")

    if fails:
        with pytest.raises(RuntimeError):
            run()
    else:
        run()
    assert state["threads"] == 7


@pytest.mark.parametrize("value", ["0", "9", "invalid"])
def test_cpu_thread_configuration_bounds(monkeypatch, value):
    monkeypatch.setenv("MEMORA_DIARIZATION_CPU_THREADS", value)
    with pytest.raises(d.DiarizationError):
        with d._cpu_threads():
            pytest.fail("Invalid thread setting must not run model")
