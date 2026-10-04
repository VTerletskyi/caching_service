import asyncio

from uuid import uuid4

import pytest

from sqlalchemy import func, select

from caching_svc.database import session_factory
from caching_svc.shared.application.services import PayloadService
from caching_svc.shared.domain.exceptions import PayloadNotFoundError, TransformerError
from caching_svc.shared.models import PayloadModel, TransformationModel


pytestmark = pytest.mark.integration


async def test_create_persists_payload_with_interleaved_output(payload_service):
    result = await payload_service.create(["first string", "second string"], ["other", "another"])

    payload = await payload_service.get(result.payload_id)
    assert result.created is True
    assert payload.output == "FIRST STRING, OTHER, SECOND STRING, ANOTHER"


async def test_create_transforms_each_distinct_string_once(payload_service, transformer):
    await payload_service.create(["a", "b", "a"], ["b", "c", "a"])

    assert transformer.calls == {"a": 1, "b": 1, "c": 1}


async def test_create_reuses_id_and_skips_transformer_for_known_payload(
    payload_service, transformer
):
    first = await payload_service.create(["a"], ["b"])
    second = await payload_service.create(["a"], ["b"])

    assert (first.created, second.created) == (True, False)
    assert second.payload_id == first.payload_id
    assert transformer.total_calls == 2


async def test_create_transforms_only_strings_missing_from_cache(payload_service, transformer):
    await payload_service.create(["a", "b"], ["c", "d"])
    transformer.calls.clear()

    result = await payload_service.create(["d", "c"], ["b", "new"])

    assert result.created is True
    assert transformer.calls == {"new": 1}


async def test_get_raises_when_payload_does_not_exist(payload_service):
    with pytest.raises(PayloadNotFoundError):
        await payload_service.get(uuid4())


async def test_concurrent_identical_requests_share_one_payload_id(payload_service):
    results = await asyncio.gather(*(payload_service.create(["same"], ["input"]) for _ in range(5)))

    assert len({result.payload_id for result in results}) == 1
    assert sum(result.created for result in results) == 1


class FailingTransformer:
    async def transform(self, value: str) -> str:
        raise RuntimeError("external service failed")


async def test_failed_transformer_call_persists_nothing(transformer):
    await PayloadService(session_factory, transformer, max_concurrency=10).create(["a"], ["b"])
    service = PayloadService(session_factory, FailingTransformer(), max_concurrency=10)

    with pytest.raises(TransformerError):
        await service.create(["a", "new"], ["b", "other"])

    async with session_factory() as db:
        cached_rows = await db.scalar(select(func.count()).select_from(TransformationModel))
        payload_rows = await db.scalar(select(func.count()).select_from(PayloadModel))
    assert (cached_rows, payload_rows) == (2, 1)
