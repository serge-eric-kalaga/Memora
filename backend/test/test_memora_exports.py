"""Synthetic exports, access isolation, immutable versions and document formats."""
# ruff: noqa: F811

from io import BytesIO
import json
import zipfile
import time

import pytest
from pypdf import PdfReader
from api.memora import exports, store as s
from .test_memora_domain import client, create, seed, PREFIX  # noqa: F401


def prepare(client):
    mid = create(client, title='Réunion œuf <test> " français / English')
    seed(mid)
    return mid, PREFIX + "/meetings/" + mid + "/export"


def get(client, path, content="transcript", format="txt", **kwargs):
    return client.get(path, params={"content": content, "format": format, **kwargs})


@pytest.mark.parametrize(
    "content,formats",
    [
        ("transcript", ["txt", "pdf", "docx", "srt", "vtt"]),
        ("report", ["txt", "pdf", "docx", "md"]),
    ],
)
def test_all_formats_and_headers(client, content, formats):
    _, path = prepare(client)
    for format in formats:
        response = get(client, path, content, format)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-type"].startswith(
            exports.MEDIA_TYPES[format].split(";")[0]
        )
        header = response.headers["content-disposition"]
        assert "attachment;" in header and "filename*=UTF-8''" in header
        assert f".{format}" in header
        if format == "pdf":
            text = "\n".join(
                p.extract_text() for p in PdfReader(BytesIO(response.content)).pages
            )
            assert "Réunion œuf <test>" in text
            assert "budget" in text and "Page 1" in text
        elif format == "docx":
            with zipfile.ZipFile(BytesIO(response.content)) as archive:
                text = archive.read("word/document.xml").decode()
                assert "budget" in text and "Réunion œuf &lt;test&gt;" in text
        else:
            assert "budget" in response.text


def test_version_history_and_no_mutation(client):
    mid, path = prepare(client)
    with s.db() as c:
        m = s.meeting(c, mid)
        old = s.transcript(c, mid, 1)
        modified = [
            {
                **old[0],
                "text": "Texte corrigé",
                "speaker": "Béatrice",
                "uncertain": True,
            }
        ]
        c.execute(
            "INSERT INTO transcripts VALUES(?,?,?,?,?)",
            (mid, 2, json.dumps(modified), "user:1", time.time()),
        )
        m["version"] = 2
        s.save(c, m)
        before = c.execute("SELECT data FROM reports WHERE id='report1'").fetchone()[0]
    current = get(client, path).text
    assert (
        "Texte corrigé" in current
        and "Béatrice" in current
        and "Passage incertain" in current
    )
    old = get(client, path, version=1).text
    assert "Texte corrigé" not in old and "Version historique" in old
    report = get(client, path, "report", "txt", report_id="report1")
    assert report.status_code == 200 and "À actualiser" in report.text
    assert get(client, path, version=999).status_code == 404
    assert get(client, path, "report", report_id="no-report").status_code == 404
    other = create(client)
    assert (
        get(
            client,
            PREFIX + "/meetings/" + other + "/export",
            "report",
            report_id="report1",
        ).status_code
        == 404
    )
    with s.db() as c:
        assert (
            c.execute("SELECT data FROM reports WHERE id='report1'").fetchone()[0]
            == before
        )
        assert s.meeting(c, mid)["version"] == 2


def share(client, mid, **rights):
    response = client.post(
        PREFIX + "/meetings/" + mid + "/shares",
        json={
            "permissions": {
                "report": False,
                "transcript": False,
                "audio": False,
                "chat": False,
                **rights,
            }
        },
    )
    assert response.status_code == 201, response.text
    return {"x-share-token": response.json()["id"]}


@pytest.mark.parametrize("capability", ["transcript", "report"])
def test_guest_capabilities(client, capability):
    mid, path = prepare(client)
    headers = share(client, mid, **{capability: True})
    okay = client.get(
        path, params={"content": capability, "format": "txt"}, headers=headers
    )
    assert okay.status_code == 200
    other = "report" if capability == "transcript" else "transcript"
    assert (
        client.get(
            path, params={"content": other, "format": "txt"}, headers=headers
        ).status_code
        == 403
    )
    if capability == "report":
        assert "Intervenant non identifié" not in okay.text
        assert "s0" not in okay.text
    assert (
        client.get(
            path,
            params={"content": capability, "format": "txt"},
            headers={"Authorization": "Bearer 2"},
        ).status_code
        == 404
    )


