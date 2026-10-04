# Caching Service

A FastAPI microservice that builds payloads from two lists of strings. Each string goes through a
"transformer" that stands in for a slow external service, and the transformed strings are
interleaved. Transformer results are cached in Postgres, so a string that was transformed before
is never sent to the transformer again (see [Shortcuts](#shortcuts-and-known-limitations) for the
one concurrent-request exception). The repo also ships `cache-cli`, a small command line client for
exercising the service.

## Quick start (Docker)

```bash
docker compose up -d --build website      # postgres → migrations → API on :8000

curl -s -X POST localhost:8000/payload -H 'content-type: application/json' \
  -d '{"list_1": ["first string", "second string", "third string"],
       "list_2": ["other string", "another string", "last string"]}'
# {"id":"01a1...","message":"Payload created"}               (201)

curl -s localhost:8000/payload/<id>
# {"output":"FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"}
```

The CLI is installed in the same image:

```bash
docker compose exec website cache-cli -h http://localhost:8000 -r 3 \
  -j '{"list_1": ["alpha", "beta"], "list_2": ["gamma", "alpha"]}'
# {"iteration": 1, "id": "01a1...", "created": true,  "elapsed_ms": 523.2, "output": "ALPHA, GAMMA, BETA, ALPHA"}
# {"iteration": 2, "id": "01a1...", "created": false, "elapsed_ms": 7.0,   "output": "ALPHA, GAMMA, BETA, ALPHA"}
# {"iteration": 3, "id": "01a1...", "created": false, "elapsed_ms": 4.5,   "output": "ALPHA, GAMMA, BETA, ALPHA"}
```

Only the first iteration pays the transformer latency (0.5 s per call by default, with the calls
running concurrently). Later iterations reuse the stored payload.

OpenAPI docs: <http://localhost:8000/docs>.

## Local development

Requirements: Python 3.13, Poetry 2.x, Docker.

```bash
make install            # poetry install (in-project .venv)
make up-test            # test Postgres on :5442 (tmpfs, throwaway)
make verify             # ruff fix + format, ty, unit + integration tests
```

| Command | What it does |
|---|---|
| `make unit` / `make integration` | Run one test suite (integration needs `make up-test`) |
| `make coverage` | Both suites with branch coverage |
| `make migrate` / `make migrations msg="..."` | Apply / autogenerate Alembic migrations |
| `poetry run website` | Run the API locally (copy `.env.example` to `.env`; dev DB from `docker compose up -d postgres` on :5441) |
| `poetry run cache-cli --help` | CLI usage |

Configuration uses environment variables with `__` as the nesting delimiter (for example
`DATABASE__URL` or `TRANSFORMER__DELAY_SECONDS`). See `.env.example`.

## API

| Method | Path | Success | Errors |
|---|---|---|---|
| `POST` | `/payload` | `201 {"id", "message": "Payload created"}`, or `200 {"id", "message": "Payload already exists"}` for an input seen before | `422`: lists of different length, empty, longer than 1000 items, or non-string items; `502`: the external transformer failed |
| `GET` | `/payload/{id}` | `200 {"output": "..."}` | `404` unknown id, `422` malformed id |

## How the transformer calls are minimized

`PayloadService.create` (`caching_svc/shared/application/services/payload_service.py`):

1. **Payload reuse.** The request is hashed (SHA-256 of the canonical JSON of both lists). If a
   payload with that hash exists, its id is returned straight away, and neither the transformer
   nor the string cache is touched.
2. **Deduplication within a request.** Duplicate strings, including the same string in both lists,
   collapse to a single lookup.
3. **One cache query.** All distinct strings are looked up with a single `WHERE input_hash IN (...)`.
4. **Transform misses only.** The transformer is called for cache misses only, concurrently but
   bounded by `TRANSFORMER__MAX_CONCURRENCY` (default 10), so one large payload cannot flood the
   external service.
5. **Persist and build.** New results are inserted in one statement, then the output is
   interleaved and the payload is stored.

Steps 1 and 3 run in a short read transaction, and step 5 runs in a short write transaction. No
database connection is held while the transformer is being called, so slow external calls cannot
exhaust the connection pool. A test checks `pg_stat_activity` during transformer calls to prove it.

The deduplication and miss detection are pure functions (`shared/domain/services/payload.py`), and
the bounded fan-out is `transform_many` (`shared/clients/transformer.py`). Both are unit-tested
without a database. The integration tests assert on exact call counts end to end through a
counting transformer double: `tests/integration/shared/test_payload_service.py`,
`tests/integration/apps/website/test_payload_api.py` and
`tests/integration/apps/cli/test_cli_against_service.py`.

## CLI

```
cache-cli [--help] [-h URL] [-r N] [-i FILE|-] [-j JSON] [-o FILE|-]
```

- Arguments are parsed and validated by **pydantic-settings** (`CliSettingsSource`):
  - `--host` must be a URL;
  - `--repeat` must be at least 1;
  - exactly one of `--input` / `--json` must be given.
- The request body is validated with the same schema the server uses, so bad input fails locally
  with exit code `2`. HTTP and connection errors exit with code `1`.
- Only connecting has a timeout. Generating a large payload can take as long as its transformer
  calls do, so reads are not time-limited.
- Every iteration creates the payload, reads it back and writes one JSON line containing the id,
  whether the payload was new, the round-trip time and the output.

## Project layout

The layout follows a layered (hexagonal) structure, and dependencies only point inwards:

```
caching_svc/
  apps/
    website/        # FastAPI: routes/ schemas/ deps/ app.py
    cli/            # cache-cli: settings.py (argument parsing) client.py main.py
  shared/
    domain/         # pure logic: dedup, miss detection, interleave, hashing; exceptions
    clients/        # transformer contract, simulated implementation, bounded transform_many
    models/         # SQLAlchemy models
    persistence/    # repositories (SQL lives here)
    application/    # PayloadService: orchestrates repositories + transformer
  config.py  database.py
alembic/            # migrations
tests/unit/         # no IO: domain, schemas, service with in-memory repos, CLI with mocked HTTP
tests/integration/  # real Postgres: repositories/service, HTTP API, CLI against the app
```

Two rules hold throughout:

- **Data flow:** route → `PayloadService` → repository → database.
- **Transactions:** `PayloadService` opens its own short transactions instead of using a
  request-scoped session. This is a deliberate exception, so that no connection is held while the
  external transformer is called.

## Decisions and assumptions

- **PostgreSQL over SQLite.** It matches the deployment target and gives atomic
  `INSERT ... ON CONFLICT`, which resolves races between concurrent identical requests: they all
  get the same payload id (covered by a test). Tests run against a real Postgres rather than
  SQLite, so they exercise the same SQL that production runs.
- **SQLAlchemy 2.0 (async) + Alembic** rather than SQLModel. This keeps the API schemas separate
  from the table models.
- **Hashes as lookup keys.** Strings can be arbitrarily long, and a B-tree index on long text hits
  Postgres' index row size limit. A hash index key has a fixed size.
- **Order matters.** Swapping the lists or reordering items produces a different output, so it is
  a different payload. Lists are hashed as JSON, so `["a, b"]` and `["a", "b"]` never collide.
- **`201` vs `200` on `POST`.** `201` means a payload was generated now, and `200` means an
  existing one was reused. The body has the same shape in both cases.
- **The payload stores its generated output.** It is not rebuilt from the cache on every `GET`.
  Reads stay a single primary-key lookup, and a payload stays stable even if cache entries are
  ever evicted.
- **"Payloads files"** in the task is read as stored payload records, not files on disk.
- **`-h` means `--host`,** as the specification requires, and `--help` stays long-only. The task
  lists `-h` for both options, which argparse cannot support.
- **The CLI reads only the command line.** Environment and `.env` sources are disabled. Fields
  with aliases ignore `env_prefix`, so otherwise a stray `HOST` variable would silently override
  `--host`.
- **Transformer.** `str.upper()` with a configurable delay that simulates the external service,
  behind a `Transformer` protocol so it can be replaced by a real client.
- **UUID v7 ids:** time-ordered, so inserts are index-friendly.

## Shortcuts and known limitations

- **Concurrent cache misses.** Two concurrent requests that both miss the cache for the same new
  string both call the transformer. The cache stays consistent (`ON CONFLICT DO NOTHING`), but the
  call is duplicated. Preventing that would need a distributed lock or request coalescing, which
  is overkill here.
- **Size limits.** Each list is capped at 1000 items. This keeps the batched `IN (...)` and
  multi-row insert well within Postgres' bind parameter limit. Larger inputs would need chunking.
- **No cache eviction or TTL.** Transformations are deterministic, so cached values never go
  stale.
- **Not production-ready yet.** There is no authentication, rate limiting or metrics, and logging
  is plain stdlib logging.
- **Transformer failures.** If one transformer call fails, the remaining calls for that request
  are cancelled, the cause is logged, and the request fails with `502 Bad Gateway`. Results that
  were already transformed in that request are not persisted, and there are no retries.
