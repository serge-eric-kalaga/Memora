"""Explicit acoustic recovery strategy; infrastructure failures never fall back."""

import pytest

from api.memora import diarization as d, diarization_segmented as segmented


@pytest.fixture
def hybrid(monkeypatch):
    monkeypatch.setenv("MEMORA_DIARIZATION_ENGINE", "ecapa-segmented")
    monkeypatch.delenv("MEMORA_INFERENCE_URL", raising=False)
    monkeypatch.setattr(segmented, "verified_segmentation", lambda: (None, "synthetic"))


def test_verified_primary_result_keeps_its_labels_and_provenance(hybrid, monkeypatch):
    result = {
        "metadata": {"engine": "ecapa-silero-ahc-v1", "speaker_count": 1},
        "segments": [],
    }
    monkeypatch.setattr(d, "_diarize_embeddings", lambda *a, **kw: result)
    monkeypatch.setattr(segmented, "diarize", lambda *a, **kw: pytest.fail("No retry"))
    assert d.diarize(None, []) is result
    assert result["metadata"]["strategy"] == "validated-ecapa-then-segmentation-v1"
    assert "recovery_reason" not in result["metadata"]


def test_uncertain_count_uses_segmentation_and_records_the_actual_engine(
    hybrid, monkeypatch
):
    def uncertain(*args, **kwargs):
        raise d.UncertainSpeakerCount("Synthetic acoustic disagreement")

    monkeypatch.setattr(d, "_diarize_embeddings", uncertain)
    source = [{"id": "synthetic", "text": "Synthetic source"}]
    calls = []

    def recover(path, segments, **kwargs):
        calls.append((path, segments, kwargs))
        return {
            "metadata": {"engine": "pyannote-onnx-ecapa-ahc-v1"},
            "segments": segments,
        }

    monkeypatch.setattr(segmented, "diarize", recover)
    result = d.diarize("synthetic.wav", source, num_speakers=2)
    assert result["segments"] is source
    assert calls == [("synthetic.wav", source, {"num_speakers": 2, "max_speakers": 8})]
    assert result["metadata"]["recovery_reason"] == "unstable_voice_clustering"


def test_invalid_audio_or_assets_do_not_get_hidden_by_recovery(hybrid, monkeypatch):
    def fail(*args, **kwargs):
        raise d.DiarizationError("Synthetic integrity failure")

    monkeypatch.setattr(d, "_diarize_embeddings", fail)
    monkeypatch.setattr(segmented, "diarize", lambda *a, **kw: pytest.fail("No retry"))
    with pytest.raises(d.DiarizationError, match="integrity"):
        d.diarize(None, [])
    monkeypatch.setattr(segmented, "verified_segmentation", fail)
    with pytest.raises(d.DiarizationError, match="integrity"):
        d.diarize(None, [])
    assert not d.available()


def test_legacy_selection_does_not_silently_enable_another_model(monkeypatch):
    monkeypatch.setenv("MEMORA_DIARIZATION_ENGINE", "ecapa-tdnn")
    monkeypatch.delenv("MEMORA_INFERENCE_URL", raising=False)

    def uncertain(*args, **kwargs):
        raise d.UncertainSpeakerCount("Synthetic acoustic disagreement")

    monkeypatch.setattr(d, "_diarize_embeddings", uncertain)
    monkeypatch.setattr(segmented, "diarize", lambda *a, **kw: pytest.fail("No retry"))
    with pytest.raises(d.UncertainSpeakerCount):
        d.diarize(None, [])
