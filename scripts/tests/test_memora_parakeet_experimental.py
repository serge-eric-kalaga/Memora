"""Pure timestamp mapping; deliberately no MLX import or inference."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "parakeet_adapter_test",
    Path(__file__).resolve().parents[1] / "memora-parakeet-experimental.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_native_times_preserved_without_fake_english():
    result = SimpleNamespace(
        text="Bonjour", sentences=[SimpleNamespace(text="Bonjour", start=1.25, end=2.5)]
    )
    segments = module.source_segments(result, 10, 5)
    assert segments[0]["start"] == 11.25
    assert segments[0]["end"] == 12.5
    assert segments[0]["language"] is None
    assert segments[0]["language_confidence"] is None
    assert segments[0]["uncertain"] is True


@pytest.mark.parametrize(
    "start,end", [(float("nan"), 2), (2, 1), (-1, 2), (1, 9), (5.1, 5.2)]
)
def test_invalid_native_times_rejected(start, end):
    with pytest.raises(RuntimeError):
        module.source_segments(
            SimpleNamespace(
                text="x", sentences=[SimpleNamespace(text="x", start=start, end=end)]
            ),
            0,
            5,
        )


def test_requires_offline_before_runtime_import():
    with (
        patch.dict("os.environ", {"HF_HUB_OFFLINE": "0"}),
        pytest.raises(RuntimeError, match="offline|OFFLINE"),
    ):
        module.transcribe(Path("synthetic.wav"))


@pytest.mark.parametrize(
    "container_format,codec,suffix",
    [("wav", "pcm_s16le", ".wav"), ("webm", "libopus", ".bin")],
)
def test_decode_synthetic_wav_and_webm_bytes_to_mono_16k(
    tmp_path, container_format, codec, suffix
):
    import av
    import numpy as np

    path = tmp_path / ("synthetic" + suffix)
    rate = 48000
    signal = (
        (0.1 * np.sin(2 * np.pi * 440 * np.arange(rate) / rate))
        .astype(np.float32)
        .reshape(1, -1)
    )
    with av.open(str(path), "w", format=container_format) as output:
        stream = output.add_stream(codec, rate=rate)
        stream.layout = "mono"
        frame = av.AudioFrame.from_ndarray(signal, format="flt", layout="mono")
        frame.sample_rate = rate
        for packet in stream.encode(frame):
            output.mux(packet)
        for packet in stream.encode(None):
            output.mux(packet)
    decoded = module.decode_audio(path)
    assert decoded.dtype == np.float32
    assert decoded.ndim == 1
    assert abs(len(decoded) - 16000) <= 1
    assert np.isfinite(decoded).all()
    assert float(np.max(np.abs(decoded))) > 0.05
