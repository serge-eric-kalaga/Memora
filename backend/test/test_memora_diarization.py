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


def test_disputed_automatic_count_abstains_instead_of_merging(monkeypatch):
    # Short contexts suggest four groups; long contexts suggest only two.
    # Neither estimate justifies asserting four people, or forcing one.
    monkeypatch.setattr(d, "_embed_cells", lambda *args: ([1], []))
    monkeypatch.setattr(d, "_cluster", lambda *args, **kwargs: ([], [], [], 2))
    with pytest.raises(d.DiarizationError, match="se contredisent"):
        d._validate_automatic_count(None, None, [], 4, {})


def test_consistent_automatic_count_is_only_a_veto_not_a_replacement(monkeypatch):
    seen = []
    monkeypatch.setattr(d, "_embed_cells", lambda *args: ([1], []))

    def cluster(values, **kwargs):
        seen.append(kwargs["max_speakers"])
        return [], [], [], 2

    monkeypatch.setattr(d, "_cluster", cluster)
    assert d._validate_automatic_count(None, None, [], 2, {}, 16) is None
    assert seen == [16]


def test_single_group_does_not_run_additional_inference(monkeypatch):
    def unexpected(*args):
        pytest.fail("Single-group output must not run a second neural pass")

    monkeypatch.setattr(d, "_embed_cells", unexpected)
    d._validate_automatic_count(None, None, [], 1, {})


def test_long_context_preserves_cells_and_does_not_cross_silence():
    regions = [dict(start=16000, end=80000), dict(start=100000, end=130000)]
    short, long = list(d._cells(regions)), list(d._cells(regions, 3.2))
    assert [(a, b) for a, b, _, _ in short] == [(a, b) for a, b, _, _ in long]
    for _, _, start, end in long:
        assert any(r["start"] <= start < end <= r["end"] for r in regions)


def test_known_one_does_not_invent_multiple_groups_for_diverse_vectors():
    vectors = np.eye(4)
    assert d._cluster(vectors)[3] == 4
    labels, _, _, count = d._cluster(vectors, num_speakers=1)
    assert count == 1 and set(labels) == {0}


def test_explicit_one_bypasses_automatic_veto_preserving_source(monkeypatch):
    import resemblyzer

    monkeypatch.setattr(d, "_verified_weights", lambda: (Path("/unused"), "a" * 64))
    monkeypatch.setattr(d, "_decode", lambda path: np.ones(32000, dtype=np.float32))
    monkeypatch.setattr(d, "_regions", lambda audio: [dict(start=0, end=32000)])
    monkeypatch.setattr(resemblyzer, "VoiceEncoder", lambda **kwargs: object())
    cells = list(d._cells([dict(start=0, end=32000)]))
    monkeypatch.setattr(
        d, "_embed_cells", lambda *args: ([np.array([1.0, 0.0])] * len(cells), cells)
    )

    def unexpected(*args):
        pytest.fail("Explicit reviewer count must bypass automatic inference veto")

    monkeypatch.setattr(d, "_validate_automatic_count", unexpected)
    original = segment()
    result = d.diarize(Path("/synthetic"), [original], num_speakers=1)
    assert result["metadata"]["count_policy"] == "explicit"
    assert result["metadata"]["speaker_count"] == 1
    assert result["segments"][0]["speaker"] == "Intervenant 1"
    assert all(
        result["segments"][0][k] == original[k] for k in ("id", "text", "start", "end")
    )


def test_unknown_engine_is_unavailable_without_fallback(monkeypatch):
    monkeypatch.setenv("MEMORA_DIARIZATION_ENGINE", "unconfigured")
    assert not d.available()
    assert "reconnu" in d.availability()["reason"]


def test_ecapa_assets_reject_wrong_revision_or_modified_weights(tmp_path, monkeypatch):
    from api.memora import diarization_ecapa as e

    payload = b"synthetic weights only"
    digest = hashlib.sha256(payload).hexdigest()
    (tmp_path / "embedding_model.ckpt").write_bytes(payload)
    manifest = {"revision": e.REVISION, "sha256": digest, "license": "Apache-2.0"}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(e, "model_dir", lambda: tmp_path)
    monkeypatch.setattr(e, "SHA256", digest)
    monkeypatch.setattr(e, "BYTES", len(payload))
    monkeypatch.setattr(e.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(e.importlib.metadata, "version", lambda name: "1.1.2")
    assert e.availability()["available"]
    assert e.verified_weights() == (tmp_path / "embedding_model.ckpt", digest)
    (tmp_path / "embedding_model.ckpt").write_bytes(b"x" * len(payload))
    with pytest.raises(ValueError, match="intégrité"):
        e.verified_weights()
    manifest["revision"] = "different"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert not e.availability()["available"]
    (tmp_path / "manifest.json").write_text("[]")
    assert not e.availability()["available"]


def test_ecapa_source_frames_retain_primary_long_context_and_explicit_policy(
    monkeypatch,
):
    from api.memora import diarization_ecapa as e

    monkeypatch.setenv("MEMORA_DIARIZATION_ENGINE", "ecapa-tdnn")
    monkeypatch.setattr(d, "_verified_weights", lambda: (Path("/unused"), "a" * 64))
    monkeypatch.setattr(d, "_decode", lambda path: np.ones(64000, dtype=np.float32))
    monkeypatch.setattr(d, "_regions", lambda audio: [dict(start=0, end=64000)])
    monkeypatch.setattr(e, "Encoder", lambda weights: object())
    seen = []

    def embed(encoder, audio, cells, cache):
        cells = list(cells)
        seen.extend(cells)
        return [np.array([1.0, 0.0])] * len(cells), cells

    monkeypatch.setattr(d, "_embed_cells", embed)
    result = d.diarize(Path("/synthetic"), [segment(0, 4)], num_speakers=1)
    assert max(end - start for _, _, start, end in seen) == int(3.2 * 16000)
    assert result["metadata"]["engine"] == "ecapa-silero-ahc-v1"
    assert result["metadata"]["cluster_distance"] == 0.55
    assert result["metadata"]["count_policy"] == "explicit"
    assert result["segments"][0]["speaker"] == "Intervenant 1"
