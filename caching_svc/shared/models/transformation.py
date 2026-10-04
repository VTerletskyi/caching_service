from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from caching_svc.shared.models.base import BaseModel


class TransformationModel(BaseModel):
    """Cached outcome of the external transformer for a single input string."""

    __tablename__ = "transformations"

    input_hash: Mapped[str] = mapped_column(String(64), unique=True)
    input: Mapped[str] = mapped_column(Text)
    output: Mapped[str] = mapped_column(Text)
