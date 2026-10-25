"""Meeting API: authorization is enforced for every resource, including guest access."""

import hashlib
import html
import json
import secrets
import shutil
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, EmailStr
from werkzeug.security import generate_password_hash, check_password_hash

from api.services.authorization import current_user
from . import store as s, ai
from .worker import queue_mail

AUTH_USER = Depends(current_user)

router = APIRouter(prefix="/api/memora", tags=["Memora"])


def error(code, message):
    raise HTTPException(code, message)


def audio_expired(m):
    return (
        bool(m.get("audio_expired"))
        or m.get("audio_expires_at", float("inf")) <= time.time()
    )


def limit(c, key, maximum=60, seconds=60):
    # Keys are digests: addresses, tokens and IPs are not persisted in clear text.
    key = hashlib.sha256(key.encode()).hexdigest()
    window = int(time.time()) // seconds
    c.execute(
        "INSERT INTO limits VALUES(?,?,1) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN window=? THEN count+1 ELSE 1 END,window=?",
        (key, window, window, window),
    )
    count = c.execute("SELECT count FROM limits WHERE key=?", (key,)).fetchone()[0]
    c.commit()  # Persist failed-attempt counters too. Called before domain mutations.
    if count > maximum:
        error(429, "Trop de requêtes. Réessayez dans une minute.")


def share_access(c, request, mid, capability):
    token = request.headers.get("x-share-token", "")
    row = c.execute("SELECT meeting,data FROM shares WHERE id=?", (token,)).fetchone()
    if not row or row["meeting"] != mid:
        error(404, "Lien indisponible, expiré ou révoqué.")
    sh = json.loads(row["data"])
    if sh.get("revoked") or (
        sh.get("expires_at") is not None and sh["expires_at"] <= time.time()
    ):
        error(404, "Lien indisponible, expiré ou révoqué.")
    password = request.headers.get("x-share-password", "")
    if sh.get("password_hash"):
        unlock_key = (
            "unlock:" + token + ":" + (request.client.host if request.client else "")
        )
        digest = hashlib.sha256(unlock_key.encode()).hexdigest()
        attempts = c.execute(
            "SELECT window,count FROM limits WHERE key=?", (digest,)
        ).fetchone()
        if (
            attempts
            and attempts["window"] == int(time.time()) // 60
            and attempts["count"] >= 20
        ):
            error(429, "Trop de tentatives. Réessayez dans une minute.")
        if not check_password_hash(sh["password_hash"], password):
            # Legitimate polling does not consume the failed-guess quota.
            limit(c, unlock_key, 20)
            error(401, "Mot de passe requis ou incorrect.")
    if capability == "edit" and (
        not s.config(c)["allow_guest_edit"] or not sh["permissions"].get("transcript")
    ):
        error(403, "Modification invitée désactivée.")
    if not sh["permissions"].get(capability, False):
        error(403, "Ce partage ne permet pas cette action.")
    guest_session = request.headers.get("x-guest-session", "")
    # Never give unrelated visitors who omit a session a common chat history.
    if len(guest_session) < 16 or len(guest_session) > 128:
        guest_session = secrets.token_urlsafe(24)
    actor = (
        "guest:" + hashlib.sha256((token + ":" + guest_session).encode()).hexdigest()
    )
    return sh, actor


async def access(request, mid, capability="view"):
    with s.db() as c:
        m = s.meeting(c, mid)
        if not m or not m.get("owner_uid") or s.owner_deleted(c, m["owner_uid"]):
            error(404, "Réunion indisponible.")
        if request.headers.get("x-share-token"):
            sh, actor = share_access(c, request, mid, capability)
            rights = dict(sh["permissions"])
            rights["edit"] = bool(
                rights.get("edit")
                and rights.get("transcript")
                and s.config(c)["allow_guest_edit"]
            )
            return m, rights, actor
    # Reuse existing template JWT validation and database identity, including revocation.
    from api.services.jwt import getPayload
    from api.database import get_db

    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        error(401, "Connexion requise.")
    gen = get_db()
    db = next(gen)
    try:
        payload = getPayload(request, auth[7:], db)
        from api.database import User

        user = User.get(db=db, username=payload["username"])
        if (
            user.id != m["owner"]
            or not m.get("owner_uid")
            or m["owner_uid"] != user.account_uid
        ):
            error(404, "Réunion indisponible.")
        return (
            m,
            {
                k: True
                for k in (
                    "view",
                    "report",
                    "transcript",
                    "audio",
                    "chat",
                    "edit",
                    "manage",
                )
            },
            f"user:{user.id}",
        )
    finally:
        gen.close()


