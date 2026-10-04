POETRY ?= poetry
PATHS  := caching_svc tests alembic

.PHONY: install migrations migrate unit integration test-one coverage lint fmt fix type-check up down up-test verify

install:
	$(POETRY) install

migrations:
	$(POETRY) run alembic revision --autogenerate -m "$(msg)"

migrate:
	$(POETRY) run alembic upgrade head

unit:
	$(POETRY) run pytest -m unit

integration:
	$(POETRY) run pytest -m integration

# Run a single test by name: make test-one m=unit k=test_name
test-one:
	$(POETRY) run pytest -m $(or $(m),unit) -k "$(k)"

coverage:
	$(POETRY) run pytest -m "unit or integration" --cov --cov-report=term

lint:
	$(POETRY) run ruff check $(PATHS)

fmt:
	$(POETRY) run ruff format $(PATHS)

fix:
	-$(POETRY) run ruff check --fix $(PATHS)
	$(POETRY) run ruff format $(PATHS)

type-check:
	$(POETRY) run ty check

up:
	docker compose up -d --build

down:
	docker compose down

up-test:
	docker compose up postgres-test -d --wait

# Full verification: lint-fix + type-check + unit + integration
verify:
	$(MAKE) fix
	$(MAKE) type-check
	$(MAKE) unit
	$(MAKE) integration
