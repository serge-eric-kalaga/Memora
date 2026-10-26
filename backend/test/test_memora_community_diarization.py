"""Synthetic protocol, privacy, source integrity and opt-in recovery checks."""

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from api.memora import diarization as d, diarization_community as community


def result():
    return {
        "turns": [
            {"start": 1, "end": 2, "speaker_id": "B"},
            {"start": 0, "end": 1, "speaker_id": "A"},
        ],
        "speaker_count": 2,
    }


def test_labels_follow_first_occurrence_and_preserve_overlapping_turns():
    value = result()
    turns, count = community.parse_turns(value, 2, 8)
    assert count == 2
    assert [t["speaker"] for t in turns] == ["Intervenant 1", "Intervenant 2"]
    assert value == result()
    value["turns"][0]["start"] = 0.5
    assert community.parse_turns(value, 2, 8)[1] == 2


@pytest.mark.parametrize(
    "change",
    [
        {"start": "0"},
        {"start": True},
        {"start": float("nan")},
        {"end": 3},
        {"end": -1},
        {"speaker_id": None},
        {"speaker_id": ""},
    ],
)
def test_invalid_native_boundaries_are_rejected(change):
    value = result()
    value["turns"][0].update(change)
    with pytest.raises(d.DiarizationError):
        community.parse_turns(value, 2, 8)


@pytest.mark.parametrize("count", [0, 1, True, "2"])
def test_inconsistent_counts_never_establish_speaker_labels(count):
    value = result()
    value["speaker_count"] = count
    with pytest.raises(d.UncertainSpeakerCount):
        community.parse_turns(value, 2, 8)


def test_inference_only_reads_local_assets_and_removes_temporary_audio(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        community, "assets", lambda: (tmp_path, Path("/synthetic/binary"))
    )
    monkeypatch.setattr(d, "_decode", lambda path: np.zeros(32000, dtype=np.float32))
    paths = []

    def run(args, **kwargs):
        assert kwargs["timeout"] == 1800
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
        paths.append(Path(args[2]))
        assert paths[-1].stat().st_size == 32000 * 4
        Path(args[3]).write_text(json.dumps(result()))

    monkeypatch.setattr(subprocess, "run", run)
    source = [
        {"id": "one", "start": 0, "end": 1, "text": "Synthetic A"},
        {"id": "two", "start": 1, "end": 2, "text": "Synthetic B"},
    ]
    output = community.diarize(tmp_path / "source", source)
    assert [s["speaker"] for s in output["segments"]] == [
        "Intervenant 1",
        "Intervenant 2",
    ]
    assert all(
        all(x[k] == y[k] for k in ("id", "start", "end", "text"))
        for x, y in zip(source, output["segments"], strict=True)
    )
    assert not paths[-1].exists()


def test_native_failure_cleans_up_and_does_not_disclose_details(monkeypatch, tmp_path):
    monkeypatch.setattr(
        community, "assets", lambda: (tmp_path, Path("/synthetic/binary"))
    )
    monkeypatch.setattr(d, "_decode", lambda path: np.zeros(16000, dtype=np.float32))
    paths = []

    def run(args, **kwargs):
        paths.append(Path(args[2]))
        raise subprocess.TimeoutExpired("private source", 1800)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(d.DiarizationError) as caught:
        community.diarize(tmp_path / "source", [])
    assert "private" not in str(caught.value)
    assert not paths[-1].exists()


def test_missing_assets_do_not_trigger_download(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMORA_COMMUNITY_MODEL_DIR", str(tmp_path))
    with pytest.raises(d.DiarizationError):
        community.assets()
