.PHONY: run test clean

run:
	python3 -m src.main

test:
	python3 -m unittest discover -s tests

clean:
	bash scripts/clean_logs.sh