def public_meeting(c, m, rights, actor):
    result = {
        k: v
        for k, v in m.items()
        if k not in ("owner", "owner_uid", "email", "live_segments")
    }
    result["permissions"] = rights
    if not rights.get("audio"):
        result.pop("filename", None)
        result.pop("mime_type", None)
    result["audio_available"] = bool(
        rights.get("audio")
        and not audio_expired(m)
        and (s.ROOT / m["id"] / "audio.bin").exists()
    )
    if rights.get("transcript"):
        result["segments"] = s.transcript(c, m["id"], m["version"])
        result["live_segments"] = m.get("live_segments", [])
        result["transcript_versions"] = [
            dict(r)
            for r in c.execute(
                "SELECT version,author,created FROM transcripts WHERE meeting=? ORDER BY version DESC",
                (m["id"],),
            )
        ]
    if rights.get("report"):
        reports = []
        for r in c.execute(
            "SELECT * FROM reports WHERE meeting=? ORDER BY created DESC", (m["id"],)
        ):
            d = dict(r)
            d.pop("meeting", None)
            d["data"] = json.loads(d["data"])
            if not rights.get("transcript"):
                for key in (
                    "summary",
                    "topics",
                    "decisions",
                    "actions",
                    "open_questions",
                ):
                    for item in d["data"][key]:
                        item["sources"] = []
            reports.append(d)
        for revision, historical in enumerate(reversed(reports), start=1):
            historical["revision"] = revision
        result["reports"] = reports
    if rights.get("manage"):
        result["jobs"] = [
            dict(r)
            for r in c.execute(
                "SELECT id,kind,version,state,error,created,finished FROM jobs WHERE meeting=? ORDER BY created DESC",
                (m["id"],),
            )
        ]
        result["chunks"] = [
            dict(r)
            for r in c.execute(
                "SELECT seq,bytes FROM chunks WHERE meeting=? ORDER BY seq", (m["id"],)
            )
        ]
        result["shares"] = shares_list(c, m["id"])
    if rights.get("chat"):
        result["chat"] = [
            {
                **json.loads(r["data"]),
                "id": r["id"],
                "version": r["version"],
                "created": r["created"],
            }
            for r in c.execute(
                "SELECT * FROM chats WHERE meeting=? AND actor=? ORDER BY created",
                (m["id"], actor),
            )
        ]
    return result


class CreateMeeting(BaseModel):
    title: str = Field(default="Réunion sans titre", max_length=200)
    mode: Literal["recording", "import"] = "import"
    transcription_language: Literal["auto", "fr", "en"] = "auto"
    meeting_date: str | None = Field(default=None, max_length=40)


@router.get("/meetings")
def meetings(user=AUTH_USER):
    with s.db() as c:
        rows = c.execute("SELECT id FROM meetings WHERE owner=?", (user.id,)).fetchall()
        return sorted(
            [
                {
                    key: value
                    for key, value in m.items()
                    if key not in ("live_segments", "email", "owner", "owner_uid")
                }
                for r in rows
                if (m := s.meeting(c, r[0])).get("owner_uid") == user.account_uid
            ],
            key=lambda m: m["created"],
            reverse=True,
        )


