from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid6 import uuid7


def utc_now() -> datetime:
    return datetime.now(UTC)


class BaseModel(DeclarativeBase):
    """Declarative base; UUID v7 ids keep inserts index-friendly (time-ordered)."""

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
