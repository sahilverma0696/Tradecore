.PHONY: run test clean

# To run with Binance as the market:
# make run MARKET=binance
run:
	python3 -m src.main

test:
	python3 -m unittest discover -s tests

clean:
	bash scripts/clean_logs.sh