@router.post("/meetings", status_code=201)
def create_meeting(body: CreateMeeting, user=AUTH_USER):
    with s.db() as c:
        limit(c, f"create:{user.id}", 20)
        c.execute("BEGIN IMMEDIATE")
        if s.owner_deleted(c, user.account_uid):
            error(
                403,
                "Compte en cours de suppression. Réessayez la suppression du compte.",
            )
        mid = s.uid()
        m = {
            "id": mid,
            "owner_uid": user.account_uid,
            "title": body.title.strip() or "Réunion sans titre",
            "mode": body.mode,
            "transcription_language": body.transcription_language,
            "meeting_date": body.meeting_date,
            "created": time.time(),
            "updated": time.time(),
            "state": "draft",
            "archived": False,
            "version": 0,
            "report_version": None,
            "report_id": None,
            "settings": s.config(c),
            "duration": 0,
            "error": None,
            "email": user.email,
            "audio_expired": False,
        }
        m["audio_expires_at"] = (
            time.time() + m["settings"]["audio_retention_days"] * 86400
        )
        c.execute("INSERT INTO meetings VALUES(?,?,?)", (mid, user.id, json.dumps(m)))
        s.audit(c, f"user:{user.id}", mid, "create")
    return m


@router.get("/meetings/{mid}")
async def get_meeting(mid: str, request: Request):
    m, rights, actor = await access(request, mid)
    with s.db() as c:
        return public_meeting(c, m, rights, actor)


class MeetingPatch(BaseModel):
    transcription_language: Literal["auto", "fr", "en"] | None = None
    filename: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    archived: bool | None = None
    state: Literal["recording", "paused", "interrupted"] | None = None


@router.patch("/meetings/{mid}")
async def patch_meeting(mid: str, body: MeetingPatch, request: Request):
    _, _, actor = await access(request, mid, "manage")
    with s.db() as c:
        c.execute("BEGIN IMMEDIATE")
        m = s.meeting(c, mid)
        if not m:
            error(404, "Réunion indisponible.")
        changes = body.model_dump(exclude_none=True)
        if "transcription_language" in changes and m["state"] not in (
            "draft",
            "recording",
            "paused",
            "interrupted",
        ):
            error(
                409,
                "Choisissez la langue lors d’une nouvelle transcription de l’audio.",
            )
        if changes.get("filename"):
            changes["filename"] = (
                changes["filename"].replace("\\", "/").rsplit("/", 1)[-1]
            )
        if "state" in changes and m["state"] not in (
            "draft",
            "recording",
            "paused",
            "interrupted",
        ):
            error(409, "La capture est déjà finalisée.")
        m.update(changes, updated=time.time())
        s.save(c, m)
        s.audit(c, actor, mid, "update:" + ",".join(changes))
    return m


@router.delete("/meetings/{mid}")
async def delete_meeting(mid: str, request: Request):
    _, _, actor = await access(request, mid, "manage")
    with s.db() as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            s.purge_meeting(c, mid)
        except OSError:
            error(
                503,
                "Suppression des fichiers interrompue. Réessayez ; la réunion reste référencée.",
            )
        s.audit(c, actor, mid, "delete")
    return {"deleted": True}


@router.post("/meetings/{mid}/chunks")
async def upload_chunk(mid: str, request: Request, seq: int = 0):
    m, _, _ = await access(request, mid, "manage")
    if seq < 0 or seq > 100000:
        error(422, "Numéro de fragment invalide.")
    body = bytearray()
    async for data in request.stream():
        body.extend(data)
        if len(body) > 5 * 1024 * 1024:
            error(413, "Fragment limité à 5 Mo.")
    if not body:
        error(422, "Fragment vide.")
    digest = hashlib.sha256(body).hexdigest()
    supplied = request.headers.get("x-chunk-digest")
    if supplied and supplied != digest:
        error(422, "Intégrité du fragment invalide.")
    with s.db() as c:
        c.execute("BEGIN IMMEDIATE")
        m = s.meeting(c, mid)
        if not m or m["state"] not in ("draft", "recording", "paused", "interrupted"):
            error(409, "Transfert fermé : réunion déjà finalisée.")
        if audio_expired(m):
            error(
                410,
                "La durée de conservation de cet audio est dépassée. Créez une nouvelle réunion.",
            )
        existing = c.execute(
            "SELECT digest FROM chunks WHERE meeting=? AND seq=?", (mid, seq)
        ).fetchone()
        if existing:
            if existing[0] != digest:
                error(409, "Un autre fragment existe à cette position.")
            return {"seq": seq, "saved": True, "duplicate": True}
        count, total = c.execute(
            "SELECT count(*),coalesce(sum(bytes),0) FROM chunks WHERE meeting=?", (mid,)
        ).fetchone()
        if seq != count:
            error(409, f"Fragment manquant. Prochain attendu : {count}.")
        if total + len(body) > m["settings"]["max_upload_mb"] * 1024 * 1024:
            error(413, "Taille maximale de la réunion dépassée.")
        if shutil.disk_usage(s.ROOT).free < len(body) + 512 * 1024 * 1024:
            error(507, "Espace disque insuffisant : conservez au moins 512 Mo libres.")
        folder = s.ROOT / mid
        folder.mkdir(exist_ok=True)
        path = folder / "audio.bin"
        # Reconcile a possible crash between file append and database commit.
        with path.open("r+b" if path.exists() else "wb") as f:
            f.truncate(total)
            f.seek(total)
            f.write(body)
            f.flush()
            import os

            os.fsync(f.fileno())
        c.execute("INSERT INTO chunks VALUES(?,?,?,?)", (mid, seq, digest, len(body)))
        if m["mode"] == "recording" and total + len(body) > 10000 and seq % 3 == 0:
            s.enqueue(c, mid, "live", 0)
    return {"seq": seq, "saved": True, "bytes": len(body)}


