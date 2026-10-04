from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# Bounds a single request so the batched cache lookup/insert stays within Postgres' bind
# parameter limit and one request cannot monopolize the external transformer.
MAX_LIST_LENGTH = 1000


class PayloadCreateSchema(BaseModel):
    list_1: list[str] = Field(min_length=1, max_length=MAX_LIST_LENGTH)
    list_2: list[str] = Field(min_length=1, max_length=MAX_LIST_LENGTH)

    @model_validator(mode="after")
    def check_same_length(self) -> Self:
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        return self


class PayloadCreatedSchema(BaseModel):
    id: UUID
    message: str


class PayloadSchema(BaseModel):
    output: str
