.PHONY: run test test-eventbus clean

run:
	python3 -m src.main

test:
	python3 -m unittest discover -s tests

test-eventbus:
	python3 -m unittest tests.test_event_bus -v

clean:
	bash scripts/clean_logs.sh