class Finalize(BaseModel):
    expected_chunks: int = Field(ge=1, le=100001)


@router.post("/meetings/{mid}/finalize")
async def finalize(mid: str, body: Finalize, request: Request):
    m, _, _ = await access(request, mid, "manage")
    with s.db() as c:
        c.execute("BEGIN IMMEDIATE")
        m = s.meeting(c, mid)
        if not m:
            error(404, "Réunion indisponible.")
        if m["state"] in ("queued", "transcribing", "analyzing", "ready"):
            return {"state": m["state"], "idempotent": True}
        if audio_expired(m):
            error(410, "La durée de conservation de cet audio est dépassée.")
        count = c.execute(
            "SELECT count(*) FROM chunks WHERE meeting=?", (mid,)
        ).fetchone()[0]
        if count != body.expected_chunks:
            error(
                409,
                f"Audio incomplet : {count}/{body.expected_chunks} fragments reçus.",
            )
        try:
            duration = ai.validate_audio(
                s.ROOT / mid / "audio.bin", m["settings"]["max_duration_minutes"] * 60
            )
        except ValueError as exc:
            error(422, str(exc))
        m.update(duration=duration, state="queued", error=None)
        s.save(c, m)
        job = s.enqueue(c, mid, "pipeline", m["version"])
        m["active_job_id"] = job
        s.save(c, m)
    return {"state": "queued", "job_id": job}


class AnalyzeRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")


@router.post("/meetings/{mid}/analyze")
async def analyze(mid: str, request: Request, body: AnalyzeRequest | None = None):
    m, rights, _ = await access(request, mid, "edit")
    with s.db() as c:
        limit(c, "analyze:" + mid, 6)
        c.execute("BEGIN IMMEDIATE")
        m = s.meeting(c, mid)
        if not m:
            error(404, "Réunion indisponible.")
        if not m["version"] and not m["duration"]:
            error(409, "Finalisez un audio valide avant analyse.")
        logical_id = body.request_id if body else f"source_{m['version']}"
        existing = c.execute(
            "SELECT j.id,j.state FROM analysis_requests a JOIN jobs j ON j.id=a.job WHERE a.meeting=? AND a.request_id=?",
            (mid, logical_id),
        ).fetchone()
        if existing and not (not body and existing["state"] == "failed"):
            if m["state"] == "failed" and existing["state"] == "queued":
                m.update(state="queued", error=None, active_job_id=existing["id"])
                s.save(c, m)
            return {
                "state": existing["state"],
                "job_id": existing["id"],
                "idempotent": True,
            }
        if existing:
            logical_id = "retry_" + s.uid()
        if not body and m["report_version"] == m["version"] and m["state"] == "ready":
            return {"state": "ready", "idempotent": True}
        if c.execute(
            "SELECT 1 FROM jobs WHERE meeting=? AND kind='retranscribe' AND state IN ('queued','running')",
            (mid,),
        ).fetchone():
            error(409, "Une nouvelle transcription est déjà en cours.")
        # A pipeline without source segments retries ASR and therefore reads audio.
        # Report-only regeneration must remain available without audio permission.
        # Existing request IDs above do not create another processing operation.
        if not s.transcript(c, mid, m["version"]):
            if not rights.get("audio"):
                error(403, "Ce partage ne permet pas de retranscrire l’audio.")
            if audio_expired(m):
                error(410, "La durée de conservation de cet audio est dépassée.")
            if not (s.ROOT / mid / "audio.bin").is_file():
                error(404, "Audio indisponible pour une nouvelle transcription.")
        job = s.enqueue(c, mid, "pipeline", m["version"])
        c.execute("INSERT INTO analysis_requests VALUES(?,?,?)", (mid, logical_id, job))
        m.update(state="queued", error=None, active_job_id=job)
        s.save(c, m)
    return {"job_id": job, "state": "queued"}


