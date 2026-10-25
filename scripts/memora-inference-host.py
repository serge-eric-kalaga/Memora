#!/usr/bin/env python3
"""Private native audio bridge; Docker retains the application and PostgreSQL.

No database access, public listener, access log or uploaded audio. Requests refer
only to audio files under the shared domain storage and carry a random secret.
"""

import argparse
import asyncio
import hmac
import json
import math
import os
import re
import shlex
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 5 * 1024 * 1024
_LOCK = threading.Lock()


def load_env(path):
    # Generated environment files are KEY=quoted-value, never executable scripts.
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError("Invalid environment file")
        words = shlex.split(value)
        os.environ[key] = words[0] if len(words) == 1 else value


def create_app(data_root, token):
    from fastapi import FastAPI, HTTPException, Request

    # Local annotations are evaluated by FastAPI against this module's globals.
    globals()["Request"] = Request
    from api.memora import ai, capture_awake, diarization

    if len(token) < 32:
        raise ValueError(
            "A random inference token of at least 32 characters is required"
        )
    data_root = Path(data_root).resolve()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def authorize(request):
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied, "Bearer " + token):
            raise HTTPException(401, "Accès au moteur local refusé.")

    def audio_path(raw):
        if not isinstance(raw, str) or len(raw) > 4096:
            raise HTTPException(422, "Référence audio invalide.")
        path = Path(raw).resolve()
        try:
            relative = path.relative_to(data_root)
        except ValueError:
            raise HTTPException(403, "Référence audio refusée.") from None
        if (
            len(relative.parts) != 2
            or not re.fullmatch(r"[a-f0-9]{32}", relative.parts[0])
            or not re.fullmatch(
                r"audio\.bin|snapshot-[a-f0-9]{32}(?:-speakers)?\.bin", path.name
            )
            or not path.is_file()
        ):
            raise HTTPException(422, "Référence audio invalide.")
        return path

    async def payload(request):
        authorize(request)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                raise HTTPException(413, "Requête trop volumineuse.")
        try:
            value = json.loads(body)
        except (ValueError, UnicodeError):
            raise HTTPException(422, "Requête invalide.") from None
        if not isinstance(value, dict):
            raise HTTPException(422, "Requête invalide.")
        return value

    async def execute(function):
        if not _LOCK.acquire(blocking=False):
            raise HTTPException(429, "Le moteur local est occupé ; réessayez.")

        def run():
            try:
                return function()
            except Exception:  # noqa: BLE001 - model errors must never leak private payloads
                # Never return paths, transcript text, tokens or model internals.
                raise HTTPException(
                    503, "Le traitement audio local a échoué."
                ) from None
            finally:
                _LOCK.release()

        # Shield prevents cancellation releasing the lock while native inference runs.
        return await asyncio.shield(asyncio.to_thread(run))

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "memora-native-inference"}

    @app.get("/diarization/availability")
    def availability(request: Request):
        authorize(request)
        return diarization.availability()

    @app.post("/transcribe")
    async def transcribe(request: Request):
        value = await payload(request)
        path = audio_path(value.get("path"))
        language = value.get("language", "auto")
        tail = value.get("tail_seconds")
        if language not in ("auto", "fr", "en") or (
            tail is not None
            and (
                type(tail) not in (int, float)
                or not math.isfinite(tail)
                or not 0 < tail <= 14400
            )
        ):
            raise HTTPException(422, "Paramètres de transcription invalides.")
        return await execute(
            lambda: ai.transcribe(path, tail_seconds=tail, language=language)
        )

    @app.post("/capture-awake")
    async def capture_awake_lease(request: Request):
        value = await payload(request)
        owner, meeting, active = (
            value.get("owner"),
            value.get("meeting"),
            value.get("active"),
        )
        if (
            not isinstance(owner, str)
            or not re.fullmatch(r"[a-f0-9]{32}", owner)
            or not isinstance(meeting, str)
            or not re.fullmatch(r"[a-f0-9]{32}", meeting)
            or type(active) is not bool
        ):
            raise HTTPException(422, "Paramètres de capture invalides.")
        # Independent short lease: a long ASR must never block renewal/release.
        return await asyncio.to_thread(capture_awake.set_active, owner, meeting, active)

    @app.post("/diarize")
    async def diarize(request: Request):
        value = await payload(request)
        path = audio_path(value.get("path"))
        segments = value.get("segments")
        count, maximum = value.get("num_speakers"), value.get("max_speakers", 8)
        if (
            not isinstance(segments, list)
            or len(segments) > 50000
            or type(maximum) is not int
            or not 1 <= maximum <= 32
            or (
                count is not None
                and (type(count) is not int or not 1 <= count <= maximum)
            )
        ):
            raise HTTPException(422, "Paramètres des intervenants invalides.")
        for segment in segments:
            if not isinstance(segment, dict) or not isinstance(
                segment.get("text"), str
            ):
                raise HTTPException(422, "Passage invalide.")
            for field in ("start", "end"):
                number = segment.get(field)
                if (
                    type(number) not in (int, float)
                    or not math.isfinite(number)
                    or not 0 <= number <= 14400
                ):
                    raise HTTPException(422, "Horodatage invalide.")
            if segment["end"] < segment["start"]:
                raise HTTPException(422, "Horodatage invalide.")
        return await execute(
            lambda: diarization.diarize(
                path, segments, num_speakers=count, max_speakers=maximum
            )
        )

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".memora/backend.env"))
    parser.add_argument("--bridge-env", default=str(ROOT / ".memora/docker/bridge.env"))
    args = parser.parse_args()
    load_env(args.env_file)
    load_env(args.bridge_env)
    os.environ.pop("MEMORA_INFERENCE_URL", None)  # Never recurse into this bridge.
    os.chdir(ROOT / "backend")
    sys.path.insert(0, str(ROOT / "backend"))
    import uvicorn

    app = create_app(
        os.environ.get("MEMORA_DATA_DIR", "../.memora/data"),
        os.environ.get("MEMORA_INFERENCE_TOKEN", ""),
    )
    bind = os.environ.get("MEMORA_INFERENCE_BIND", "127.0.0.1")
    if bind != "127.0.0.1":
        raise ValueError("Inference bridge must remain bound to 127.0.0.1")
    port = int(os.environ.get("MEMORA_INFERENCE_PORT", "8091"))
    if not 1024 <= port <= 65535:
        raise ValueError("Invalid local inference port")
    uvicorn.run(app, host=bind, port=port, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
