"""Provider routing contract; no ASR inference or user audio."""

import threading
from pathlib import Path

import pytest
from api.memora import ai, asr_mlx, asr_parakeet


@pytest.mark.parametrize(
    ("language", "tail", "expected"),
    [
        ("fr", None, "parakeet"),
        ("en", None, "whisper"),
        ("auto", None, "whisper"),
        ("fr", 12, "whisper"),
    ],
)
def test_french_final_route_preserves_other_languages_and_live(
    monkeypatch, language, tail, expected
):
    monkeypatch.setenv("MEMORA_ASR_ENGINE", "mlx-whisper")
    monkeypatch.setenv("MEMORA_LIVE_ASR_ENGINE", "mlx-whisper")
    monkeypatch.setenv("MEMORA_FRENCH_ASR_ENGINE", "parakeet-mlx")
    guard = threading.Lock()
    monkeypatch.setattr(ai, "_lock", guard)
    calls = []

    def provider(name):
        def transcribe(path, **kwargs):
            assert guard.locked()
            calls.append((name, path, kwargs))
            return [{"text": name}]

        return transcribe

    monkeypatch.setattr(asr_mlx, "transcribe", provider("whisper"))
    monkeypatch.setattr(asr_parakeet, "transcribe", provider("parakeet"))
    result = ai.transcribe(Path("synthetic.wav"), tail_seconds=tail, language=language)
    assert result == [{"text": expected}]
    assert calls == [
        (expected, Path("synthetic.wav"), {"tail_seconds": tail, "language": language})
    ]
    assert not guard.locked()


def test_disabled_route_preserves_existing_french_provider(monkeypatch):
    monkeypatch.setenv("MEMORA_ASR_ENGINE", "mlx-whisper")
    monkeypatch.setenv("MEMORA_FRENCH_ASR_ENGINE", "")
    monkeypatch.setattr(asr_mlx, "transcribe", lambda *a, **kw: ["existing"])
    assert ai.transcribe(Path("synthetic.wav"), language="fr") == ["existing"]


def test_invalid_french_route_never_silently_falls_back(monkeypatch):
    monkeypatch.setenv("MEMORA_ASR_ENGINE", "mlx-whisper")
    monkeypatch.setenv("MEMORA_FRENCH_ASR_ENGINE", "invalid-engine")
    monkeypatch.setattr(
        asr_mlx, "transcribe", lambda *a, **kw: pytest.fail("Silent fallback")
    )
    with pytest.raises(ai.ProcessingError, match="inconnu"):
        ai.transcribe(Path("synthetic.wav"), language="fr")


def test_parakeet_failure_releases_shared_inference_lock(monkeypatch):
    monkeypatch.setenv("MEMORA_ASR_ENGINE", "parakeet-mlx")
    monkeypatch.delenv("MEMORA_FRENCH_ASR_ENGINE", raising=False)
    guard = threading.Lock()
    monkeypatch.setattr(ai, "_lock", guard)

    def fail(*a, **kw):
        assert guard.locked()
        raise RuntimeError("Synthetic unavailable provider")

    monkeypatch.setattr(asr_parakeet, "transcribe", fail)
    with pytest.raises(RuntimeError, match="Synthetic unavailable"):
        ai.transcribe(Path("synthetic.wav"), language="fr")
    assert not guard.locked()


@pytest.mark.parametrize("tail", [None, 120])
def test_explicit_french_language_conditioned_route_uses_same_language_live_and_final(
    monkeypatch, tail
):
    monkeypatch.setenv("MEMORA_ASR_ENGINE", "mlx-whisper")
    monkeypatch.setenv("MEMORA_LIVE_ASR_ENGINE", "mlx-whisper")
    monkeypatch.setenv("MEMORA_FRENCH_ASR_ENGINE", "mlx-whisper")
    calls = []
    monkeypatch.setattr(
        asr_mlx,
        "transcribe",
        lambda path, **kwargs: (
            calls.append(kwargs)
            or [{"language": "fr", "language_scope": "forced", "text": "Bonjour"}]
        ),
    )
    monkeypatch.setattr(
        asr_parakeet,
        "transcribe",
        lambda *args, **kwargs: pytest.fail(
            "French unexpectedly routed to an unconstrained decoder"
        ),
    )
    result = ai.transcribe(Path("synthetic.wav"), tail_seconds=tail, language="fr")
    assert result[0]["language_scope"] == "forced"
    assert calls == [{"language": "fr", "tail_seconds": tail}]
