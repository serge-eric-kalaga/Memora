"""Photos de profil et cache : vérifier les frontières HTTP, SQL, fichiers et Redis."""

from io import BytesIO
from uuid import uuid4
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from api import createApp, SETTINGS
from api.database import User, engine
from api.services.jwt import create_token


def picture(fmt="PNG", size=(8, 8)):
    output = BytesIO()
    Image.new("RGB", size, "green").save(output, format=fmt)
    return output.getvalue()


@pytest.fixture
def account_client(tmp_path):
    config = SETTINGS()
    config.CACHE_ENABLED = bool(os.environ.get("TEST_REDIS_URL"))
    config.REDIS_URL = os.environ.get("TEST_REDIS_URL")
    config.REDIS_DATABASE_URL = None
    config.REDIS_PREFIX = f"template-tests:{uuid4().hex}"
    config.PROFILE_PHOTO_DIR = tmp_path / "photos"
    config.PROFILE_PHOTO_MAX_BYTES = 4096
    app = createApp(config)
    with Session(engine) as db:
        name = f"photo_{uuid4().hex}"
        other = f"other_{uuid4().hex}"
        for username in [name, other]:
            User(
                username=username,
                telephone=None,
                password=generate_password_hash("TestPassword!2026"),
            ).saveWithCommit(db)
    headers = {"Authorization": f"Bearer {create_token({'username': name})}"}
    other_headers = {"Authorization": f"Bearer {create_token({'username': other})}"}
    with TestClient(app) as client:
        yield client, name, headers, other, other_headers, config
    if config.CACHE_ENABLED:
        from redis import Redis

        redis = Redis.from_url(config.REDIS_URL)
        keys = list(redis.scan_iter(match=f"{config.REDIS_PREFIX}:*"))
        if keys:
            redis.delete(*keys)
        redis.close()