def test_password_expiry_revocation(client):
    mid, path = prepare(client)
    base = PREFIX + "/meetings/" + mid
    response = client.post(
        base + "/shares",
        json={"password": "synthetic-pass123", "permissions": {"report": True}},
    )
    assert response.status_code == 201
    token = response.json()["id"]
    headers = {"x-share-token": token}
    params = {"content": "report", "format": "txt"}
    assert client.get(path, params=params, headers=headers).status_code == 401
    headers["x-share-password"] = "wrong"
    assert client.get(path, params=params, headers=headers).status_code == 401
    headers["x-share-password"] = "synthetic-pass123"
    assert client.get(path, params=params, headers=headers).status_code == 200
    with s.db() as c:
        data = json.loads(
            c.execute("SELECT data FROM shares WHERE id=?", (token,)).fetchone()[0]
        )
        data["expires_at"] = time.time() - 1
        c.execute("UPDATE shares SET data=? WHERE id=?", (json.dumps(data), token))
    assert client.get(path, params=params, headers=headers).status_code == 404
    with s.db() as c:
        data.pop("expires_at")
        data["revoked"] = True
        c.execute("UPDATE shares SET data=? WHERE id=?", (json.dumps(data), token))
    assert client.get(path, params=params, headers=headers).status_code == 404


def test_revalidation_after_generation(client, monkeypatch):
    mid, path = prepare(client)
    headers = share(client, mid, report=True, transcript=True)
    original = exports.render

    def revoked(snapshot, extension):
        result = original(snapshot, extension)
        with s.db() as c:
            token = headers["x-share-token"]
            data = json.loads(
                c.execute("SELECT data FROM shares WHERE id=?", (token,)).fetchone()[0]
            )
            data["revoked"] = True
            c.execute("UPDATE shares SET data=? WHERE id=?", (json.dumps(data), token))
        return result

    monkeypatch.setattr(exports, "render", revoked)
    assert (
        client.get(
            path, params={"content": "transcript", "format": "txt"}, headers=headers
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "params",
    [
        {"content": "report", "format": "srt"},
        {"content": "transcript", "format": "md"},
        {"content": "audio", "format": "txt"},
        {"content": "report", "format": "html"},
        {"content": "transcript", "format": "txt", "version": 0},
        {"content": "transcript", "format": "txt", "report_id": "report1"},
        {"content": "report", "format": "txt", "version": 1},
    ],
)
def test_invalid_format_and_parameters(client, params):
    _, path = prepare(client)
    assert client.get(path, params=params).status_code == 422


def test_empty_missing_and_filename_injection(client):
    mid = create(client)
    path = PREFIX + "/meetings/" + mid + "/export"
    assert get(client, path).status_code == 404
    assert get(client, path, "report").status_code == 404
    seed(mid)
    with s.db() as c:
        c.execute("UPDATE transcripts SET data='[]' WHERE meeting=?", (mid,))
        c.execute("UPDATE reports SET data='{}' WHERE meeting=?", (mid,))
    assert get(client, path).status_code == 409
    assert get(client, path, "report").status_code == 409
    header = exports.disposition('a"\r\nInjected: yes/../../', "report", 1, "txt")
    assert "\r" not in header and "\n" not in header
    assert 'filename="a-' in header and "/" not in header


def test_subtitles_timing_and_markup():
    snapshot = {
        "segments": [
            {
                "speaker": "Élise",
                "text": "<b>Bonjour</b> & oui",
                "start": 3661.125,
                "end": 3661.125,
                "uncertain": True,
            }
        ]
    }
    srt = exports.subtitle(snapshot, "srt").decode()
    assert "01:01:01,125 --> 01:01:01,126" in srt
    vtt = exports.subtitle(snapshot, "vtt").decode()
    assert vtt.startswith("WEBVTT\n") and "&lt;b&gt;Bonjour&lt;/b&gt; &amp; oui" in vtt


def test_pdf_long_text_wrapping_and_escaped_markup():
    source = "Élève œuf cœur, l’été <b>littéral</b> & English. "
    pdf = exports.pdf_document([("title", "Réunion"), ("text", source * 1500)])
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) > 2
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "<b>littéral</b>" in text and "œuf cœur" in text
    for index, page in enumerate(reader.pages, start=1):
        assert f"Page {index}" in page.extract_text()


