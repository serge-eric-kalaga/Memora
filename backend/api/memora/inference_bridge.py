"""Authenticated private host inference transport for Docker on Apple Silicon."""

import os
from pathlib import Path

import httpx


class BridgeError(ValueError):
    """Safe failure: never exposes audio, request payloads, tokens or host paths."""


def configured():
    return bool(os.environ.get("MEMORA_INFERENCE_URL"))


def request(endpoint, payload=None):
    url = os.environ.get("MEMORA_INFERENCE_URL", "").rstrip("/")
    token = os.environ.get("MEMORA_INFERENCE_TOKEN", "")
    parsed = httpx.URL(url)
    if (
        parsed.scheme != "http"
        or parsed.host not in {"127.0.0.1", "localhost", "host.docker.internal"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.path not in ("", "/")
        or len(token) < 32
    ):
        raise BridgeError("La connexion au moteur local est mal configurée.")
    try:
        with httpx.Client(
            timeout=httpx.Timeout(
                5
                if endpoint in ("/capture-awake", "/diarization/availability")
                else 1800,
                connect=5,
            ),
            trust_env=False,
        ) as client:
            with client.stream(
                "GET" if payload is None else "POST",
                url + endpoint,
                headers={"Authorization": "Bearer " + token},
                json=payload,
            ) as response:
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 32 * 1024 * 1024:
                        raise BridgeError(
                            "La réponse du moteur local dépasse la limite."
                        )
                import json

                return json.loads(body)
    except (httpx.HTTPError, ValueError) as exc:
        if isinstance(exc, BridgeError):
            raise
        raise BridgeError(
            "Le moteur audio local est indisponible. Vérifiez son état puis relancez le traitement."
        ) from None


def transcribe(path: Path, tail_seconds=None, language="auto"):
    result = request(
        "/transcribe",
        {
            "path": str(path.resolve()),
            "tail_seconds": tail_seconds,
            "language": language,
        },
    )
    if not isinstance(result, list):
        raise BridgeError("Le moteur local a renvoyé un résultat invalide.")
    return result


def diarize(path, segments, *, num_speakers=None, max_speakers=8):
    result = request(
        "/diarize",
        {
            "path": str(Path(path).resolve()),
            "segments": segments,
            "num_speakers": num_speakers,
            "max_speakers": max_speakers,
        },
    )
    if not isinstance(result, dict) or not isinstance(result.get("segments"), list):
        raise BridgeError("Le moteur local a renvoyé un résultat invalide.")
    return result


def availability():
    try:
        result = request("/diarization/availability")
        if isinstance(result, dict) and isinstance(result.get("available"), bool):
            return result
    except BridgeError:
        pass
    return {"available": False, "reason": "Le moteur audio local est indisponible."}


def capture_awake(owner, meeting, active):
    try:
        result = request(
            "/capture-awake", {"owner": owner, "meeting": meeting, "active": active}
        )
        if (
            isinstance(result, dict)
            and type(result.get("supported")) is bool
            and type(result.get("active")) is bool
        ):
            return result
    except BridgeError:
        pass
    return {"supported": False, "active": False}
