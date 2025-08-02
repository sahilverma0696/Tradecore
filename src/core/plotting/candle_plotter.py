import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation
import pandas as pd
from collections import deque

class CandlePlotter:
    def __init__(self, max_candles=100):
        self.candles = deque(maxlen=max_candles)
        self.fig, self.ax = plt.subplots()
        self.vwap_line, = self.ax.plot([], [], label='VWAP', color='orange')
        self.ohlc_lines = []
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        self.ax.set_title("OHLC + VWAP")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Price")
        self.ax.legend()

    def add_candle(self, name, candle):
        self.candles.append(candle)

    def plot(self):
        df = pd.DataFrame(list(self.candles))
        if df.empty:
            return
        self.ax.clear()
        self.ax.set_title("OHLC + VWAP")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Price")
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        # Plot OHLC as candlesticks
        for idx, row in df.iterrows():
            color = 'green' if row['close'] >= row['open'] else 'red'
            self.ax.plot([row['timestamp'], row['timestamp']], [row['low'], row['high']], color=color)
            self.ax.plot([row['timestamp'], row['timestamp']], [row['open'], row['close']], color=color, linewidth=4)
        # Plot VWAP
        self.ax.plot(df['timestamp'], df['vwap'], label='VWAP', color='orange')
        self.ax.legend()
        plt.pause(0.01)

    def start_live_plot(self, interval=1000):
        def update(frame):
            self.plot()
        ani = FuncAnimation(self.fig, update, interval=interval)
        plt.show()

# Example usage (add this to your main script, not here):
# from src.core.plotting.candle_plotter import CandlePlotter
# plotter = CandlePlotter()
# for candle in candles:  # candles is a list/dict of your candle data
#     plotter.add_candle("BTCUSDT", candle)
# plotter.plot()  # For static plot
# plotter.start_live_plot()  # For live plot
# To integrate with main, see main.py changes.
