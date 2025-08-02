from src.market.zerodha.zerodha_streamer import ZerodhaStreamer
from src.market.binance.binance_streamer import BinanceStreamer

def get_streamer(cfg):
    market = cfg.get("market", "zerodha")
    if market == "zerodha":
        return ZerodhaStreamer(
            symbols=[int(s) for s in cfg['symbols']],
            api_key=cfg['api_key'],
            api_secret=cfg['api_secret'],
            name_symbol=cfg['name_symbol'],
            paper_trade=cfg.get('paper_trade', True),
        )
    elif market == "binance":
        return BinanceStreamer(
            symbols=cfg['symbols'],
            name_symbol=cfg['name_symbol']
        )
    else:
        raise ValueError(f"Unknown market: {market}")

# No changes needed, cfg is now always the selected market's config.
