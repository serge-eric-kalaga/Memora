"""Synthetic-only review/rename/diarization contracts on isolated domain storage."""
# ruff: noqa: F811

import json
import sys
from types import SimpleNamespace

import pytest
from api.memora import routes as r, store as s
from .test_memora_domain import client, create, seed, SEGMENTS, PREFIX  # noqa: F401


def prepared(client):
    mid = create(client)
    seed(mid)
    with s.db() as c:
        report = json.loads(
            c.execute("SELECT data FROM reports WHERE id='report1'").fetchone()[0]
        )
        report["actions"] = [
            {
                "text": "Alice préparera le dossier vendredi.",
                "owner": "Alice",
                "deadline": "vendredi",
                "sources": ["s0"],
            }
        ]
        report["decisions"] = [
            {
                "text": "Nous validons le projet.",
                "owner": "Non précisé",
                "deadline": "Non précisée",
                "sources": ["s0"],
            }
        ]
        c.execute("UPDATE reports SET data=? WHERE id='report1'", (json.dumps(report),))
    return mid, PREFIX + "/meetings/" + mid


def review_body(**kw):
    return {
        "transcript_version": 1,
        "expected_revision": 0,
        "status": "confirmed",
        **kw,
    }


def guest(client, base, **rights):
    with s.db() as c:
        config = s.config(c)
        config["allow_guest_edit"] = True
        c.execute("UPDATE config SET data=? WHERE id=1", (json.dumps(config),))
    response = client.post(
        base + "/shares", json={"permissions": {"edit": True, **rights}}
    )
    assert response.status_code == 201, response.text
    return {
        "x-share-token": response.json()["id"],
        "x-guest-session": "synthetic-browser-session-0001",
    }


def test_review_append_only_conflict_and_raw_ai_unchanged(client):
    mid, base = prepared(client)
    path = base + "/reports/report1/reviews/actions/0"
    with s.db() as c:
        raw = c.execute("SELECT data FROM reports WHERE id='report1'").fetchone()[0]
    first = client.put(
        path,
        json=review_body(corrections={"owner": "Béa", "deadline": "avant vendredi"}),
    )
    assert first.status_code == 200, first.text
    entry = first.json()
    assert (
        entry["revision"] == 1
        and entry["provenance"] == "human_review"
        and entry["author"] == "user:1"
    )
    assert client.put(path, json=review_body()).status_code == 409
    second = client.put(
        path, json=review_body(expected_revision=1, status="needs_review")
    )
    assert (
        second.status_code == 200
        and second.json()["corrections"] == entry["corrections"]
    )
    third = client.put(
        path, json=review_body(expected_revision=2, status="cancelled", corrections={})
    )
    assert third.status_code == 200 and third.json()["corrections"] == {}
    read = client.get(base + "/reports/report1/reviews").json()
    assert (
        len(read["history"]) == 3
        and len(read["items"]) == 1
        and read["items"][0]["status"] == "cancelled"
    )
    meeting = client.get(base).json()
    assert meeting["reports"][0]["human_reviews"] == read["items"]
    with s.db() as c:
        assert (
            c.execute("SELECT data FROM reports WHERE id='report1'").fetchone()[0]
            == raw
        )


def test_review_owner_report_and_item_isolation(client):
    _, base = prepared(client)
    path = base + "/reports/report1/reviews/actions/0"
    assert (
        client.put(
            path, headers={"Authorization": "Bearer 2"}, json=review_body()
        ).status_code
        == 404
    )
    assert (
        client.get(
            base + "/reports/report1/reviews", headers={"Authorization": "Bearer 2"}
        ).status_code
        == 404
    )
    other = create(client)
    assert (
        client.get(
            PREFIX + "/meetings/" + other + "/reports/report1/reviews"
        ).status_code
        == 404
    )
    assert (
        client.put(
            base + "/reports/report1/reviews/actions/99", json=review_body()
        ).status_code
        == 404
    )
    assert (
        client.put(
            base + "/reports/report1/reviews/summary/0", json=review_body()
        ).status_code
        == 422
    )
    assert (
        client.put(path, json=review_body(corrections={"text": " "})).status_code == 422
    )
    assert (
        client.put(
            path, json=review_body(corrections={"deadline": "x" * 201})
        ).status_code
        == 422
    )


