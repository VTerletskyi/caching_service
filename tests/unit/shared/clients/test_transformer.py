import asyncio

import pytest

from caching_svc.shared.clients.transformer import UppercaseTransformer, transform_many
from caching_svc.shared.domain.exceptions import TransformerError


pytestmark = pytest.mark.unit


async def test_uppercase_transformer_uppercases_value():
    transformer = UppercaseTransformer()

    assert await transformer.transform("first string") == "FIRST STRING"


async def test_transform_many_calls_transformer_once_per_value(transformer):
    result = await transform_many(transformer, ["a", "b", "c"], max_concurrency=2)

    assert result == {"a": "A", "b": "B", "c": "C"}
    assert transformer.calls == {"a": 1, "b": 1, "c": 1}


async def test_transform_many_without_values_does_not_call_transformer(transformer):
    assert await transform_many(transformer, [], max_concurrency=2) == {}
    assert transformer.total_calls == 0


class ConcurrencyProbeTransformer:
    def __init__(self):
        self.in_flight = 0
        self.max_in_flight = 0

    async def transform(self, value: str) -> str:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0.01)
        self.in_flight -= 1
        return value.upper()


async def test_transform_many_bounds_calls_in_flight():
    probe = ConcurrencyProbeTransformer()

    await transform_many(probe, [f"value-{i}" for i in range(10)], max_concurrency=3)

    assert probe.max_in_flight == 3


class FailingTransformer:
    """Fails on "bad" while the other calls are still in flight."""

    def __init__(self):
        self.finished: list[str] = []

    async def transform(self, value: str) -> str:
        if value == "bad":
            raise RuntimeError("external service failed")
        await asyncio.sleep(0.2)
        self.finished.append(value)
        return value.upper()


async def test_transform_many_cancels_remaining_calls_when_one_fails():
    failing = FailingTransformer()

    with pytest.raises(TransformerError):
        await transform_many(failing, ["slow-1", "bad", "slow-2"], max_concurrency=10)
    await asyncio.sleep(0.3)

    assert failing.finished == []


async def test_transform_many_logs_the_underlying_failure(caplog):
    with pytest.raises(TransformerError):
        await transform_many(FailingTransformer(), ["bad"], max_concurrency=1)

    [record] = caplog.records
    assert record.levelname == "ERROR"
    assert "external service failed" in caplog.text
