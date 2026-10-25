"""Isolated CPU tests; mocked model runtime, never proof of ASR quality."""

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import BaseModel, Field

spec = importlib.util.spec_from_file_location(
    "memora_parakeet_test", Path(__file__).parents[1] / "api/memora/asr_parakeet.py"
)
asr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(asr)


@pytest.fixture
def model(tmp_path, monkeypatch):
    payload = b"synthetic weights"
    assets = {
        name: {"bytes": 2, "sha256": hashlib.sha256(b"{}").hexdigest()}
        for name in asr.ASSETS
    }
    monkeypatch.setattr(asr, "ASSETS", assets)
    monkeypatch.setattr(asr, "WEIGHTS_BYTES", len(payload))
    monkeypatch.setattr(asr, "WEIGHTS_SHA", hashlib.sha256(payload).hexdigest())
    (tmp_path / "model.safetensors").write_bytes(payload)
    for name in assets:
        (tmp_path / name).write_bytes(b"{}")
    (tmp_path / "memora-model.json").write_text(
        json.dumps(
            {
                "repo": asr.REPO,
                "revision": asr.REVISION,
                "sha256": asr.WEIGHTS_SHA,
                "bytes": len(payload),
                "license": "CC-BY-4.0",
            }
        )
    )
    monkeypatch.setenv("MEMORA_PARAKEET_MODEL_PATH", str(tmp_path))
    asr._verified.clear()
    return tmp_path


def test_cache_skips_rehash_only_when_all_stat_fingerprints_unchanged(
    model, monkeypatch
):
    original = asr._sha
    calls = []
    monkeypatch.setattr(asr, "_sha", lambda p: (calls.append(p.name), original(p))[1])
    assert asr.verify_model(model) == model
    assert len(calls) == 6
    asr.verify_model(model)
    assert len(calls) == 6
    for name in asr.ASSETS:
        (model / name).touch()
        asr.verify_model(model)
    assert len(calls) == 36


def test_asset_same_size_corruption_invalidates_cache(model):
    asr.verify_model(model)
    (model / "tokenizer.vocab").write_bytes(b"[]")
    with pytest.raises(RuntimeError, match="Intégrité"):
        asr.verify_model(model)


def test_manifest_change_invalidates_cache(model):
    asr.verify_model(model)
    manifest = model / "memora-model.json"
    data = json.loads(manifest.read_text())
    data["license"] = "MIT"
    manifest.write_text(json.dumps(data))
    with pytest.raises(RuntimeError, match="Provenance"):
        asr.verify_model(model)


def test_missing_model_does_not_import_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORA_PARAKEET_MODEL_PATH", str(tmp_path / "absent"))
    monkeypatch.setattr(asr, "_runtime", lambda: pytest.fail("Runtime must not load"))
    with pytest.raises(RuntimeError, match="incomplet"):
        asr.transcribe(Path("synthetic.bin"))


def test_external_asset_symlink_rejected(model, tmp_path):
    external = tmp_path.parent / (tmp_path.name + "-external")
    external.write_bytes(b"{}")
    asset = model / "config.json"
    asset.unlink()
    asset.symlink_to(external)
    try:
        with pytest.raises(RuntimeError, match="externe"):
            asr.verify_model(model)
    finally:
        external.unlink()


