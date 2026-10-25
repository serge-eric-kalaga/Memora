"""Configuration-only tests, no subprocess/service/GPU."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "isolated_asr_policy_test",
    Path(__file__).resolve().parents[1] / "memora-verify-isolated.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize(
    "choice,expected",
    [
        ("inherit", "parakeet-mlx"),
        ("disabled", ""),
        ("mlx-whisper", "mlx-whisper"),
        ("parakeet-mlx", "parakeet-mlx"),
        ("faster-whisper", "faster-whisper"),
    ],
)
def test_french_override_and_live_preservation(choice, expected):
    env = {
        "MEMORA_ASR_ENGINE": "faster-whisper",
        "MEMORA_FRENCH_ASR_ENGINE": "parakeet-mlx",
        "MEMORA_LIVE_ASR_ENGINE": "mlx-whisper",
    }
    runner.apply_asr_policy(env, "mlx-whisper", choice)
    assert env["MEMORA_ASR_ENGINE"] == "mlx-whisper"
    assert env["MEMORA_FRENCH_ASR_ENGINE"] == expected
    assert env["MEMORA_LIVE_ASR_ENGINE"] == "mlx-whisper"


def test_inherit_does_not_invent_optional_key():
    env = {}
    runner.apply_asr_policy(env)
    assert env == {}


def test_bad_value_rejected_before_mutation():
    env = {}
    with pytest.raises(ValueError):
        runner.apply_asr_policy(env, "mlx-whisper", "typo")
    assert env == {}
