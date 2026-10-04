import logging

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caching_svc.shared.clients.transformer import Transformer, transform_many
from caching_svc.shared.domain.exceptions import PayloadNotFoundError
from caching_svc.shared.domain.services import (
    build_output,
    build_payload_hash,
    distinct_values,
    missing_values,
)
from caching_svc.shared.models import PayloadModel
from caching_svc.shared.persistence.repositories import (
    PayloadRepository,
    TransformationRepository,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PayloadCreateResult:
    payload_id: UUID
    created: bool


@dataclass
class PayloadService:
    """Generates payloads while calling the external transformer as rarely as possible.

    Unlike a typical service it owns its transactions instead of using a request-scoped session:
    payload creation is split into a short read and a short write transaction, so no database
    connection is held (idle in transaction) while waiting on the slow external transformer.
    Otherwise a handful of concurrent requests with new strings would exhaust the pool.
    """

    session_factory: async_sessionmaker[AsyncSession]
    transformer: Transformer
    max_concurrency: int

    async def create(self, list_1: list[str], list_2: list[str]) -> PayloadCreateResult:
        payload_hash = build_payload_hash(list_1, list_2)
        values = distinct_values(list_1, list_2)

        async with self.session_factory() as db:
            # A payload is a pure function of its input, so a known input is answered without
            # touching the transformer or the cache at all.
            existing_id = await PayloadRepository(db).get_id_by_hash(payload_hash)
            if existing_id is not None:
                return PayloadCreateResult(payload_id=existing_id, created=False)
            cached = await TransformationRepository(db).get_outputs(values)

        missing = missing_values(values, cached)
        logger.info("Transformer cache: %d hit(s), %d miss(es)", len(cached), len(missing))
        fresh = await transform_many(self.transformer, missing, self.max_concurrency)
        output = build_output(list_1, list_2, cached | fresh)

        async with self.session_factory.begin() as db:
            await TransformationRepository(db).save_outputs(fresh)
            payload_id, created = await PayloadRepository(db).create(payload_hash, output)
        return PayloadCreateResult(payload_id=payload_id, created=created)

    async def get(self, payload_id: UUID) -> PayloadModel:
        async with self.session_factory() as db:
            payload = await PayloadRepository(db).get(payload_id)
        if payload is None:
            raise PayloadNotFoundError(payload_id)
        return payload
