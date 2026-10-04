from collections import Counter
from dataclasses import dataclass, field

import pytest


@dataclass
class CountingTransformer:
    """Transformer double that records every call, so tests can assert cache effectiveness."""

    calls: Counter[str] = field(default_factory=Counter)

    async def transform(self, value: str) -> str:
        self.calls[value] += 1
        return value.upper()

    @property
    def total_calls(self) -> int:
        return self.calls.total()


@pytest.fixture
def transformer() -> CountingTransformer:
    return CountingTransformer()
