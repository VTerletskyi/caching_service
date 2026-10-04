from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from caching_svc.shared.models.base import BaseModel


class PayloadModel(BaseModel):
    """Generated payload; ``payload_hash`` identifies the request that produced it."""

    __tablename__ = "payloads"

    payload_hash: Mapped[str] = mapped_column(String(64), unique=True)
    output: Mapped[str] = mapped_column(Text)
