from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from caching_svc.shared.domain.services import hash_text
from caching_svc.shared.models import TransformationModel


@dataclass
class TransformationRepository:
    """Persistence of cached transformer outcomes."""

    db: AsyncSession

    async def get_outputs(self, values: Iterable[str]) -> dict[str, str]:
        """Return cached outputs keyed by input, for the subset of ``values`` already cached."""
        values_by_hash = {hash_text(value): value for value in values}
        if not values_by_hash:
            return {}

        stmt = select(TransformationModel.input_hash, TransformationModel.output).where(
            TransformationModel.input_hash.in_(values_by_hash)
        )
        result = await self.db.execute(stmt)
        return {values_by_hash[input_hash]: output for input_hash, output in result.all()}

    async def save_outputs(self, outputs: dict[str, str]) -> None:
        """Insert new outputs; rows cached concurrently by another request are left as is."""
        if not outputs:
            return

        rows = [
            {"input_hash": hash_text(value), "input": value, "output": output}
            for value, output in outputs.items()
        ]
        # A consistent key order makes concurrent inserts of overlapping sets wait on each other
        # instead of deadlocking on the unique index (A holds x and waits for y, B the reverse).
        rows.sort(key=lambda row: row["input_hash"])
        stmt = (
            pg_insert(TransformationModel)
            .values(rows)
            .on_conflict_do_nothing(index_elements=[TransformationModel.input_hash])
        )
        await self.db.execute(stmt)
