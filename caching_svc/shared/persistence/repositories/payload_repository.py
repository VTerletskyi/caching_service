from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from caching_svc.shared.models import PayloadModel


@dataclass
class PayloadRepository:
    """Persistence of generated payloads."""

    db: AsyncSession

    async def get(self, payload_id: UUID) -> PayloadModel | None:
        return await self.db.get(PayloadModel, payload_id)

    async def get_id_by_hash(self, payload_hash: str) -> UUID | None:
        stmt = select(PayloadModel.id).where(PayloadModel.payload_hash == payload_hash)
        return await self.db.scalar(stmt)

    async def create(self, payload_hash: str, output: str) -> tuple[UUID, bool]:
        """Insert a payload unless one with the same hash exists.

        Returns ``(payload_id, created)``. When a concurrent request inserted the same payload
        first, its id is returned with ``created=False``, so both callers share one identifier.
        """
        stmt = (
            pg_insert(PayloadModel)
            .values(payload_hash=payload_hash, output=output)
            .on_conflict_do_nothing(index_elements=[PayloadModel.payload_hash])
            .returning(PayloadModel.id)
        )
        payload_id = await self.db.scalar(stmt)
        if payload_id is not None:
            return payload_id, True

        existing_id = await self.get_id_by_hash(payload_hash)
        if existing_id is None:
            raise RuntimeError("Payload insert conflicted but no payload with this hash exists")
        return existing_id, False
