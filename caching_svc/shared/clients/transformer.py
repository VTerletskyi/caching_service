import asyncio
import logging

from dataclasses import dataclass
from typing import Protocol

from caching_svc.shared.domain.exceptions import TransformerError


logger = logging.getLogger(__name__)


class Transformer(Protocol):
    """Contract of the external "transformer" service."""

    async def transform(self, value: str) -> str: ...


@dataclass
class UppercaseTransformer:
    """Simulates the external transformer service.

    The artificial delay stands in for network latency / per-call cost of the real service; it is
    what makes caching worthwhile and makes cache hits observable from the outside.
    """

    delay_seconds: float = 0.0

    async def transform(self, value: str) -> str:
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        return value.upper()


async def transform_many(
    transformer: Transformer, values: list[str], max_concurrency: int
) -> dict[str, str]:
    """Transform every value once, with at most ``max_concurrency`` calls in flight.

    The bound keeps one payload with many new strings from flooding the external service.
    A ``TaskGroup`` cancels the remaining calls as soon as one fails, so a request that is
    already lost does not keep hitting the service; the failure surfaces as ``TransformerError``.
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def transform(value: str) -> str:
        async with semaphore:
            return await transformer.transform(value)

    try:
        async with asyncio.TaskGroup() as group:
            tasks = {value: group.create_task(transform(value)) for value in values}
    except ExceptionGroup as exc:
        # Logged here because the API turns TransformerError into a 502, which FastAPI does not
        # log; without this the actual cause would be lost.
        logger.error("Transformer failed for %d value(s)", len(values), exc_info=exc)
        raise TransformerError("Transformer service failed") from exc
    return {value: task.result() for value, task in tasks.items()}
