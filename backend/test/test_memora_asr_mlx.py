"""Adapter unit tests with mocked MLX, not proof of real ASR quality."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location(
    "memora_mlx_test", Path(__file__).parents[1] / "api/memora/asr_mlx.py"
)
asr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(asr)


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    model = tmp_path / "local-model"
    model.mkdir()
    (model / "config.json").write_text("{}")
    (model / "weights.npz").write_bytes(b"synthetic mock")
    monkeypatch.setenv("MEMORA_MLX_MODEL_PATH", str(model))
    monkeypatch.setattr(
        asr, "_decode_audio", lambda _: np.full(32000, 0.2, dtype=np.float32)
    )
    monkeypatch.setattr(
        asr, "_speech_regions", lambda audio: [{"start": 0, "end": len(audio)}]
    )
    holder = SimpleNamespace(model=object(), model_path="local-model")
    calls = []

    def transcribe(audio, **kwargs):
        calls.append((audio, kwargs))
        return {
            "language": "fr",
            "segments": [
                {
                    "start": 0.1,
                    "end": 1.8,
                    "text": " Phrase synthétique. ",
                    "avg_logprob": -0.1,
                    "no_speech_prob": 0.05,
                    "compression_ratio": 1.2,
                }
            ],
        }

    fake = SimpleNamespace(ModelHolder=holder, transcribe=transcribe)
    cleared = []
    monkeypatch.setattr(
        asr,
        "_runtime",
        lambda: (fake, SimpleNamespace(clear_cache=lambda: cleared.append(True))),
    )
    return fake, calls, cleared


@pytest.mark.parametrize(
    "language,expected", [("auto", None), ("fr", "fr"), ("en", "en")]
)
def test_local_ndarray_no_translation_and_cleanup(runtime, language, expected):
    fake, calls, cleared = runtime
    result = asr.transcribe(Path("synthetic.wav"), language=language)
    audio, kwargs = calls[0]
    assert isinstance(audio, np.ndarray) and len(audio) == 32000
    assert (
        kwargs["task"] == "transcribe"
        and kwargs["verbose"] is None
        and kwargs["language"] == expected
    )
    assert Path(kwargs["path_or_hf_repo"]).is_absolute()
    assert (
        result[0]["id"] == "s1"
        and result[0]["start"] == 0.1
        and result[0]["end"] == 1.8
    )
    assert result[0]["language_confidence"] is None
    assert result[0]["language_scope"] == (
        "speech_region_detection" if language == "auto" else "forced"
    )
    assert not result[0]["uncertain"]
    assert (
        fake.ModelHolder.model is None
        and fake.ModelHolder.model_path is None
        and cleared == [True]
    )


def test_tail_offsets_and_uncertain_missing_scores(runtime):
    fake, calls, _ = runtime
    fake.transcribe = lambda *_args, **_kwargs: {
        "language": "fr",
        "segments": [{"start": 0, "end": 0.5, "text": "Fin synthétique."}],
    }
    result = asr.transcribe(Path("synthetic.wav"), tail_seconds=0.5)
    assert result[0]["start"] == 1.5 and result[0]["end"] == 2.0
    assert result[0]["uncertain"]


def test_cleanup_on_model_failure(runtime):
    fake, _, cleared = runtime

    def fail(*_args, **_kwargs):
        raise RuntimeError("mock model unavailable")

    fake.transcribe = fail
    with pytest.raises(RuntimeError, match="unavailable"):
        asr.transcribe(Path("synthetic.wav"))
    assert fake.ModelHolder.model is None and cleared == [True]


def test_incomplete_local_model_never_loads_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORA_MLX_MODEL_PATH", str(tmp_path / "missing"))
    monkeypatch.setattr(
        asr, "_decode_audio", lambda _: np.ones(16000, dtype=np.float32)
    )
    monkeypatch.setattr(
        asr, "_runtime", lambda: pytest.fail("No download or runtime allowed")
    )
    with pytest.raises(RuntimeError, match="incomplet"):
        asr.transcribe(Path("synthetic.wav"))


def test_silence_and_invalid_options_never_load_model(monkeypatch):
    monkeypatch.setattr(
        asr, "_decode_audio", lambda _: np.zeros(16000, dtype=np.float32)
    )
    monkeypatch.setattr(
        asr, "_runtime", lambda: pytest.fail("Silence must not load model")
    )
    assert asr.transcribe(Path("synthetic.wav")) == []
    with pytest.raises(ValueError, match="Langue"):
        asr.transcribe(Path("synthetic.wav"), language="translate")
    with pytest.raises(ValueError, match="positive"):
        asr.transcribe(Path("synthetic.wav"), tail_seconds=-1)


def test_invalid_timestamps_fail_and_release_model(runtime):
    fake, _, cleared = runtime
    fake.transcribe = lambda *_args, **_kwargs: {
        "language": "fr",
        "segments": [
            {"start": float("nan"), "end": 1, "text": "Texte sans repère valide"}
        ],
    }
    with pytest.raises(RuntimeError, match="Horodatages"):
        asr.transcribe(Path("synthetic.wav"))
    assert fake.ModelHolder.model is None and cleared == [True]


def test_partial_invalid_timestamps_do_not_silently_drop_text(runtime):
    fake, _, cleared = runtime
    fake.transcribe = lambda *_args, **_kwargs: {
        "language": "fr",
        "segments": [
            {"start": 0, "end": 1, "text": "Passage valide."},
            {"start": None, "end": 2, "text": "Passage sans repère."},
        ],
    }
    with pytest.raises(RuntimeError, match="Horodatages"):
        asr.transcribe(Path("synthetic.wav"))
    assert cleared == [True]


def test_vad_empty_does_not_load_model(runtime, monkeypatch):
    monkeypatch.setattr(asr, "_speech_regions", lambda audio: [])
    monkeypatch.setattr(asr, "_runtime", lambda: pytest.fail("No model for silence"))
    assert asr.transcribe(Path("synthetic-noise.wav")) == []


def test_regions_keep_source_offsets_unique_ids_and_independent_language(
    runtime, monkeypatch
):
    fake, _, cleared = runtime
    monkeypatch.setattr(
        asr,
        "_speech_regions",
        lambda audio: [
            {"start": 1600, "end": 12800},
            {"start": 16000, "end": 30400},
        ],
    )
    results = iter(["fr", "en"])

    def transcribe(audio, **kwargs):
        assert kwargs["language"] is None
        assert fake.ModelHolder.model is not None
        return {
            "language": next(results),
            "segments": [
                {"start": 0, "end": len(audio) / 16000, "text": "Synthetic"},
            ],
        }

    fake.transcribe = transcribe
    result = asr.transcribe(Path("synthetic-mixed.wav"))
    assert [(x["id"], x["start"], x["end"], x["language"]) for x in result] == [
        ("s1", 0.1, 0.8, "fr"),
        ("s2", 1.0, 1.9, "en"),
    ]
    assert cleared == [True]


def test_french_final_model_is_separate_from_live_and_bilingual(
    runtime, tmp_path, monkeypatch
):
    _, calls, _ = runtime
    full = tmp_path / "full-model"
    full.mkdir()
    (full / "config.json").write_text("{}")
    (full / "weights.npz").write_bytes(b"synthetic mock")
    monkeypatch.setenv("MEMORA_MLX_FR_MODEL_PATH", str(full))
    asr.transcribe(Path("synthetic.wav"), language="fr")
    assert calls[-1][1]["path_or_hf_repo"] == str(full)
    for language, tail in (("auto", None), ("en", None), ("fr", 120)):
        asr.transcribe(Path("synthetic.wav"), language=language, tail_seconds=tail)
        assert calls[-1][1]["path_or_hf_repo"] != str(full)


def test_missing_french_model_fails_without_silent_fallback(
    runtime, tmp_path, monkeypatch
):
    _, calls, _ = runtime
    monkeypatch.setenv("MEMORA_MLX_FR_MODEL_PATH", str(tmp_path / "missing-full"))
    with pytest.raises(RuntimeError, match="incomplet"):
        asr.transcribe(Path("synthetic.wav"), language="fr")
    assert calls == []