def test_review_guest_same_permissions_and_current_policy(client):
    _, base = prepared(client)
    headers = guest(client, base)
    path = base + "/reports/report1/reviews/decisions/0"
    assert client.put(path, headers=headers, json=review_body()).status_code == 403
    assert (
        client.put(
            path, headers=headers, json=review_body(editor_name="Invité test")
        ).status_code
        == 200
    )
    with s.db() as c:
        cfg = s.config(c)
        cfg["allow_guest_edit"] = False
        c.execute("UPDATE config SET data=? WHERE id=1", (json.dumps(cfg),))
    assert (
        client.put(
            path,
            headers=headers,
            json=review_body(expected_revision=1, editor_name="Invité test"),
        ).status_code
        == 403
    )
    assert (
        client.get(base + "/reports/report1/reviews", headers=headers).status_code
        == 200
    )


def test_revocation_between_access_and_writer_lock_prevents_review_and_rename(
    client, monkeypatch
):
    _, base = prepared(client)
    headers = guest(client, base)
    original = r.access

    async def revoked(request, mid, capability="view"):
        result = await original(request, mid, capability)
        with s.db() as c:
            row = c.execute(
                "SELECT data FROM shares WHERE id=?", (headers["x-share-token"],)
            ).fetchone()
            data = json.loads(row[0])
            data["revoked"] = True
            c.execute(
                "UPDATE shares SET data=? WHERE id=?",
                (json.dumps(data), headers["x-share-token"]),
            )
        return result

    monkeypatch.setattr(r, "access", revoked)
    assert (
        client.put(
            base + "/reports/report1/reviews/actions/0",
            headers=headers,
            json=review_body(editor_name="Invité test"),
        ).status_code
        == 404
    )
    with s.db() as c:
        assert c.execute("SELECT count(*) FROM report_reviews").fetchone()[0] == 0


def test_global_rename_preserves_sources_history_and_stales_reviews(client):
    mid, base = prepared(client)
    with s.db() as c:
        segments = [
            dict(SEGMENTS[0], speaker="Alice"),
            dict(SEGMENTS[0], id="s1", start=1, end=2, speaker="Bob"),
            dict(SEGMENTS[0], id="s2", start=2, end=3, speaker="Alice"),
        ]
        c.execute(
            "UPDATE transcripts SET data=? WHERE meeting=? AND version=1",
            (json.dumps(segments), mid),
        )
    path = base + "/reports/report1/reviews/actions/0"
    assert client.put(path, json=review_body()).status_code == 200
    result = client.post(
        base + "/speakers/rename",
        json={"version": 1, "from_speaker": "Alice", "to_speaker": "Alicia"},
    )
    assert (
        result.status_code == 200
        and result.json()["version"] == 2
        and result.json()["renamed_segments"] == 2
    )
    now = client.get(base + "/transcript").json()
    assert [v["speaker"] for v in now["segments"]] == ["Alicia", "Bob", "Alicia"]
    assert [(v["id"], v["start"], v["end"], v["text"]) for v in now["segments"]] == [
        (v["id"], v["start"], v["end"], v["text"]) for v in segments
    ]
    assert now["provenance"]["kind"] == "global_speaker_rename"
    assert client.get(base + "/transcript?version=1").json()["segments"] == segments
    assert client.get(base + "/reports/report1/reviews").json()["stale"] is True
    assert (
        client.put(
            path, json=review_body(transcript_version=2, expected_revision=1)
        ).status_code
        == 409
    )
    assert (
        client.post(
            base + "/speakers/rename",
            json={"version": 1, "from_speaker": "Alice", "to_speaker": "Autre"},
        ).status_code
        == 409
    )
    with s.db() as c:
        assert (
            json.loads(
                c.execute("SELECT data FROM reports WHERE id='report1'").fetchone()[0]
            )["actions"][0]["owner"]
            == "Alice"
        )


def test_unidentified_global_rename_requires_explicit_confirmation(client):
    _, base = prepared(client)
    body = {
        "version": 1,
        "from_speaker": "Intervenant non identifié",
        "to_speaker": "Alice",
    }
    assert client.post(base + "/speakers/rename", json=body).status_code == 422
    assert (
        client.post(
            base + "/speakers/rename", json={**body, "confirm_unidentified": True}
        ).status_code
        == 200
    )
    assert (
        client.post(
            base + "/speakers/rename",
            headers={"Authorization": "Bearer 2"},
            json={**body, "version": 2},
        ).status_code
        == 404
    )


