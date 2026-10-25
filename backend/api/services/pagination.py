"""Contrat de listes partagé : pagination bornée, recherche littérale et tri autorisé."""

from typing import Generic, Literal, TypeVar
from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_

T = TypeVar("T")


class ListParams(BaseModel):
    """Paramètres query à réutiliser avec Annotated[ListParams, Query()]."""

    page: int = Field(
        default=1, ge=1, le=1_000_000, description="Page demandée, à partir de 1"
    )
    page_size: int = Field(
        default=20, ge=1, le=100, description="Éléments par page, maximum 100"
    )
    q: str = Field(
        default="", max_length=100, description="Recherche textuelle littérale"
    )
    sort: str = Field(
        default="id", max_length=50, description="Nom d’un champ de tri autorisé"
    )
    order: Literal["asc", "desc"] = Field(default="asc", description="Sens du tri")


class Page(BaseModel, Generic[T]):
    """Résultat paginé, placé dans data de l’enveloppe API habituelle."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


def paginate(
    query,
    params: ListParams,
    *,
    sort_columns: dict,
    search_columns: tuple = (),
    tie_breaker,
):
    """Appliquer les filtres après restriction métier du query, jamais du SQL client.

    Fournir un query portant sur une seule entité et un départage unique pour
    obtenir des pages stables quand plusieurs lignes ont le même champ de tri.
    """
    if params.sort not in sort_columns:
        raise HTTPException(422, "Champ de tri non autorisé")
    text = params.q.strip()
    if text and search_columns:
        query = query.filter(
            or_(*(column.icontains(text, autoescape=True) for column in search_columns))
        )
    total = query.order_by(None).count()
    column = sort_columns[params.sort]
    primary = column.desc() if params.order == "desc" else column.asc()
    items = (
        query.order_by(None)
        .order_by(primary, tie_breaker.asc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
        .all()
    )
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "pages": (total + params.page_size - 1) // params.page_size,
    }