class RetranscribeRequest(AnalyzeRequest):
    language: Literal["auto", "fr", "en"] | None = None


@router.post("/meetings/{mid}/retranscribe")
async def retranscribe(mid: str, body: RetranscribeRequest, request: Request):
    m, _, _ = await access(request, mid, "edit")
    await access(request, mid, "audio")
    with s.db() as c:
        limit(c, "retranscribe:" + mid, 3)
        c.execute("BEGIN IMMEDIATE")
        m = s.meeting(c, mid)
        if not m or audio_expired(m) or not (s.ROOT / mid / "audio.bin").exists():
            error(404, "Audio indisponible pour une nouvelle transcription.")
        if not m.get("duration"):
            error(409, "Finalisez un audio valide avant de le retranscrire.")
        logical_id = "asr_" + body.request_id
        existing = c.execute(
            "SELECT j.id,j.state FROM analysis_requests a JOIN jobs j ON j.id=a.job WHERE a.meeting=? AND a.request_id=?",
            (mid, logical_id),
        ).fetchone()
        if existing:
            return {
                "job_id": existing["id"],
                "state": existing["state"],
                "idempotent": True,
            }
        if c.execute(
            "SELECT 1 FROM jobs WHERE meeting=? AND kind!='live' AND state IN ('queued','running')",
            (mid,),
        ).fetchone():
            error(
                409,
                "Un traitement est déjà en cours. Attendez sa fin avant de retranscrire.",
            )
        job = s.enqueue(c, mid, "retranscribe", m["version"])
        c.execute("INSERT INTO analysis_requests VALUES(?,?,?)", (mid, logical_id, job))
        m.update(state="queued", error=None, active_job_id=job)
        if body.language:
            m["transcription_language"] = body.language
        s.save(c, m)
    return {"job_id": job, "state": "queued"}


@router.get("/meetings/{mid}/transcript")
async def read_transcript(mid: str, request: Request, version: int | None = None):
    m, _, _ = await access(request, mid, "transcript")
    version = m["version"] if version is None else version
    with s.db() as c:
        row = c.execute(
            "SELECT author,created FROM transcripts WHERE meeting=? AND version=?",
            (mid, version),
        ).fetchone()
        if not row:
            error(404, "Version de transcription indisponible.")
        return {
            "version": version,
            "segments": s.transcript(c, mid, version),
            "created": row["created"],
        }


class Segment(BaseModel):
    id: str = Field(pattern=r"^s[0-9]+$")
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str = Field(max_length=10000)
    speaker: str = Field(default="Intervenant non identifié", max_length=100)
    language: str = Field(default="unknown", max_length=20)
    uncertain: bool = False


class Correction(BaseModel):
    version: int = Field(ge=1)
    segments: list[Segment] = Field(max_length=50000)
    editor_name: str | None = Field(default=None, min_length=2, max_length=100)