@pytest.mark.parametrize("language", ["auto", "fr", "en"])
def test_native_timing_unknown_language_and_fixed_chunks(model, monkeypatch, language):
    calls = []
    cleared = []
    sentence = SimpleNamespace(text=" Source synthétique. ", start=0.1, end=0.8)
    result = SimpleNamespace(text=sentence.text, sentences=[sentence])

    class Model:
        def generate(self, audio, **kwargs):
            calls.append((len(audio), kwargs))
            return result

    mx = SimpleNamespace(
        array=lambda value: value, clear_cache=lambda: cleared.append(True)
    )
    monkeypatch.setattr(asr, "_runtime", lambda: (mx, lambda path, **kwargs: Model()))
    monkeypatch.setattr(
        asr, "decode_audio", lambda path: np.ones(48000, dtype=np.float32)
    )
    output = asr.transcribe(Path("synthetic.bin"), tail_seconds=1, language=language)
    assert output[0]["start"] == 2.1 and output[0]["end"] == 2.8
    assert (
        output[0]["language"] == "unknown" and output[0]["language_confidence"] is None
    )
    assert output[0]["uncertain"] is True
    assert calls == [
        (16000, {"chunk_duration": 30.0, "overlap_duration": 2.0, "verbose": False})
    ]
    assert cleared == [True]
    # Use the real route's model definitions without importing application/DB.
    tree = ast.parse((Path(__file__).parents[1] / "api/memora/routes.py").read_text())
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in {"Segment", "Correction"}
    ]
    namespace = {"BaseModel": BaseModel, "Field": Field}
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), "route-models", "exec"),
        namespace,
    )
    corrected = namespace["Correction"].model_validate(
        {"version": 1, "segments": output}
    )
    assert corrected.model_dump()["segments"][0]["language"] == "unknown"


def test_runtime_failure_releases_cache(model, monkeypatch):
    cleared = []

    class Model:
        def generate(self, *args, **kwargs):
            raise RuntimeError("synthetic failure")

    monkeypatch.setattr(
        asr,
        "_runtime",
        lambda: (
            SimpleNamespace(
                array=lambda x: x, clear_cache=lambda: cleared.append(True)
            ),
            lambda path, **kwargs: Model(),
        ),
    )
    monkeypatch.setattr(
        asr, "decode_audio", lambda path: np.ones(16000, dtype=np.float32)
    )
    with pytest.raises(RuntimeError, match="synthetic failure"):
        asr.transcribe(Path("synthetic.bin"))
    assert cleared == [True]


@pytest.mark.parametrize(
    "start,end", [(float("nan"), 2), (-1, 2), (2, 1), (5.1, 5.2), (1, 9)]
)
def test_invalid_native_times_rejected(start, end):
    with pytest.raises(RuntimeError):
        asr.source_segments(
            SimpleNamespace(
                text="x", sentences=[SimpleNamespace(text="x", start=start, end=end)]
            ),
            0,
            5,
        )


@pytest.mark.parametrize(
    "fmt,codec,suffix", [("wav", "pcm_s16le", ".wav"), ("webm", "libopus", ".bin")]
)
def test_real_synthetic_container_decode(tmp_path, fmt, codec, suffix):
    import av

    path = tmp_path / ("synthetic" + suffix)
    samples = (
        (0.1 * np.sin(2 * np.pi * 440 * np.arange(48000) / 48000))
        .astype(np.float32)
        .reshape(1, -1)
    )
    with av.open(str(path), "w", format=fmt) as container:
        stream = container.add_stream(codec, rate=48000)
        stream.layout = "mono"
        frame = av.AudioFrame.from_ndarray(samples, format="flt", layout="mono")
        frame.sample_rate = 48000
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    decoded = asr.decode_audio(path)
    assert decoded.ndim == 1 and decoded.dtype == np.float32
    assert abs(len(decoded) - 16000) <= 1 and np.isfinite(decoded).all()


def test_invalid_audio_is_rejected_before_model_load(model, tmp_path, monkeypatch):
    import av

    audio = tmp_path / "invalid.bin"
    audio.write_bytes(b"not an audio container")
    monkeypatch.setattr(
        asr, "_runtime", lambda: pytest.fail("Model must not load invalid audio")
    )
    with pytest.raises(av.error.InvalidDataError):
        asr.transcribe(audio)


@pytest.mark.parametrize("sample", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_samples_never_reach_model(model, monkeypatch, sample):
    monkeypatch.setattr(
        asr, "decode_audio", lambda _: np.array([0, sample], dtype=np.float32)
    )
    monkeypatch.setattr(
        asr, "_runtime", lambda: pytest.fail("Nonfinite audio must not reach model")
    )
    with pytest.raises(ValueError, match="non finis"):
        asr.transcribe(Path("synthetic.wav"))
