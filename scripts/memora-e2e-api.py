"""Actual loopback API acceptance run. Never prints credentials, tokens or share URLs."""

import hashlib
import json
import os
import secrets
import sys
import time
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("MEMORA_TEST_API_URL", "http://127.0.0.1:8080")
CREDENTIALS = Path(
    os.environ.get("MEMORA_TEST_CREDENTIALS", str(ROOT / ".memora/demo.json"))
)
MAIL_DIR = Path(os.environ.get("MEMORA_TEST_MAIL_DIR", str(ROOT / ".memora/mail")))
HANDOFF = Path(
    os.environ.get("MEMORA_TEST_HANDOFF_DIR", str(ROOT / "agents/handoffs"))
) / (os.environ.get("MEMORA_TEST_ARTIFACT_PREFIX", "") + "e2e-api.md")
HANDOFF.parent.mkdir(parents=True, exist_ok=True)
checks = []
started = time.monotonic()


def check(condition, label):
    if not condition:
        raise RuntimeError(label)
    checks.append(label)
    print("PASS", label, flush=True)


def main():
    isolated = os.environ.get("MEMORA_TEST_ISOLATED") == "1"
    if isolated:
        marker_path = Path(
            os.environ.get("MEMORA_TEST_ISOLATION_MARKER", "missing-isolation-marker")
        )
        marker = json.loads(marker_path.read_text()) if marker_path.is_file() else {}
        target = urlparse(BASE)
        if not (
            target.hostname == "127.0.0.1"
            and target.port not in (3000, 8080)
            and marker.get("api_url") == BASE
            and marker.get("credentials_path") == str(CREDENTIALS.resolve())
            and CREDENTIALS.resolve().parent.name.startswith("memora-isolated-")
        ):
            raise RuntimeError(
                "Administrative acceptance requires the runner's disposable isolation marker"
            )
    credentials = json.loads(CREDENTIALS.read_text())
    with httpx.Client(base_url=BASE, timeout=360, trust_env=False) as client:

        def call(method, path, expected=200, *, guest=None, password=None, **kwargs):
            headers = dict(kwargs.pop("headers", {}))
            if guest is not None:
                headers.update(
                    {"x-share-token": guest, "x-guest-session": "synthetic-api-qa"}
                )
                if password is not None:
                    headers["x-share-password"] = password
            elif auth:
                headers["Authorization"] = auth
            response = client.request(method, path, headers=headers, **kwargs)
            if response.status_code != expected:
                raise RuntimeError(
                    f"API status mismatch {method} operation: {response.status_code}, expected {expected}"
                )
            return (
                response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else response.content
            )

        auth = None
        login = call(
            "POST",
            "/api/auth/login",
            json={k: credentials[k] for k in ("username", "password")},
        )
        auth = "Bearer " + login["data"]["token"]
        check(bool(auth), "Compte synthétique connecté")
        meeting = call(
            "POST",
            "/api/memora/meetings",
            expected=201,
            json={"title": "QA réelle synthétique FR EN", "mode": "import"},
        )
        mid = meeting["id"]
        route = "/api/memora/meetings/" + mid
        check(meeting["state"] == "draft", "Création réunion persistée")
        audio = (ROOT / "backend/test/fixtures/memora/mixed-native.wav").read_bytes()
        chunks = [audio[n : n + 65536] for n in range(0, len(audio), 65536)]
        call("POST", route + "/chunks?seq=1", expected=409, content=chunks[0])
        for seq, chunk in enumerate(chunks):
            call(
                "POST",
                route + f"/chunks?seq={seq}",
                content=chunk,
                headers={"x-chunk-digest": hashlib.sha256(chunk).hexdigest()},
            )
            if seq == 0:
                duplicate = call("POST", route + "/chunks?seq=0", content=chunk)
                check(
                    duplicate.get("duplicate"), "Fragment idempotent sans duplication"
                )
        check(
            len(call("GET", route)["chunks"]) == len(chunks),
            "Import fragmenté et reprise persistés",
        )
        call("POST", route + "/finalize", json={"expected_chunks": len(chunks)})
        again = call("POST", route + "/finalize", json={"expected_chunks": len(chunks)})
        check(again.get("idempotent"), "Finalisation idempotente")

        def ready(version):
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                value = call("GET", route)
                if value["state"] == "failed":
                    raise RuntimeError(
                        "Traitement réel échoué ; consulter état réunion sans secrets"
                    )
                if value["state"] == "ready" and value.get("report_version") == version:
                    return value
                time.sleep(2)
            raise RuntimeError("Traitement réel dépasse 600 secondes")

        meeting = ready(1)
        check(
            bool(meeting["segments"]) and bool(meeting["reports"]),
            "Transcription et rapport réels prêts",
        )
        source_ids = {x["id"] for x in meeting["segments"]}
        report = meeting["reports"][0]["data"]
        items = [
            i
            for key in ("summary", "topics", "decisions", "actions", "open_questions")
            for i in report[key]
        ]
        check(
            bool(items)
            and all(i["sources"] and set(i["sources"]) <= source_ids for i in items),
            "Toutes références rapport appartiennent à réunion",
        )
        answer = call(
            "POST",
            route + "/chat",
            json={"question": "Qui prépare la démonstration et quand ?"},
        )
        check(
            bool(answer["sources"])
            and set(answer["sources"]) <= source_ids
            and "Alice" in answer["answer"],
            "Chat réel Alice et sources vérifiables",
        )
        absent = call(
            "POST",
            route + "/chat",
            json={"question": "Quel est le numéro de carte bancaire de Bob ?"},
        )
        check(absent["sources"] == [], "Information absente sans fausse citation")
        downloaded = call("GET", route + "/audio")
        check(
            hashlib.sha256(downloaded).digest() == hashlib.sha256(audio).digest(),
            "Audio téléchargé identique à upload",
        )
        corrected = [dict(s) for s in meeting["segments"]]
        corrected[0]["text"] = (
            corrected[0]["text"]
            .replace("Memorale Indie", "Memora lundi")
            .replace("Memoral Indie", "Memora lundi")
        )
        corrected[0]["speaker"] = "Intervenant synthétique"
        result = call(
            "PUT", route + "/transcript", json={"version": 1, "segments": corrected}
        )
        check(
            result["version"] == 2 and result["stale"],
            "Correction version 2 et résultat périmé signalé",
        )
        call(
            "PUT",
            route + "/transcript",
            expected=409,
            json={"version": 1, "segments": corrected},
        )
        stale = call("GET", route)
        check(
            stale["report_version"] == 1 and len(stale["reports"]) == 1,
            "Ancien rapport conservé avant régénération",
        )
        call("POST", route + "/analyze")
        meeting = ready(2)
        check(
            len(meeting["reports"]) == 2
            and {r["version"] for r in meeting["reports"]} == {1, 2},
            "Régénération réelle historique deux rapports",
        )
        share = call("POST", route + "/shares", expected=201, json={})
        token = share["id"]
        guest = call("GET", "/api/memora/share/" + token, guest=token)
        check(
            guest["id"] == mid and guest["segments"], "Accès invité ouvert sans compte"
        )
        call(
            "PUT",
            route + "/transcript",
            expected=403,
            guest=token,
            json={"version": 2, "segments": corrected},
        )
        check(True, "Modification invitée interdite côté backend")
        restricted = call(
            "POST",
            route + "/shares",
            expected=201,
            json={
                "permissions": {
                    "report": True,
                    "transcript": False,
                    "audio": False,
                    "chat": False,
                    "edit": False,
                }
            },
        )
        limited = call(
            "GET", "/api/memora/share/" + restricted["id"], guest=restricted["id"]
        )
        check(
            "segments" not in limited and limited["audio_available"] is False,
            "Partage limité masque transcription et audio",
        )
        call("GET", route + "/audio", expected=403, guest=restricted["id"])
        call(
            "POST",
            route + "/chat",
            expected=403,
            guest=restricted["id"],
            json={"question": "Qui prépare ?"},
        )
        password = secrets.token_urlsafe(16)
        protected = call(
            "POST", route + "/shares", expected=201, json={"password": password}
        )
        call(
            "GET",
            "/api/memora/share/" + protected["id"],
            expected=401,
            guest=protected["id"],
            password="wrong-synthetic",
        )
        unlocked = call(
            "GET",
            "/api/memora/share/" + protected["id"],
            guest=protected["id"],
            password=password,
        )
        check(
            unlocked["id"] == mid,
            "Partage protégé refuse faux mot de passe et accepte correct",
        )
        expiring = call(
            "POST",
            route + "/shares",
            expected=201,
            json={"expires_at": time.time() + 2},
        )
        time.sleep(3)
        call(
            "GET",
            "/api/memora/share/" + expiring["id"],
            expected=404,
            guest=expiring["id"],
        )
        check(True, "Expiration réellement appliquée")
        previous = set(MAIL_DIR.glob("*.eml"))
        invited = call(
            "POST",
            route + "/shares/" + token + "/invite",
            json={
                "emails": [
                    "synthetic-qa-one@example.com",
                    "synthetic-qa-two@example.com",
                ],
                "summary": "Résumé synthétique de recette Memora.",
            },
        )
        check(
            invited["recipients"] == 2,
            "Invitation deux destinataires mise en file capture locale",
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            new = set(MAIL_DIR.glob("*.eml")) - previous
            matching = []
            for file in new:
                message = BytesParser(policy=policy.default).parsebytes(
                    file.read_bytes()
                )
                html_body = message.get_body(preferencelist=("html",))
                if html_body and token in html_body.get_content():
                    matching.append(html_body.get_content())
            if len(matching) >= 2:
                break
            time.sleep(1)
        check(
            len(matching) >= 2
            and all(
                "Accéder à la réunion" in x and "Résumé synthétique" in x
                for x in matching
            ),
            "Deux emails reçus localement avec résumé et bouton accès",
        )
        notifications = call("GET", "/api/memora/notifications")
        check(
            any(n["meeting"] == mid for n in notifications),
            "Notification disponibilité dans application",
        )
        call("DELETE", route + "/shares/" + token)
        call("GET", "/api/memora/share/" + token, expected=404, guest=token)
        call("GET", route + "/audio", expected=404, guest=token)
        check(True, "Révocation retire accès réunion et fichier audio")
        check(
            call("PATCH", route, json={"archived": True})["archived"],
            "Archivage distinct suppression",
        )
        check(
            call("PATCH", route, json={"archived": False})["archived"] is False,
            "Restauration archive conserve réunion",
        )
        if isolated:
            initial = call("GET", "/api/memora/settings")
            check(
                initial.get("can_administer"),
                "Compte jetable autorisé à administrer la recette isolée",
            )
            initial.pop("can_administer", None)
            old_snapshot = call("GET", route)["settings"]
            configured = {
                **initial,
                "max_duration_minutes": 90
                if initial["max_duration_minutes"] != 90
                else 120,
                "max_upload_mb": 200 if initial["max_upload_mb"] != 200 else 250,
                "audio_retention_days": 14
                if initial["audio_retention_days"] != 14
                else 30,
                "allow_guest_edit": True,
            }
            new_mid = None
            try:
                saved = call("PUT", "/api/memora/settings", json=configured)
                check(
                    saved == configured,
                    "Configuration administrative valide réellement sauvegardée",
                )
                fresh = call(
                    "POST",
                    "/api/memora/meetings",
                    expected=201,
                    json={"title": "Snapshot paramètres synthétique"},
                )
                new_mid = fresh["id"]
                check(
                    fresh["settings"] == configured
                    and call("GET", route)["settings"] == old_snapshot,
                    "Nouveaux paramètres appliqués aux réunions futures sans rétroactivité",
                )
                editable = call(
                    "POST",
                    route + "/shares",
                    expected=201,
                    json={
                        "permissions": {"edit": True, "audio": True, "transcript": True}
                    },
                )
                current = call("GET", route)
                edited = [dict(segment) for segment in current["segments"]]
                edited[0]["speaker"] = "Invité synthétique de recette"
                correction = call(
                    "PUT",
                    route + "/transcript",
                    guest=editable["id"],
                    json={
                        "version": current["version"],
                        "segments": edited,
                        "editor_name": "Éditeur synthétique",
                    },
                )
                current = call("GET", route)
                check(
                    correction["version"] == 3
                    and current["segments"][0]["speaker"] == edited[0]["speaker"],
                    "Invité explicitement autorisé corrige réellement une transcription",
                )
                call(
                    "PUT",
                    "/api/memora/settings",
                    json={**configured, "allow_guest_edit": False},
                )
                call(
                    "PUT",
                    route + "/transcript",
                    expected=403,
                    guest=editable["id"],
                    json={
                        "version": 3,
                        "segments": edited,
                        "editor_name": "Éditeur synthétique",
                    },
                )
                denied = call(
                    "GET", "/api/memora/share/" + editable["id"], guest=editable["id"]
                )
                check(
                    denied["permissions"]["edit"] is False
                    and call("GET", route)["version"] == 3,
                    "Désactivation administrative retire les droits d’un ancien lien invité",
                )
                historical_reports = {report["id"] for report in current["reports"]}
                historical_versions = {
                    version["version"] for version in current["transcript_versions"]
                }
                request_id = "isolated-asr-" + secrets.token_hex(8)
                request_body = {"request_id": request_id, "language": "auto"}
                submitted = call("POST", route + "/retranscribe", json=request_body)
                repeated = call("POST", route + "/retranscribe", json=request_body)
                check(
                    repeated.get("idempotent")
                    and submitted["job_id"] == repeated["job_id"],
                    "Retranscription réelle dédupliquée par identifiant de requête",
                )
                retranscribed = ready(4)
                check(
                    bool(retranscribed["segments"])
                    and historical_reports
                    <= {report["id"] for report in retranscribed["reports"]}
                    and len(retranscribed["reports"]) == len(historical_reports) + 1
                    and historical_versions | {4}
                    <= {
                        version["version"]
                        for version in retranscribed["transcript_versions"]
                    },
                    "Nouvelle ASR et nouveau rapport prêts avec toutes les versions antérieures conservées",
                )
                repeated = call("POST", route + "/retranscribe", json=request_body)
                unchanged = call("GET", route)
                check(
                    repeated.get("idempotent")
                    and repeated["job_id"] == submitted["job_id"]
                    and unchanged["version"] == 4
                    and len(unchanged["reports"]) == len(retranscribed["reports"]),
                    "Rejeu après retranscription terminée ne crée aucune nouvelle version",
                )
            finally:
                call("PUT", "/api/memora/settings", json=initial)
                restored = call("GET", "/api/memora/settings")
                restored.pop("can_administer", None)
                check(
                    restored == initial,
                    "Configuration administrative initiale restaurée après recette",
                )
                if new_mid:
                    call("DELETE", "/api/memora/meetings/" + new_mid)

        if isolated and os.environ.get("MEMORA_FRENCH_ASR_ENGINE") == "parakeet-mlx":
            # Exercise the actual optional final-French route, which the bilingual
            # acceptance fixture deliberately does not select. Disposable data only.
            original_route = route
            french_mid = None
            try:
                french = call(
                    "POST",
                    "/api/memora/meetings",
                    expected=201,
                    json={
                        "title": "QA route française locale",
                        "mode": "import",
                        "transcription_language": "fr",
                    },
                )
                french_mid = french["id"]
                route = "/api/memora/meetings/" + french_mid
                call(
                    "POST",
                    route + "/chunks?seq=0",
                    content=(
                        ROOT / "backend/test/fixtures/memora/french.wav"
                    ).read_bytes(),
                )
                call("POST", route + "/finalize", json={"expected_chunks": 1})
                french = ready(1)
                check(
                    bool(french["segments"])
                    and all(
                        segment.get("language") == "unknown"
                        for segment in french["segments"]
                    ),
                    "Route française réelle : transcription et rapport prêts sans langue détectée inventée",
                )
                current_report = next(
                    item
                    for item in french["reports"]
                    if item["id"] == french["report_id"]
                )
                review_category = (
                    "actions" if current_report["data"].get("actions") else "decisions"
                )
                check(
                    bool(current_report["data"].get(review_category)),
                    "Rapport réel fournit un élément sourcé à réviser",
                )
                review_path = route + "/reports/" + current_report["id"] + "/reviews"
                human = call(
                    "PUT",
                    review_path + "/" + review_category + "/0",
                    json={
                        "transcript_version": 1,
                        "expected_revision": 0,
                        "status": "confirmed",
                        "corrections": {},
                    },
                )
                call(
                    "PUT",
                    review_path + "/" + review_category + "/0",
                    expected=409,
                    json={
                        "transcript_version": 1,
                        "expected_revision": 0,
                        "status": "cancelled",
                    },
                )
                reviewed = call("GET", review_path)
                same_report = next(
                    item
                    for item in call("GET", route)["reports"]
                    if item["id"] == current_report["id"]
                )
                check(
                    human["provenance"] == "human_review"
                    and reviewed["history"][0]["status"] == "confirmed"
                    and same_report["data"] == current_report["data"],
                    "Validation humaine réelle historisée, conflit détecté et sortie IA inchangée",
                )
                edited = [dict(segment) for segment in french["segments"]]
                edited[0]["speaker"] = "Voix synthétique française"
                updated = call(
                    "PUT",
                    route + "/transcript",
                    json={"version": 1, "segments": edited},
                )
                saved = call("GET", route)
                check(
                    updated["version"] == 2
                    and updated["stale"]
                    and saved["segments"][0]["speaker"] == edited[0]["speaker"]
                    and saved["segments"][0]["language"] == "unknown"
                    and saved["report_version"] == 1
                    and len(saved["reports"]) == 1,
                    "Correction de la nouvelle ASR persistée sans422, ancien rapport conservé et périmé",
                )
                check(
                    call("GET", review_path)["stale"],
                    "Correction rend aussi la validation humaine précédente périmée",
                )
                renamed = call(
                    "POST",
                    route + "/speakers/rename",
                    json={
                        "version": 2,
                        "from_speaker": edited[0]["speaker"],
                        "to_speaker": "Intervenant synthétique relu",
                    },
                )
                renamed_meeting = call("GET", route)
                check(
                    renamed["version"] == 3
                    and renamed_meeting["segments"][0]["speaker"]
                    == "Intervenant synthétique relu"
                    and renamed_meeting["report_version"] == 1,
                    "Renommage global réel crée une version sans effacer le rapport",
                )
                speaker_request = {
                    "version": 3,
                    "request_id": "isolated-speakers-" + secrets.token_hex(8),
                    "num_speakers": 1,
                }
                submitted_speakers = call(
                    "POST", route + "/diarize", json=speaker_request
                )
                deadline = time.monotonic() + 180
                separated = None
                while time.monotonic() < deadline:
                    separated = call("GET", route)
                    if separated["state"] == "failed":
                        raise RuntimeError("Séparation locale réelle échouée")
                    if separated["state"] == "ready" and separated["version"] == 4:
                        break
                    time.sleep(1)
                check(
                    separated is not None
                    and separated["version"] == 4
                    and separated["report_version"] == 1
                    and len(separated["reports"]) == 1
                    and separated.get("diarization", {}).get("engine")
                    and [item["text"] for item in separated["segments"]]
                    == [item["text"] for item in renamed_meeting["segments"]],
                    "Job de séparation vocale réel terminé, texte et ancien rapport conservés",
                )
                repeated_speakers = call(
                    "POST", route + "/diarize", json=speaker_request
                )
                check(
                    repeated_speakers.get("idempotent")
                    and repeated_speakers["job_id"] == submitted_speakers["job_id"]
                    and call("GET", route)["version"] == 4,
                    "Rejeu après séparation réelle ne crée pas de version supplémentaire",
                )

            finally:
                route = original_route
                if french_mid:
                    call("DELETE", "/api/memora/meetings/" + french_mid)

        elapsed = round(time.monotonic() - started, 2)
        text = "# Recette API réelle synthétique\n\n"
        isolated = os.environ.get("MEMORA_TEST_ISOLATED") == "1"
        text += f"Réunion synthétique {'temporaire et supprimée après recette' if isolated else 'conservée pour démonstration'} : `{mid}`. Durée totale : {elapsed}s.\n\n"
        text += f"Exécution : `backend/.venv/bin/python scripts/memora-e2e-api.py` sur {BASE} ; compte {'jetable isolé' if isolated else 'local de démonstration'} (aucun secret affiché).\n\n"
        text += "\n".join("- VALIDÉ : " + label for label in checks)
        text += "\n\nPortée : API + persistance + Whisper/Ollama réels + capture SMTP locale. Aucun test microphone physique ni délivrabilité email externe. Navigateur géré par intégrateur.\n"
        HANDOFF.write_text(text)
        print("SUCCESS", len(checks), "checks", elapsed, "seconds", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 -- sanitize recipe boundary errors
        # Never echo response bodies, HTTP URLs or credentials in errors.
        reason = (
            str(exc)
            if isinstance(exc, RuntimeError)
            else "Diagnostic ciblé nécessaire sans secrets"
        )
        print("FAILED", type(exc).__name__, reason, flush=True)
        HANDOFF.write_text(
            "# Recette API interrompue\n\n"
            + "\n".join("- VALIDÉ : " + label for label in checks)
            + "\n\nÉchec : "
            + reason
            + ". Aucun secret enregistré.\n"
        )
        sys.exit(1)