@router.put("/meetings/{mid}/transcript")
async def correct(mid: str, body: Correction, request: Request):
    _, rights, actor = await access(request, mid, "edit")
    with s.db() as c:
        c.execute("BEGIN IMMEDIATE")
        m = s.meeting(c, mid)
        if not m:
            error(404, "Réunion indisponible.")
        if actor.startswith("guest:") and (
            not s.config(c)["allow_guest_edit"]
            or not rights.get("transcript")
            or not body.editor_name
        ):
            error(403, "Modification invitée désactivée ou nom d’éditeur manquant.")
        if m["version"] != body.version:
            error(409, "La transcription a changé. Rechargez avant de corriger.")
        old = s.transcript(c, mid, m["version"])
        new = [x.model_dump() for x in body.segments]
        if [(x["id"], x["start"], x["end"]) for x in old] != [
            (x["id"], x["start"], x["end"]) for x in new
        ]:
            error(
                422,
                "Seuls le texte, le nom et l’incertitude peuvent être corrigés ; repères audio immuables.",
            )
        m["version"] += 1
        c.execute(
            "INSERT INTO transcripts VALUES(?,?,?,?,?)",
            (
                mid,
                m["version"],
                json.dumps(new),
                actor + (":" + body.editor_name if body.editor_name else ""),
                time.time(),
            ),
        )
        m["updated"] = time.time()
        m["state"] = "ready" if m.get("report_id") else "failed"
        m["error"] = (
            None
            if m.get("report_id")
            else "Transcription modifiée : relancez l’analyse."
        )
        s.save(c, m)
        s.audit(c, actor, mid, "transcript_corrected:v" + str(m["version"]))
    return {"version": m["version"], "stale": True}


