from dataclasses import dataclass, field
from uuid import uuid4

import pytest

from sqlalchemy import text

from caching_svc.apps.website.app import app
from caching_svc.apps.website.deps import get_transformer
from caching_svc.database import engine


pytestmark = pytest.mark.integration

SPEC_INPUT = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}
SPEC_OUTPUT = "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"


async def test_create_and_read_payload_from_spec_example(website_client):
    create_response = await website_client.post("/payload", json=SPEC_INPUT)
    payload_id = create_response.json()["id"]
    read_response = await website_client.get(f"/payload/{payload_id}")

    assert create_response.status_code == 201
    assert create_response.json()["message"] == "Payload created"
    assert read_response.status_code == 200
    assert read_response.json() == {"output": SPEC_OUTPUT}


async def test_repeated_request_reuses_id_without_calling_transformer(website_client, transformer):
    first = await website_client.post("/payload", json=SPEC_INPUT)
    calls_after_first = transformer.total_calls

    second = await website_client.post("/payload", json=SPEC_INPUT)

    assert calls_after_first == 6
    assert second.status_code == 200
    assert second.json() == {"id": first.json()["id"], "message": "Payload already exists"}
    assert transformer.total_calls == calls_after_first


async def test_new_payload_reuses_cached_strings(website_client, transformer):
    await website_client.post("/payload", json=SPEC_INPUT)
    transformer.calls.clear()

    response = await website_client.post(
        "/payload",
        json={"list_1": ["last string", "brand new"], "list_2": ["first string", "first string"]},
    )

    assert response.status_code == 201
    assert transformer.calls == {"brand new": 1}


async def test_rejects_lists_of_different_length(website_client, transformer):
    response = await website_client.post("/payload", json={"list_1": ["a"], "list_2": []})

    assert response.status_code == 422
    assert transformer.total_calls == 0


async def test_read_unknown_payload_returns_404(website_client):
    response = await website_client.get(f"/payload/{uuid4()}")

    assert response.status_code == 404


async def test_read_payload_with_malformed_id_returns_422(website_client):
    response = await website_client.get("/payload/not-a-uuid")

    assert response.status_code == 422


@dataclass
class TransactionProbeTransformer:
    """Records how many DB transactions sit open while the external service is being called."""

    open_transactions: list[int] = field(default_factory=list)

    async def transform(self, value: str) -> str:
        # AUTOCOMMIT keeps the probe's own connection out of the count.
        async with engine.connect() as conn:
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            count = await conn.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND state LIKE 'idle in transaction%'"
                )
            )
        self.open_transactions.append(count)
        return value.upper()


async def test_no_transaction_is_held_while_calling_transformer(website_client):
    probe = TransactionProbeTransformer()
    app.dependency_overrides[get_transformer] = lambda: probe

    response = await website_client.post("/payload", json=SPEC_INPUT)

    assert response.status_code == 201
    assert probe.open_transactions == [0] * 6


class FailingTransformer:
    async def transform(self, value: str) -> str:
        raise RuntimeError("external service failed")


async def test_transformer_failure_returns_bad_gateway(website_client):
    app.dependency_overrides[get_transformer] = FailingTransformer

    response = await website_client.post("/payload", json=SPEC_INPUT)

    assert response.status_code == 502
    assert response.json() == {"detail": "Transformer service failed"}