def test_human_reviews_distinct_from_original_and_current_scope(client):
    mid, path = prepare(client)
    base = PREFIX + "/meetings/" + mid
    with s.db() as c:
        report = json.loads(
            c.execute("SELECT data FROM reports WHERE id='report1'").fetchone()[0]
        )
        report["actions"] = [
            {
                "text": "Préparer le dossier",
                "owner": "Alice",
                "deadline": "vendredi",
                "sources": ["s0"],
            }
        ]
        c.execute("UPDATE reports SET data=? WHERE id='report1'", (json.dumps(report),))
    response = client.put(
        base + "/reports/report1/reviews/actions/0",
        json={
            "transcript_version": 1,
            "expected_revision": 0,
            "status": "confirmed",
            "corrections": {"owner": "Béatrice", "text": "Préparer les tests"},
        },
    )
    assert response.status_code == 200, response.text
    text = get(client, path, "report").text
    assert "Préparer le dossier" in text and "Responsable : Alice" in text
    assert "Correction humaine — Responsable : Béatrice" in text
    assert "Correction humaine — Texte : Préparer les tests" in text
    assert "Révision humaine : Validé" in text
    assert "Sources : 00:00:00" in text
    report_only = share(client, mid, report=True)
    text = client.get(
        path, params={"content": "report", "format": "txt"}, headers=report_only
    ).text
    assert "Sources :" not in text and "Intervenant non identifié" not in text
    assert "Correction humaine — Responsable : Béatrice" in text


def test_source_rights_changed_during_generation(client, monkeypatch):
    mid, path = prepare(client)
    headers = share(client, mid, report=True, transcript=True)
    original = exports.render

    def changed(snapshot, extension):
        result = original(snapshot, extension)
        with s.db() as c:
            token = headers["x-share-token"]
            data = json.loads(
                c.execute("SELECT data FROM shares WHERE id=?", (token,)).fetchone()[0]
            )
            data["permissions"]["transcript"] = False
            c.execute("UPDATE shares SET data=? WHERE id=?", (json.dumps(data), token))
        return result

    monkeypatch.setattr(exports, "render", changed)
    assert (
        client.get(
            path, params={"content": "report", "format": "txt"}, headers=headers
        ).status_code
        == 403
    )


def test_version_changed_during_generation(client, monkeypatch):
    mid, path = prepare(client)
    original = exports.render

    def changed(snapshot, extension):
        result = original(snapshot, extension)
        with s.db() as c:
            meeting = s.meeting(c, mid)
            meeting["version"] += 1
            s.save(c, meeting)
        return result

    monkeypatch.setattr(exports, "render", changed)
    assert get(client, path).status_code == 409


def test_unsupported_pdf_glyphs_and_invalid_xml_are_explicit():
    entries = [("title", "Emoji 😀 et contrôle \x01"), ("text", "mot" * 2000)]
    data = exports.pdf_document(entries)
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(data)).pages)
    assert "[U+1F600]" in text and "[U+0001]" in text
    assert "non représentables" in text
    doc = exports.docx_document(entries)
    with zipfile.ZipFile(BytesIO(doc)) as archive:
        xml = archive.read("word/document.xml").decode()
        assert "😀" in xml and "[U+0001]" in xml and "\x01" not in xml


def test_export_rate_and_concurrency_limits(client, monkeypatch):
    _, path = prepare(client)
    from api.memora import routes
    import threading

    slots = threading.BoundedSemaphore(1)
    slots.acquire()
    monkeypatch.setattr(routes, "_export_slots", slots)
    assert get(client, path).status_code == 429
    slots.release()
    for _ in range(19):
        assert get(client, path).status_code == 200
    assert get(client, path).status_code == 429


def test_historical_report_revision_and_markdown_sections(client):
    mid, path = prepare(client)
    with s.db() as c:
        report = json.loads(
            c.execute("SELECT data FROM reports WHERE id='report1'").fetchone()[0]
        )
        report["summary"][0]["text"] = "Nouveau rapport"
        c.execute(
            "INSERT INTO reports VALUES(?,?,?,?,?)",
            ("report2", mid, 1, json.dumps(report), time.time() + 1),
        )
        meeting = s.meeting(c, mid)
        meeting["report_id"] = "report2"
        s.save(c, meeting)
    historical = get(client, path, "report", "md", report_id="report1").text
    assert "Version historique" in historical and "Version 1" in historical
    assert "Nouveau rapport" not in historical
    current = get(client, path, "report", "md", report_id="report2").text
    assert (
        "Version courante" in current
        and "Version 2" in current
        and "Nouveau rapport" in current
    )
    for heading in [
        "Résumé",
        "Sujets abordés",
        "Décisions",
        "Actions à suivre",
        "Questions ouvertes",
    ]:
        assert "## " + heading in current


