.PHONY: run cli cli-simple sys test test-eventbus test-streamer test-executor clean

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
