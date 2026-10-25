"""Recettes locales et S3 simulé, sans accès aux données ni services externes."""

from io import BytesIO
from types import SimpleNamespace
import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import Stubber
from fastapi import FastAPI, HTTPException, Query
from fastapi.testclient import TestClient
from typing import Annotated
from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from api.services.storage import LocalStorage, S3Storage
from .test_profile_and_cache import account_client  # noqa: F401
from api.services.pagination import ListParams, paginate


def test_local_storage_roundtrip_and_traversal(tmp_path):
    """Conserver le contrat local et refuser un accès en dehors de la racine."""
    storage = LocalStorage(tmp_path)
    storage.put("photo.webp", b"image", "image/webp")
    assert storage.read("photo.webp") == b"image"
    storage.delete("photo.webp")
    storage.delete("photo.webp")
    with pytest.raises(FileNotFoundError):
        storage.read("photo.webp")
    with pytest.raises(ValueError):
        storage.read("../private")


def test_s3_contract_and_missing_object():
    """Vérifier les requêtes S3 signées sans réseau ni ACL publique."""
    config = SimpleNamespace(
        S3_BUCKET="test-bucket",
        S3_ENDPOINT_URL="https://s3.example.com",
        S3_REGION="us-east-1",
        S3_ACCESS_KEY_ID="test-key",
        S3_SECRET_ACCESS_KEY="test-secret",
        S3_ADDRESSING_STYLE="path",
    )
    storage = S3Storage(config)
    args = {"Bucket": "test-bucket", "Key": "photo.webp"}
    with Stubber(storage.client) as stub:
        stub.add_response(
            "put_object", {}, {**args, "Body": b"image", "ContentType": "image/webp"}
        )
        stream = BytesIO(b"image")
        stub.add_response("get_object", {"Body": StreamingBody(stream, 5)}, args)
        stub.add_response("delete_object", {}, args)
        stub.add_client_error("get_object", "NoSuchKey", expected_params=args)
        stub.add_client_error("get_object", "AccessDenied", expected_params=args)
        storage.put("photo.webp", b"image", "image/webp")
        assert storage.read("photo.webp") == b"image"
        assert stream.closed
        storage.delete("photo.webp")
        with pytest.raises(FileNotFoundError):
            storage.read("photo.webp")
        with pytest.raises(ClientError):
            storage.read("photo.webp")
        stub.assert_no_pending_responses()


def test_pagination_search_sort_and_bounds():
    """Recherche littérale, tri stable, total filtré et pages hors plage."""

    class Base(DeclarativeBase):
        pass

    class Item(Base):
        __tablename__ = "items"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(String(50))

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [Item(name="same"), Item(name="same"), Item(name="100%"), Item(name="100x")]
        )
        db.commit()

        def page(**kwargs):
            return paginate(
                db.query(Item),
                ListParams(**kwargs),
                sort_columns={"id": Item.id, "name": Item.name},
                search_columns=(Item.name,),
                tie_breaker=Item.id,
            )

        first = page(q="SAME", sort="name", page_size=1)
        second = page(q="SAME", sort="name", page_size=1, page=2)
        assert first["total"] == 2 and first["pages"] == 2
        assert first["items"][0].id < second["items"][0].id
        assert page(q="% ")["total"] == 1
        assert page(page=99)["items"] == []
        assert page(q="absent")["pages"] == 0
        assert page(order="desc")["items"][0].id == 4
        with pytest.raises(HTTPException):
            page(sort="password")
    engine.dispose()


def test_list_query_validation_and_documentation():
    """FastAPI expose les paramètres et refuse les valeurs dépassant les limites."""
    app = FastAPI()

    @app.get("/")
    def endpoint(params: Annotated[ListParams, Query()]):
        return params

    client = TestClient(app)
    for query in ("page=0", "page_size=101", "order=invalid", "q=" + "x" * 101):
        assert client.get("/?" + query).status_code == 422
    params = app.openapi()["paths"]["/"]["get"]["parameters"]
    assert {p["name"] for p in params} == {"page", "page_size", "q", "sort", "order"}


def test_user_page_route(request):
    """Le contrat paginé est utilisable avec l’authentification existante."""
    client, name, headers, _, _, _ = request.getfixturevalue("account_client")
    response = client.get(
        "/api/user/page", params={"q": name, "sort": "username"}, headers=headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["username"] == name
    assert (
        client.get(
            "/api/user/page", params={"sort": "password"}, headers=headers
        ).status_code
        == 422
    )
    assert client.get("/api/user/page").status_code == 401