class Question(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


@router.post("/meetings/{mid}/chat")
async def chat(mid: str, body: Question, request: Request):
    m, rights, actor = await access(request, mid, "chat")
    with s.db() as c:
        quota_actor = request.headers.get("x-share-token") or actor
        limit(c, "chat:" + quota_actor, 20)
        version = m["version"]
        if rights.get("transcript"):
            segments = s.transcript(c, mid, version)
        elif rights.get("report"):
            # Explicit visible-only policy when source transcript is not shared.
            row = c.execute(
                "SELECT data FROM reports WHERE id=?", (m["report_id"],)
            ).fetchone()
            report = json.loads(row[0]) if row else {}
            segments = [
                {"id": f"r{i}", "text": item["text"]}
                for i, item in enumerate(
                    item
                    for key in (
                        "summary",
                        "topics",
                        "decisions",
                        "actions",
                        "open_questions",
                    )
                    for item in report.get(key, [])
                )
            ]
        else:
            segments = []
    if not segments:
        error(409, "Aucun contenu autorisé disponible pour le chat.")
    try:
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(
            ai.answer, segments, body.question, m["settings"]["report_language"]
        )
    except Exception:
        error(
            503, "Modèle local indisponible. Réessayez ; votre réunion est conservée."
        )
    # Revalidate after a slow model call: revoke/expire/correct during inference.
    current, _, _ = await access(request, mid, "chat")
    if current["version"] != version:
        error(
            409, "La source a changé pendant la réponse. Posez à nouveau la question."
        )
    if not rights.get("transcript"):
        result["sources"] = []
    result.update(question=body.question, version=version)
    with s.db() as c:
        c.execute(
            "INSERT INTO chats VALUES(?,?,?,?,?,?)",
            (s.uid(), mid, actor, version, json.dumps(result), time.time()),
        )
    return result


@router.get("/meetings/{mid}/audio")
async def audio(mid: str, request: Request):
    m, _, _ = await access(request, mid, "audio")
    path = s.ROOT / mid / "audio.bin"
    if audio_expired(m) or not path.exists():
        error(404, "Audio indisponible ou arrivé à échéance de conservation.")
    # PyAV probe supplies browser-compatible MIME independent of user filename.
    import av

    with av.open(str(path)) as container:
        fmt = container.format.name
    mime = (
        "audio/webm"
        if "webm" in fmt
        else "audio/wav"
        if "wav" in fmt
        else "audio/mpeg"
        if "mp3" in fmt
        else "audio/mp4"
        if "mp4" in fmt
        else "audio/ogg"
        if "ogg" in fmt
        else "application/octet-stream"
    )
    return FileResponse(
        path, media_type=mime, headers={"Cache-Control": "no-store, private"}
    )


class Permissions(BaseModel):
    report: bool = True
    transcript: bool = True
    audio: bool = True
    chat: bool = True
    edit: bool = False


class ShareCreate(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=200)
    permissions: Permissions = Field(default_factory=Permissions)
    expires_at: float | None = None


def shares_list(c, mid):
    result = []
    for row in c.execute("SELECT id,data FROM shares WHERE meeting=?", (mid,)):
        sh = json.loads(row["data"])
        sh["protected"] = bool(sh.pop("password_hash", None))
        result.append({"id": row["id"], **sh})
    return result


@router.get("/meetings/{mid}/shares")
async def list_shares(mid: str, request: Request):
    await access(request, mid, "manage")
    with s.db() as c:
        return shares_list(c, mid)


@router.post("/meetings/{mid}/shares", status_code=201)
async def create_share(mid: str, body: ShareCreate, request: Request):
    _, _, actor = await access(request, mid, "manage")
    with s.db() as c:
        limit(c, "share:" + actor, 20)
        permissions = body.permissions.model_dump()
        if not any(permissions[k] for k in ("report", "transcript", "audio", "chat")):
            error(422, "Choisissez au moins un contenu.")
        if permissions["edit"] and (
            not s.config(c)["allow_guest_edit"] or not permissions["transcript"]
        ):
            error(
                422,
                "Modification invitée autorisée uniquement si activée et transcription partagée.",
            )
        if (
            body.expires_at is not None
            and not time.time() < body.expires_at <= time.time() + 366 * 86400
        ):
            error(422, "Expiration entre maintenant et 366 jours requise.")
        token = secrets.token_urlsafe(32)
        sh = {
            "permissions": {**permissions, "view": True},
            "expires_at": body.expires_at,
            "revoked": False,
            "created": time.time(),
            "password_hash": generate_password_hash(body.password)
            if body.password
            else None,
        }
        c.execute("INSERT INTO shares VALUES(?,?,?)", (token, mid, json.dumps(sh)))
        s.audit(c, actor, mid, "share_created")
    return {
        "id": token,
        "url": "/partage/" + token,
        "protected": bool(body.password),
        "permissions": sh["permissions"],
        "expires_at": sh["expires_at"],
    }


@router.delete("/meetings/{mid}/shares/{token}")
async def revoke_share(mid: str, token: str, request: Request):
    _, _, actor = await access(request, mid, "manage")
    with s.db() as c:
        row = c.execute(
            "SELECT data FROM shares WHERE id=? AND meeting=?", (token, mid)
        ).fetchone()
        if not row:
            error(404, "Partage indisponible.")
        sh = json.loads(row[0])
        sh["revoked"] = True
        c.execute("UPDATE shares SET data=? WHERE id=?", (json.dumps(sh), token))
        s.audit(c, actor, mid, "share_revoked")
    return {"revoked": True}


@router.get("/share/{token}")
async def open_share(token: str, request: Request):
    # Rebuild the request to avoid Starlette's cached Headers object retaining an
    # owner Authorization path and bypassing an expired share.
    scope = dict(request.scope)
    scope["headers"] = [
        (k, v)
        for k, v in request.scope["headers"]
        if k.lower() not in (b"x-share-token", b"authorization")
    ]
    scope["headers"].append((b"x-share-token", token.encode()))
    guest_request = Request(scope, request.receive)
    with s.db() as c:
        row = c.execute("SELECT meeting FROM shares WHERE id=?", (token,)).fetchone()
        if not row:
            error(404, "Lien indisponible, expiré ou révoqué.")
        mid = row[0]
    return await get_meeting(mid, guest_request)


class Invitation(BaseModel):
    emails: list[EmailStr] = Field(min_length=1, max_length=30)
    summary: str = Field(default="", max_length=2000)
    password: str | None = Field(default=None, max_length=200)


@router.post("/meetings/{mid}/shares/{token}/invite")
async def invite(mid: str, token: str, body: Invitation, request: Request):
    m, _, actor = await access(request, mid, "manage")
    with s.db() as c:
        limit(c, "invite:" + actor, 20)
        c.execute("BEGIN IMMEDIATE")
        row = c.execute(
            "SELECT data FROM shares WHERE id=? AND meeting=?", (token, mid)
        ).fetchone()
        if not row:
            error(404, "Partage indisponible.")
        sh = json.loads(row[0])
        if sh["revoked"] or (
            sh["expires_at"] is not None and sh["expires_at"] <= time.time()
        ):
            error(409, "Lien expiré ou révoqué.")
        if body.summary and not sh["permissions"]["report"]:
            error(422, "Résumé interdit lorsque le rapport n’est pas partagé.")
        if body.password and (
            not sh["password_hash"]
            or not check_password_hash(sh["password_hash"], body.password)
        ):
            error(422, "Le mot de passe transmis ne correspond pas au partage.")
        from api.configs.config import Setting

        url = Setting.FRONTEND_URL.rstrip("/") + "/partage/" + token
        extra = (
            "<p>Mot de passe : " + html.escape(body.password) + "</p>"
            if body.password
            else ""
        )
        for email in sorted(set(str(x).lower() for x in body.emails)):
            key = (
                "invite:"
                + mid
                + ":"
                + hashlib.sha256((token + ":" + email).encode()).hexdigest()
            )
            queue_mail(
                c,
                key,
                m["owner"],
                email,
                "Une réunion Memora vous est partagée",
                f'<h1>{html.escape(m["title"])}</h1><p>{html.escape(body.summary)}</p>{extra}<p><a href="{html.escape(url)}">Accéder à la réunion</a></p><p>Ce lien peut être retransmis. Les contenus déjà copiés ne peuvent pas être rappelés.</p>',
                owner_uid=m["owner_uid"],
            )
        s.audit(c, actor, mid, "invitation_requested")
    return {
        "state": "queued",
        "recipients": len(set(str(x).lower() for x in body.emails)),
    }


@router.get("/notifications")
def notifications(user=AUTH_USER):
    with s.db() as c:
        return [
            {**dict(r), "data": json.loads(r["data"])}
            for r in c.execute(
                "SELECT n.* FROM notifications n JOIN meetings m ON m.id=n.meeting WHERE n.owner=? AND json_extract(m.data,'$.owner_uid')=? ORDER BY n.rowid DESC",
                (user.id, user.account_uid),
            )
        ]


@router.patch("/notifications/{nid}")
def mark_notification(nid: str, user=AUTH_USER):
    with s.db() as c:
        c.execute(
            "UPDATE notifications SET seen=1 WHERE id=? AND owner=? AND meeting IN (SELECT id FROM meetings WHERE json_extract(data,'$.owner_uid')=?)",
            (nid, user.id, user.account_uid),
        )
    return {"seen": True}


@router.get("/mail")
def mail_status(user=AUTH_USER):
    with s.db() as c:
        return [
            dict(r)
            for r in c.execute(
                "SELECT id,recipient,subject,state,error FROM mail WHERE owner=? AND owner_uid=?",
                (user.id, user.account_uid),
            )
        ]


@router.post("/mail/{mail_id}/retry")
def retry_mail(mail_id: str, user=AUTH_USER):
    with s.db() as c:
        c.execute(
            "UPDATE mail SET state='queued',error=NULL WHERE id=? AND owner=? AND owner_uid=? AND state='failed'",
            (mail_id, user.id, user.account_uid),
        )
    return {"state": "queued"}


class Settings(BaseModel):
    max_duration_minutes: int = Field(default=120, ge=1, le=240)
    max_upload_mb: int = Field(default=250, ge=1, le=500)
    audio_retention_days: int = Field(default=30, ge=1, le=365)
    allow_guest_edit: bool = False
    report_language: Literal["fr", "en"] = "fr"
    email_notifications: bool = True


@router.get("/settings")
def settings(user=AUTH_USER):
    with s.db() as c:
        return {**s.config(c), "can_administer": user.is_superuser}


@router.put("/settings")
def update_settings(body: Settings, user=AUTH_USER):
    if not user.is_superuser:
        error(
            403,
            "Administration requise. Ce rôle ne donne pas accès aux réunions des autres utilisateurs.",
        )
    with s.db() as c:
        c.execute(
            "INSERT INTO config_history VALUES(?,?,?,?,?)",
            (
                s.uid(),
                f"user:{user.id}",
                json.dumps(s.config(c)),
                body.model_dump_json(),
                time.time(),
            ),
        )
        c.execute("UPDATE config SET data=? WHERE id=1", (body.model_dump_json(),))
        s.audit(c, f"user:{user.id}", None, "settings_updated:future_meetings_only")
    return body.model_dump()
