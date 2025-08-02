from src.data_store.quote_database import QuoteDatabase
from src.data_store.quote_database_binance import QuoteDatabaseBinance

def get_quote_database(cfg):
    market = cfg.get("market", "zerodha")
    if market == "binance":
        symbol = cfg.get("name_symbol", "BINANCE")
        return QuoteDatabaseBinance(symbol=symbol)
    else:
        symbol = cfg.get("name_symbol", "NSE_OPTIONS")
        return QuoteDatabase(symbol=symbol)