def test_legacy_report_strings(client):
    mid, path = prepare(client)
    with s.db() as c:
        c.execute(
            "UPDATE reports SET data=? WHERE meeting=?",
            (
                json.dumps(
                    {
                        "summary": "Résumé ancien",
                        "topics": ["Sujet ancien"],
                        "actions": ["Action ancienne"],
                    }
                ),
                mid,
            ),
        )
    response = get(client, path, "report", "pdf")
    assert response.status_code == 200
    text = "\n".join(
        p.extract_text() for p in PdfReader(BytesIO(response.content)).pages
    )
    assert "Résumé ancien" in text and "Action ancienne" in text


@pytest.mark.parametrize("content", ["transcript", "report"])
def test_preflight_limits(client, monkeypatch, content):
    mid, path = prepare(client)
    with s.db() as c:
        if content == "transcript":
            raw = json.dumps([{"text": "a" * (5 * 1024 * 1024)}])
            c.execute("UPDATE transcripts SET data=? WHERE meeting=?", (raw, mid))
        else:
            raw = json.dumps({"summary": "a" * (5 * 1024 * 1024)})
            c.execute("UPDATE reports SET data=? WHERE meeting=?", (raw, mid))

    def never(*args):
        raise AssertionError("Must not render an oversized source")

    monkeypatch.setattr(exports, "render", never)
    assert get(client, path, content, "pdf").status_code == 413


def test_guest_without_session_cannot_reset_quota(client):
    mid, path = prepare(client)
    headers = share(client, mid, transcript=True)
    for index in range(20):
        assert (
            client.get(
                path,
                params={"content": "transcript", "format": "txt"},
                headers={
                    **headers,
                    "x-guest-session": f"different-synthetic-session-{index}",
                },
            ).status_code
            == 200
        )
    assert (
        client.get(
            path, params={"content": "transcript", "format": "txt"}, headers=headers
        ).status_code
        == 429
    )


def test_docx_title_no_border_and_palette():
    from lxml import etree

    data = exports.docx_document(
        [
            ("title", "Titre synthétique"),
            ("section", "Résumé"),
            ("heading", "01:00:00 - 01:00:01"),
        ]
    )
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(BytesIO(data)) as archive:
        styles = etree.fromstring(archive.read("word/styles.xml"))
        for name in ["Title", "Normal"]:
            style = styles.xpath(f'//w:style[@w:styleId="{name}"]', namespaces=ns)[0]
            assert not style.xpath(".//w:pBdr", namespaces=ns)
        for name, expected in [
            ("Title", "000000"),
            ("Heading1", "6550DF"),
            ("Heading2", "6550DF"),
        ]:
            assert styles.xpath(
                f'//w:style[@w:styleId="{name}"]/w:rPr/w:color/@w:val', namespaces=ns
            ) == [expected]
        document = etree.fromstring(archive.read("word/document.xml"))
        title = document.xpath('//w:p[w:pPr/w:pStyle[@w:val="Title"]]', namespaces=ns)[
            0
        ]
        assert not title.xpath(".//w:pBdr", namespaces=ns)


def test_markdown_source_is_literal_not_active_html_or_links(client):
    mid, path = prepare(client)
    with s.db() as c:
        report = json.loads(
            c.execute("SELECT data FROM reports WHERE id='report1'").fetchone()[0]
        )
        report["summary"] = [
            {
                "text": "<script>bad()</script> ![image](https://example.test/image) # literal *words*",
                "sources": [],
            }
        ]
        c.execute("UPDATE reports SET data=? WHERE id='report1'", (json.dumps(report),))
    response = get(client, path, "report", "md")
    assert response.status_code == 200
    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text
    assert r"\!\[image\]\(" in response.text
    assert r"\# literal \*words\*" in response.text


def test_report_revision_timestamps_ties_match_detail(client):
    mid, path = prepare(client)
    with s.db() as c:
        first = c.execute(
            "SELECT data,created FROM reports WHERE id='report1'"
        ).fetchone()
        c.execute(
            "INSERT INTO reports VALUES(?,?,?,?,?)",
            ("report0", mid, 1, first["data"], first["created"]),
        )
        c.execute(
            "INSERT INTO reports VALUES(?,?,?,?,?)",
            ("report2", mid, 1, first["data"], first["created"]),
        )
        meeting = s.meeting(c, mid)
        meeting["report_id"] = "report2"
        s.save(c, meeting)
    detail = client.get(PREFIX + "/meetings/" + mid).json()
    assert [row["id"] for row in detail["reports"]] == ["report2", "report1", "report0"]
    for row in detail["reports"]:
        response = get(client, path, "report", "txt", report_id=row["id"])
        assert response.status_code == 200
        assert f"Rapport · Version {row['revision']} ·" in response.text