def diarization_ready(mid, monkeypatch, available=True):
    import api.memora as package

    module = SimpleNamespace(available=lambda: available)
    monkeypatch.setitem(sys.modules, "api.memora.diarization", module)
    monkeypatch.setattr(package, "diarization", module, raising=False)
    folder = s.ROOT / mid
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "audio.bin").write_bytes(b"synthetic-placeholder-not-decoded")


def test_diarization_job_contract_idempotence_and_options(client, monkeypatch):
    mid, base = prepared(client)
    diarization_ready(mid, monkeypatch)
    body = {
        "version": 1,
        "request_id": "synthetic-diarization-request-01",
        "num_speakers": 2,
    }
    first = client.post(base + "/diarize", json=body)
    assert first.status_code == 200, first.text
    second = client.post(base + "/diarize", json=body)
    assert (
        second.json()["job_id"] == first.json()["job_id"]
        and second.json()["idempotent"]
    )
    assert (
        client.post(base + "/diarize", json={**body, "num_speakers": 3}).status_code
        == 409
    )
    assert (
        client.post(
            base + "/diarize",
            json={**body, "request_id": "synthetic-diarization-request-02"},
        ).status_code
        == 409
    )
    with s.db() as c:
        m = s.meeting(c, mid)
        assert (
            m["diarization_request"]["actor"] == "user:1"
            and m["diarization_request"]["num_speakers"] == 2
        )
        assert (
            c.execute("SELECT count(*) FROM jobs WHERE kind='diarize'").fetchone()[0]
            == 1
        )


@pytest.mark.parametrize(
    "available,version,expected", [(False, 1, 503), (True, 2, 409)]
)
def test_diarization_unavailable_or_stale_does_not_enqueue(
    client, monkeypatch, available, version, expected
):
    mid, base = prepared(client)
    diarization_ready(mid, monkeypatch, available)
    assert (
        client.post(base + "/diarize", json={"version": version}).status_code
        == expected
    )
    with s.db() as c:
        assert c.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0


def test_diarization_guest_requires_audio_and_edit_name(client, monkeypatch):
    mid, base = prepared(client)
    diarization_ready(mid, monkeypatch)
    headers = guest(client, base, audio=False)
    assert (
        client.post(
            base + "/diarize",
            headers=headers,
            json={"version": 1, "editor_name": "Invité test"},
        ).status_code
        == 403
    )
    assert (
        client.post(base + "/diarize", headers=headers, json={"version": 1}).status_code
        == 403
    )


def test_delete_cascades_human_history(client):
    mid, base = prepared(client)
    assert (
        client.put(
            base + "/reports/report1/reviews/actions/0", json=review_body()
        ).status_code
        == 200
    )
    assert (
        client.post(
            base + "/speakers/rename",
            json={
                "version": 1,
                "from_speaker": "Intervenant non identifié",
                "to_speaker": "Alice",
                "confirm_unidentified": True,
            },
        ).status_code
        == 200
    )
    assert client.delete(base).status_code == 200
    with s.db() as c:
        assert c.execute("SELECT count(*) FROM report_reviews").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM transcript_edits").fetchone()[0] == 0


def test_regenerated_same_source_report_stales_old_review_without_carryover(client):
    mid, base = prepared(client)
    assert (
        client.put(
            base + "/reports/report1/reviews/actions/0", json=review_body()
        ).status_code
        == 200
    )
    with s.db() as c:
        data = c.execute("SELECT data FROM reports WHERE id='report1'").fetchone()[0]
        c.execute(
            "INSERT INTO reports VALUES(?,?,?,?,?)",
            ("report2", mid, 1, data, 9999999999),
        )
        m = s.meeting(c, mid)
        m["report_id"] = "report2"
        s.save(c, m)
    meeting = client.get(base).json()
    old = next(v for v in meeting["reports"] if v["id"] == "report1")
    new = next(v for v in meeting["reports"] if v["id"] == "report2")
    assert (
        old["reviews_stale"] and not new["reviews_stale"] and not new["human_reviews"]
    )
    assert (
        client.put(
            base + "/reports/report1/reviews/actions/0",
            json=review_body(expected_revision=1),
        ).status_code
        == 409
    )
    assert (
        client.get(base + "/reports/report1/reviews").json()["items"][0]["status"]
        == "confirmed"
    )


