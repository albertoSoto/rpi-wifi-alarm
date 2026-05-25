.PHONY: help install test test-unit test-int lint type run docker-build docker-test docker-run clean

help:  ## show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## install dev deps in current venv
	pip install -e ".[dev]"

test:  ## run all tests
	PYTHONPATH=src python -m pytest -v

test-unit:  ## unit tests only
	PYTHONPATH=src python -m pytest tests/unit -v

test-int:  ## integration tests only
	PYTHONPATH=src python -m pytest tests/integration -v

lint:  ## ruff check + format check
	ruff check src tests
	ruff format --check src tests

type:  ## mypy strict
	mypy src

run:  ## run dev profile locally
	PYTHONPATH=src WIFI_ALARM_PROFILE=dev python -m wifi_alarm

docker-build:  ## build the dev image
	docker compose build

docker-test:  ## run the test suite in container
	docker compose --profile test run --rm test

docker-run:  ## run the dev service in container
	docker compose up

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache **/__pycache__
