import json
import sys
import time

from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import TextIO

import httpx

from pydantic import ValidationError

from caching_svc.apps.cli.client import PayloadClient
from caching_svc.apps.cli.settings import STD_STREAM, CliSettings, parse_cli_settings
from caching_svc.apps.website.schemas import PayloadCreateSchema


EXIT_OK = 0
EXIT_REQUEST_FAILED = 1
EXIT_USAGE_ERROR = 2

# Generating a payload takes as long as the transformer calls for its new strings, which has no
# meaningful upper bound, so only connecting is time-limited (httpx defaults to 5s for reads).
HTTP_TIMEOUT = httpx.Timeout(10.0, read=None)


def load_payload(settings: CliSettings) -> PayloadCreateSchema:
    """Read the request body from --json, a file or stdin, validated like the server does."""
    if settings.json_payload is not None:
        raw = settings.json_payload
    elif settings.input_file == STD_STREAM:
        raw = sys.stdin.read()
    else:
        raw = Path(str(settings.input_file)).read_text()
    return PayloadCreateSchema.model_validate_json(raw)


def run_iterations(
    client: PayloadClient, payload: PayloadCreateSchema, repeat: int
) -> Iterator[dict[str, object]]:
    """Create and read back the payload ``repeat`` times, yielding one record per iteration.

    Timing is reported so the effect of the cache is visible: only the first iteration should
    pay for the transformer calls.
    """
    for iteration in range(1, repeat + 1):
        started = time.perf_counter()
        created, is_new = client.create(payload)
        generated = client.get(created.id)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)

        yield {
            "iteration": iteration,
            "id": str(created.id),
            "created": is_new,
            "elapsed_ms": elapsed_ms,
            "output": generated.output,
        }


def main(args: list[str], http: httpx.Client | None = None) -> int:
    """CLI entry point; ``http`` lets tests run the CLI against an in-process app."""
    try:
        settings = parse_cli_settings(args)
        payload = load_payload(settings)
    except (ValidationError, OSError) as exc:
        sys.stderr.write(f"cache-cli: invalid input: {exc}\n")
        return EXIT_USAGE_ERROR

    with ExitStack() as stack:
        client = stack.enter_context(
            http or httpx.Client(base_url=str(settings.host), timeout=HTTP_TIMEOUT)
        )
        out: TextIO | None = sys.stdout if settings.output_file == STD_STREAM else None
        try:
            for record in run_iterations(PayloadClient(client), payload, settings.repeat):
                if out is None:
                    # Opened on the first result, so a run that fails before producing anything
                    # does not leave behind an empty (or truncated) output file.
                    out = stack.enter_context(Path(settings.output_file).open("w"))
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
        except httpx.HTTPStatusError as exc:
            sys.stderr.write(
                f"cache-cli: request failed ({exc.response.status_code}): {exc.response.text}\n"
            )
            return EXIT_REQUEST_FAILED
        except httpx.TransportError as exc:
            sys.stderr.write(f"cache-cli: request to {settings.host} failed: {exc!r}\n")
            return EXIT_REQUEST_FAILED
        except OSError as exc:
            sys.stderr.write(f"cache-cli: cannot write output: {exc}\n")
            return EXIT_USAGE_ERROR
    return EXIT_OK


def run() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    run()
