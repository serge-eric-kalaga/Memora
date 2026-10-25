from pydantic import BaseModel
from typing import Generic, TypeVar

TypeX = TypeVar("TypeX")


class Response(BaseModel, Generic[TypeX]):
    status: int = 1
    status_code: int = 200
    message: str | None = "ok"
    data: TypeX | None = None
