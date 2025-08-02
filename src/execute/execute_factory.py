from src.execute.zerodha_executioner import ZerodhaExecute
from src.execute.binance_executioner import BinanceExecute

def get_execute(cfg, streamer):
    market = cfg.get("market", "zerodha")
    if market == "zerodha":
        return ZerodhaExecute(
            excel_logger=None,
            expiry=None,
            client=streamer.get_kite()
        )
    elif market == "binance":
        return BinanceExecute(
            excel_logger=None,
            client=streamer.get_client()
        )
    else:
        raise ValueError(f"Unknown market: {market}")
