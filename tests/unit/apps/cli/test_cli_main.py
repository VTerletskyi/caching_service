import io
import json

import httpx
import pytest

from caching_svc.apps.cli.main import (
    EXIT_OK,
    EXIT_REQUEST_FAILED,
    EXIT_USAGE_ERROR,
    load_payload,
    main,
)
from caching_svc.apps.cli.settings import parse_cli_settings


pytestmark = pytest.mark.unit

PAYLOAD_ID = "0199b0a2-7a3e-7c3e-8a51-3f1d9d6f2a10"


def fake_service(request: httpx.Request) -> httpx.Response:
    if request.method == "POST":
        return httpx.Response(201, json={"id": PAYLOAD_ID, "message": "Payload created"})
    return httpx.Response(200, json={"output": "A, B"})


def test_load_payload_reads_stdin(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"list_1": ["a"], "list_2": ["b"]}'))

    payload = load_payload(parse_cli_settings(["-i", "-"]))

    assert payload.list_1 == ["a"]


def test_main_writes_one_json_line_per_iteration(tmp_path):
    output_file = tmp_path / "out.jsonl"
    http = httpx.Client(transport=httpx.MockTransport(fake_service), base_url="http://test")

    exit_code = main(
        ["-j", '{"list_1": ["a"], "list_2": ["b"]}', "-r", "2", "-o", str(output_file)], http
    )

    records = [json.loads(line) for line in output_file.read_text().splitlines()]
    assert exit_code == EXIT_OK
    assert [record["iteration"] for record in records] == [1, 2]
    assert records[0] | {"elapsed_ms": None} == {
        "iteration": 1,
        "id": PAYLOAD_ID,
        "created": True,
        "elapsed_ms": None,
        "output": "A, B",
    }


@pytest.mark.parametrize(
    "args",
    [
        ["-j", "not json"],
        ["-j", '{"list_1": ["a"], "list_2": []}'],
        ["-i", "/does/not/exist.json"],
    ],
    ids=["malformed-json", "different-length", "missing-file"],
)
def test_main_rejects_invalid_input(args, capsys):
    assert main(args) == EXIT_USAGE_ERROR
    assert "invalid input" in capsys.readouterr().err


def test_main_reports_server_errors(capsys):
    http = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(500, text="boom")),
        base_url="http://test",
    )

    exit_code = main(["-j", '{"list_1": ["a"], "list_2": ["b"]}'], http)

    assert exit_code == EXIT_REQUEST_FAILED
    assert "500" in capsys.readouterr().err


def test_main_reports_transport_errors(capsys):
    def time_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    http = httpx.Client(transport=httpx.MockTransport(time_out), base_url="http://test")

    exit_code = main(["-j", '{"list_1": ["a"], "list_2": ["b"]}'], http)

    assert exit_code == EXIT_REQUEST_FAILED
    assert "ReadTimeout" in capsys.readouterr().err


def test_main_does_not_create_output_file_when_request_fails(tmp_path):
    output_file = tmp_path / "out.jsonl"
    http = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(502, text="down")),
        base_url="http://test",
    )

    exit_code = main(["-j", '{"list_1": ["a"], "list_2": ["b"]}', "-o", str(output_file)], http)

    assert exit_code == EXIT_REQUEST_FAILED
    assert not output_file.exists()


def test_main_reports_unwritable_output(tmp_path, capsys):
    http = httpx.Client(transport=httpx.MockTransport(fake_service), base_url="http://test")
    output_file = tmp_path / "missing-dir" / "out.jsonl"

    exit_code = main(["-j", '{"list_1": ["a"], "list_2": ["b"]}', "-o", str(output_file)], http)

    assert exit_code == EXIT_USAGE_ERROR
    assert "cannot write output" in capsys.readouterr().err