def test_review_overlay_does_not_modify_chat_transcription_context(client, monkeypatch):
    _, base = prepared(client)
    assert (
        client.put(
            base + "/reports/report1/reviews/actions/0",
            json=review_body(
                corrections={"text": "Human-only instruction never used as transcript"}
            ),
        ).status_code
        == 200
    )
    seen = []

    def answer(segments, *args):
        seen.extend(segments)
        return {"answer": "Le budget est ouvert.", "sources": ["s0"]}

    monkeypatch.setattr(r.ai, "answer", answer)
    result = client.post(base + "/chat", json={"question": "Quel est le budget ?"})
    assert result.status_code == 200, result.text
    assert seen == SEGMENTS


def test_guest_global_rename_and_review_report_permission(client):
    _, base = prepared(client)
    headers = guest(client, base, report=False)
    headers["Authorization"] = ""
    assert (
        client.put(
            base + "/reports/report1/reviews/actions/0",
            headers=headers,
            json=review_body(editor_name="Invité test"),
        ).status_code
        == 403
    )
    result = client.post(
        base + "/speakers/rename",
        headers=headers,
        json={
            "version": 1,
            "from_speaker": "Intervenant non identifié",
            "to_speaker": "Personne déclarée",
            "confirm_unidentified": True,
            "editor_name": "Invité test",
        },
    )
    assert result.status_code == 200, result.text
    assert (
        client.get(base + "/transcript", headers=headers).json()["provenance"][
            "editor_name"
        ]
        == "Invité test"
    )


def test_revocation_during_rename_and_existing_correction_is_rechecked(
    client, monkeypatch
):
    _, base = prepared(client)
    headers = guest(client, base)
    original = r.access

    async def revoked(request, mid, capability="view"):
        result = await original(request, mid, capability)
        with s.db() as c:
            c.execute("DELETE FROM shares WHERE id=?", (headers["x-share-token"],))
        return result

    monkeypatch.setattr(r, "access", revoked)
    response = client.post(
        base + "/speakers/rename",
        headers=headers,
        json={
            "version": 1,
            "from_speaker": "Intervenant non identifié",
            "to_speaker": "Alice",
            "confirm_unidentified": True,
            "editor_name": "Invité test",
        },
    )
    assert response.status_code == 404
    with s.db() as c:
        assert c.execute("SELECT count(*) FROM transcripts").fetchone()[0] == 1


def test_diarization_expired_audio_and_live_job_block_enqueue(client, monkeypatch):
    mid, base = prepared(client)
    diarization_ready(mid, monkeypatch)
    with s.db() as c:
        m = s.meeting(c, mid)
        m["audio_expires_at"] = 0
        s.save(c, m)
    assert client.post(base + "/diarize", json={"version": 1}).status_code == 410
    with s.db() as c:
        m = s.meeting(c, mid)
        m.pop("audio_expires_at")
        s.save(c, m)
        s.enqueue(c, mid, "live", 1)
    assert client.post(base + "/diarize", json={"version": 1}).status_code == 409
    with s.db() as c:
        assert (
            c.execute("SELECT count(*) FROM jobs WHERE kind='diarize'").fetchone()[0]
            == 0
        )


def test_additive_migration_repeat_preserves_review_history(client):
    _, base = prepared(client)
    assert (
        client.put(
            base + "/reports/report1/reviews/actions/0", json=review_body()
        ).status_code
        == 200
    )
    with s.db() as c:
        before = c.execute("SELECT data FROM reports WHERE id='report1'").fetchone()[0]
    s.init()
    assert len(client.get(base + "/reports/report1/reviews").json()["history"]) == 1
    with s.db() as c:
        assert (
            c.execute("SELECT data FROM reports WHERE id='report1'").fetchone()[0]
            == before
        )


def test_human_can_clear_owner_deadline_without_erasing_ai_or_history(client):
    _, base = prepared(client)
    path = base + "/reports/report1/reviews/actions/0"
    first = client.put(
        path, json=review_body(corrections={"owner": "  ", "deadline": ""})
    )
    assert first.status_code == 200 and first.json()["corrections"] == {
        "owner": "",
        "deadline": "",
    }
    second = client.put(
        path,
        json=review_body(
            expected_revision=1,
            corrections={"owner": "Camille", "deadline": "avant mardi"},
        ),
    )
    assert second.status_code == 200
    read = client.get(base + "/reports/report1/reviews").json()
    assert read["history"][0]["corrections"] == {"owner": "", "deadline": ""}
    assert (
        client.get(base).json()["reports"][0]["data"]["actions"][0]["owner"] == "Alice"
    )
    assert (
        client.put(
            path, json=review_body(expected_revision=2, corrections={"text": " "})
        ).status_code
        == 422
    )