def test_add_replace_and_read_photo(account_client):
    c, name, headers, other, _, config = account_client
    assert c.get(f"/api/user/{name}/photo", headers=headers).status_code == 404
    assert (
        c.put(
            "/api/user/me/photo", files={"photo": ("p.png", picture(), "image/png")}
        ).status_code
        == 401
    )
    response = c.put(
        "/api/user/me/photo",
        headers=headers,
        files={"photo": ("../../p.png", picture(), "image/png")},
    )
    assert response.status_code == 200, response.text
    url = response.json()["data"]["profile_photo_url"]
    assert url.startswith(f"/api/user/{name}/photo?v=")
    first = list(config.PROFILE_PHOTO_DIR.iterdir())
    assert len(first) == 1 and first[0].suffix == ".webp"
    photo = c.get(url, headers=headers)
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/webp"
    with Image.open(BytesIO(photo.content)) as image:
        assert image.format == "WEBP" and image.size == (8, 8)
    assert c.get(url).status_code == 401
    assert (
        c.get(f"/api/user/{other}", headers=headers).json()["data"]["profile_photo_url"]
        is None
    )
    response = c.put(
        "/api/user/me/photo",
        headers=headers,
        files={"photo": ("p.jpg", picture("JPEG"), "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["data"]["profile_photo_url"] != url
    assert not first[0].exists() and len(list(config.PROFILE_PHOTO_DIR.iterdir())) == 1


@pytest.mark.parametrize(
    "data,mime,expected",
    [
        (b"not an image", "image/png", 400),
        (b"<svg></svg>", "image/svg+xml", 415),
        (picture("PNG"), "image/jpeg", 415),
        (b"x" * 4097, "image/png", 413),
    ],
)
def test_rejected_photo_does_not_change_profile(account_client, data, mime, expected):
    c, name, headers, _, _, config = account_client
    response = c.put(
        "/api/user/me/photo", headers=headers, files={"photo": ("photo", data, mime)}
    )
    assert response.status_code == expected, response.text
    assert (
        c.get(f"/api/user/{name}", headers=headers).json()["data"]["profile_photo_url"]
        is None
    )
    assert not config.PROFILE_PHOTO_DIR.exists()


def test_photo_dimensions_and_animation(account_client):
    c, _, headers, _, _, config = account_client
    config.PROFILE_PHOTO_MAX_PIXELS = 10
    r = c.put(
        "/api/user/me/photo",
        headers=headers,
        files={"photo": ("p.png", picture(), "image/png")},
    )
    assert r.status_code == 413
    config.PROFILE_PHOTO_MAX_PIXELS = 1000
    output = BytesIO()
    Image.new("RGB", (8, 8), "red").save(
        output,
        format="WEBP",
        save_all=True,
        append_images=[Image.new("RGB", (8, 8), "blue")],
        duration=100,
    )
    assert (
        c.put(
            "/api/user/me/photo",
            headers=headers,
            files={"photo": ("p.webp", output.getvalue(), "image/webp")},
        ).status_code
        == 415
    )


def test_photo_rollback_keeps_previous_file(account_client, monkeypatch):
    from api.services.profile_photo import update_profile_photo
    from starlette.datastructures import UploadFile, Headers

    c, name, headers, _, _, config = account_client
    assert (
        c.put(
            "/api/user/me/photo",
            headers=headers,
            files={"photo": ("p.png", picture(), "image/png")},
        ).status_code
        == 200
    )
    previous = list(config.PROFILE_PHOTO_DIR.iterdir())
    with Session(engine) as db:

        def fail():
            raise RuntimeError("Simulated SQL commit failure")

        monkeypatch.setattr(db, "commit", fail)
        with pytest.raises(RuntimeError):
            update_profile_photo(
                db,
                name,
                UploadFile(
                    BytesIO(picture()), headers=Headers({"content-type": "image/png"})
                ),
                config,
            )
    assert list(config.PROFILE_PHOTO_DIR.iterdir()) == previous
    assert c.get(f"/api/user/{name}/photo", headers=headers).status_code == 200


def test_cache_hit_auth_isolation_and_invalidation(account_client):
    if not os.environ.get("TEST_REDIS_URL"):
        pytest.skip(
            "Définir TEST_REDIS_URL vers un Redis jetable pour ce test d’intégration"
        )
    c, name, headers, _, other_headers, _ = account_client
    url = f"/api/user/{name}"
    assert c.get(url, headers=headers).headers["X-Redis-Cache"] == "MISS"
    hit = c.get(url, headers=headers)
    assert hit.headers["X-Redis-Cache"] == "HIT"
    assert hit.headers["Cache-Control"] == "no-store"
    assert "password" not in hit.json()["data"]
    assert c.get(url).status_code == 401
    assert c.get(url, headers={"Authorization": "Bearer invalid"}).status_code == 403
    assert c.get(url, headers=other_headers).headers["X-Redis-Cache"] == "MISS"
    assert c.get("/api/user/", headers=headers).headers["X-Redis-Cache"] == "MISS"
    assert c.get("/api/user/", headers=headers).headers["X-Redis-Cache"] == "HIT"
    assert (
        c.put(url, headers=headers, json={"telephone": "+22670000000"}).status_code
        == 200
    )
    changed = c.get(url, headers=headers)
    assert changed.headers["X-Redis-Cache"] == "MISS"
    assert changed.json()["data"]["telephone"] == "+22670000000"
    assert c.get("/api/user/", headers=headers).headers["X-Redis-Cache"] == "MISS"
    assert (
        c.put(
            "/api/user/me/photo",
            headers=headers,
            files={"photo": ("p.png", picture(), "image/png")},
        ).status_code
        == 200
    )
    photo = c.get(url, headers=headers)
    assert (
        photo.headers["X-Redis-Cache"] == "MISS"
        and photo.json()["data"]["profile_photo_url"]
    )
    assert c.delete(url, headers=headers).status_code == 200
    assert not list(account_client[-1].PROFILE_PHOTO_DIR.iterdir())
    assert (
        c.get(url, headers=headers).status_code == 403
    )  # Le compte supprimé n’a plus de session valide.
    assert c.get(url, headers=other_headers).status_code == 404
    assert (
        c.get(url, headers=other_headers).status_code == 404
    )  # Ne pas cacher une erreur.


def test_reusable_public_cache_ttl_and_query_keys(account_client):
    if not os.environ.get("TEST_REDIS_URL"):
        pytest.skip("TEST_REDIS_URL requis")
    import time
    from fastapi import Depends
    from api.services.cache import cached_response, invalidate_cache

    c, _, _, _, _, _ = account_client
    calls = []

    @c.app.get(
        "/cache-probe",
        dependencies=[Depends(cached_response("probe", ttl=1, authenticated=False))],
    )
    def read_probe():
        calls.append(1)
        return {"calls": len(calls)}

    @c.app.post("/cache-probe", dependencies=[Depends(invalidate_cache("probe"))])
    def write_probe():
        return {"ok": True}

    assert c.get("/cache-probe?a=1&b=2").headers["X-Redis-Cache"] == "MISS"
    assert c.get("/cache-probe?b=2&a=1").headers["X-Redis-Cache"] == "HIT"
    assert len(calls) == 1
    assert c.get("/cache-probe?a=2").headers["X-Redis-Cache"] == "MISS"
    time.sleep(1.1)
    assert c.get("/cache-probe?a=1&b=2").headers["X-Redis-Cache"] == "MISS"
    assert c.post("/cache-probe").status_code == 200
    assert c.get("/cache-probe?a=1&b=2").headers["X-Redis-Cache"] == "MISS"


def test_failed_write_keeps_cache_and_registration_invalidates(account_client):
    if not os.environ.get("TEST_REDIS_URL"):
        pytest.skip("TEST_REDIS_URL requis")
    c, name, headers, _, _, _ = account_client
    assert c.get("/api/user/", headers=headers).headers["X-Redis-Cache"] == "MISS"
    body = {"username": name, "password": "TestPassword!2026"}
    assert c.post("/api/auth/register", json=body).status_code == 400
    assert c.get("/api/user/", headers=headers).headers["X-Redis-Cache"] == "HIT"
    body["username"] = f"new_{uuid4().hex}"
    assert c.post("/api/auth/register", json=body).status_code == 200
    assert c.get("/api/user/", headers=headers).headers["X-Redis-Cache"] == "MISS"
    old = body["username"]
    renamed = f"renamed_{uuid4().hex}"
    assert c.get(f"/api/user/{old}", headers=headers).status_code == 200
    login = c.post(
        "/api/auth/login", json={"username": old, "password": body["password"]}
    )
    owner_headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    assert (
        c.put(
            f"/api/user/{old}", headers=owner_headers, json={"username": renamed}
        ).status_code
        == 200
    )
    assert c.get(f"/api/user/{old}", headers=headers).status_code == 404
    assert (
        c.get(f"/api/user/{renamed}", headers=headers).headers["X-Redis-Cache"]
        == "MISS"
    )


def test_redis_outage_does_not_break_reads_or_writes(tmp_path):
    config = SETTINGS()
    config.CACHE_ENABLED = True
    config.REDIS_URL = "redis://127.0.0.1:1/0"
    config.REDIS_PREFIX = f"outage:{uuid4().hex}"
    config.PROFILE_PHOTO_DIR = tmp_path
    name = f"outage_{uuid4().hex}"
    app = createApp(config)
    with Session(engine) as db:
        User(username=name, telephone=None, password="unused").saveWithCommit(db)
    headers = {"Authorization": f"Bearer {create_token({'username': name})}"}
    with TestClient(app) as c:
        assert c.get(f"/api/user/{name}", headers=headers).status_code == 200
        assert (
            c.put(
                f"/api/user/{name}", headers=headers, json={"telephone": "123"}
            ).status_code
            == 200
        )


def test_photo_is_resized_and_metadata_removed(account_client):
    from PIL.PngImagePlugin import PngInfo

    c, name, headers, _, _, config = account_client
    config.PROFILE_PHOTO_MAX_BYTES = 5 * 1024 * 1024
    metadata = PngInfo()
    metadata.add_text("Comment", "Private metadata to remove")
    source = BytesIO()
    Image.new("RGB", (2048, 1024), "green").save(source, format="PNG", pnginfo=metadata)
    uploaded = c.put(
        "/api/user/me/photo",
        headers=headers,
        files={"photo": ("large.png", source.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 200
    result = c.get(uploaded.json()["data"]["profile_photo_url"], headers=headers)
    with Image.open(BytesIO(result.content)) as image:
        assert image.size == (1024, 512)
        assert not image.getexif() and "Comment" not in image.info
