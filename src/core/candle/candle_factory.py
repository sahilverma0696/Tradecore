"""CandleFactory: Returns the correct candle maker for Zerodha or Binance."""
from src.core.candle.candle_maker import CandleMaker
from src.core.candle.candle_binance import CandleBinance

def get_candle_maker(cfg):
    market = cfg.get('market', 'zerodha')
    if market == 'binance':
        return CandleBinance()
    return CandleMaker()