def test_report_only_guest_can_review_but_cannot_edit_source(client):
    _, base = prepared(client)
    headers = guest(client, base, transcript=False, audio=False)
    headers["Authorization"] = ""
    assert client.get(base, headers=headers).json()["permissions"]["edit"]
    assert (
        client.put(
            base + "/reports/report1/reviews/actions/0",
            headers=headers,
            json=review_body(editor_name="Relecteur"),
        ).status_code
        == 200
    )
    assert (
        client.put(
            base + "/transcript",
            headers=headers,
            json={"version": 1, "segments": SEGMENTS, "editor_name": "Relecteur"},
        ).status_code
        == 403
    )
    assert client.post(base + "/analyze", headers=headers).status_code == 403
    assert (
        client.post(
            base + "/speakers/rename",
            headers=headers,
            json={
                "version": 1,
                "from_speaker": "Intervenant non identifié",
                "to_speaker": "Alice",
                "confirm_unidentified": True,
                "editor_name": "Relecteur",
            },
        ).status_code
        == 403
    )


def test_correction_preserves_server_metadata_and_ignores_spoofed_fields(client):
    mid, base = prepared(client)
    original = {
        **SEGMENTS[0],
        "speaker": "Alice",
        "speaker_id": "SPEAKER_00",
        "speaker_confidence": None,
        "speaker_uncertain": True,
        "speaker_provenance": {"provider": "synthetic-model"},
        "speaker_candidates": ["SPEAKER_00"],
        "language_scope": "speech_region_detection",
        "language_confidence": 0.7,
    }
    with s.db() as c:
        c.execute(
            "UPDATE transcripts SET data=? WHERE meeting=? AND version=1",
            (json.dumps([original]), mid),
        )
    spoof = {
        **original,
        "text": "Texte corrigé",
        "language": "en",
        "speaker_id": "SPOOFED",
        "speaker_confidence": 1,
        "speaker_provenance": {"provider": "spoofed"},
        "language_scope": "spoofed",
    }
    assert (
        client.put(
            base + "/transcript", json={"version": 1, "segments": [spoof]}
        ).status_code
        == 200
    )
    current = client.get(base + "/transcript").json()["segments"][0]
    assert current == {**original, "text": "Texte corrigé"}
    human = {**spoof, "speaker": "Alicia"}
    assert (
        client.put(
            base + "/transcript", json={"version": 2, "segments": [human]}
        ).status_code
        == 200
    )
    current = client.get(base + "/transcript").json()["segments"][0]
    assert (
        current["speaker"] == "Alicia"
        and current["speaker_id"] == "SPEAKER_00"
        and current["speaker_confidence"] is None
        and not current["speaker_uncertain"]
    )
    assert (
        current["speaker_provenance"]["kind"] == "human_correction"
        and current["language"] == "fr"
        and current["language_scope"] == "speech_region_detection"
    )
    assert client.get(base + "/transcript?version=1").json()["segments"][0] == original


def test_global_rename_keeps_cluster_and_marks_human_label(client):
    mid, base = prepared(client)
    original = {
        **SEGMENTS[0],
        "speaker_id": "SPEAKER_00",
        "speaker_uncertain": True,
        "speaker_provenance": {"provider": "synthetic-model"},
        "language_scope": "forced",
    }
    with s.db() as c:
        c.execute(
            "UPDATE transcripts SET data=? WHERE meeting=? AND version=1",
            (json.dumps([original]), mid),
        )
    assert (
        client.post(
            base + "/speakers/rename",
            json={
                "version": 1,
                "from_speaker": original["speaker"],
                "to_speaker": "Alice",
                "confirm_unidentified": True,
            },
        ).status_code
        == 200
    )
    now = client.get(base + "/transcript").json()["segments"][0]
    assert (
        now["speaker_id"] == "SPEAKER_00"
        and now["language_scope"] == "forced"
        and now["speaker_provenance"]["kind"] == "human_global_speaker_rename"
        and not now["speaker_uncertain"]
    )
    assert (now["id"], now["start"], now["end"], now["text"]) == (
        original["id"],
        original["start"],
        original["end"],
        original["text"],
    )
