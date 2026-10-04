import json

import pytest

from fastapi.testclient import TestClient

from caching_svc.apps.cli.main import EXIT_OK, main
from caching_svc.apps.website.app import app
from caching_svc.apps.website.deps import get_transformer


pytestmark = pytest.mark.integration


@pytest.fixture
def http_client(transformer):
    app.dependency_overrides[get_transformer] = lambda: transformer
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_repeated_runs_reuse_payload_and_cache(http_client, transformer, tmp_path):
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps({"list_1": ["a", "b"], "list_2": ["c", "a"]}))
    output_file = tmp_path / "out.jsonl"

    exit_code = main(["-i", str(input_file), "-r", "3", "-o", str(output_file)], http_client)

    records = [json.loads(line) for line in output_file.read_text().splitlines()]
    assert exit_code == EXIT_OK
    assert [record["created"] for record in records] == [True, False, False]
    assert len({record["id"] for record in records}) == 1
    assert {record["output"] for record in records} == {"A, C, B, A"}
    assert transformer.calls == {"a": 1, "b": 1, "c": 1}
