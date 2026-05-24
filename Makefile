.PHONY: run cli cli-simple sys test test-eventbus test-streamer test-executor clean \
        docker-build docker-up docker-down docker-cli docker-sys docker-logs

# ── Local ─────────────────────────────────────────────────────────────────────

run:
	python3 -m src.main

cli:
	python3 -m src.cli.cli_main --live

cli-simple:
	python3 -m src.cli.cli_main --live --no-curses

sys:
	python3 -m src.cli.sys_cli

test:
	python3 -m unittest discover -s tests

test-eventbus:
	python3 -m unittest tests.test_event_bus -v

test-streamer:
	python3 -m pytest tests/test_streamer.py -v

test-executor:
	python3 -m pytest tests/test_executor.py -v

clean:
	bash scripts/clean_logs.sh

# ── Docker ────────────────────────────────────────────────────────────────────

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-cli:
	docker compose exec engine python3 -m src.cli.cli_main --live --no-curses

docker-sys:
	docker compose exec engine python3 -m src.cli.sys_cli

docker-logs:
	docker compose logs -f engine
