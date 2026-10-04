import pytest

from pydantic import ValidationError

from caching_svc.config import TransformerConfig


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "values",
    [{"max_concurrency": 0}, {"delay_seconds": -1}],
    ids=["no-concurrency", "negative-delay"],
)
def test_transformer_config_rejects_values_that_would_hang_or_break_requests(values):
    with pytest.raises(ValidationError):
        TransformerConfig(**values)
