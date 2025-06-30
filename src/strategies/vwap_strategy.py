from src.logger_factory import get_logger

class VwapStrategy:
    """Simple VWAP cross strategy providing 'long', 'short', or None."""
    def __init__(self):
        self._logger = get_logger("VWAPStrategy")
        self.last_decision = None
        self.last_decision_candle = None

    # ------------------------------------------------------------------
    def generate_signal(self, candles, symbol, timestamp):
        # candles is CandleMaker-like but we only need last consolidated 5-min candle passed in main flow.
        return None  # placeholder

    def check_reopen_position(self, price):
        return None
