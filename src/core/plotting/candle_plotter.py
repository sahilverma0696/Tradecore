from src.logger_factory import get_logger
import pandas as pd
from collections import deque

import plotly.graph_objs as go
from dash import Dash, dcc, html
from dash.dependencies import Output, Input

class CandlePlotter:
    def __init__(self, max_candles=100):
        self.max_candles = max_candles
        self.candles = deque(maxlen=max_candles)
        self._logger = get_logger("CandlePlotter")
        self._logger.info(f"Initialized CandlePlotter with max_candles={max_candles}")

    def _pad_candles(self):
        # Pad candles to always have max_candles, using None or NaN for missing values
        candles_list = list(self.candles)
        missing = self.max_candles - len(candles_list)
        if missing > 0:
            # If there are candles, use first timestamp as base, else use pd.Timestamp.now()
            if candles_list:
                first_ts = pd.to_datetime(candles_list[0]['timestamp'])
            else:
                first_ts = pd.Timestamp.now()
            freq = '1min'  # or your candle interval
            pad_timestamps = pd.date_range(start=first_ts, periods=self.max_candles, freq=freq)
            # Fill missing candles with NaN at the end (right side)
            pad_candles = [{
                'timestamp': ts,
                'open': None,
                'high': None,
                'low': None,
                'close': None,
                'vwap': None
            } for ts in pad_timestamps[-missing:]]
            candles_list = candles_list + pad_candles
        else:
            # Ensure timestamps are evenly spaced
            freq = '1min'
            first_ts = pd.to_datetime(candles_list[0]['timestamp'])
            pad_timestamps = pd.date_range(start=first_ts, periods=self.max_candles, freq=freq)
            for i, candle in enumerate(candles_list):
                candle['timestamp'] = pad_timestamps[i]
        return pd.DataFrame(candles_list)

    def add_candle(self, name, candle):
        self.candles.append(candle)
        self._logger.info(f"Plotter data updated for {name}: OHLC({candle['open']:.2f},{candle['high']:.2f},{candle['low']:.2f},{candle['close']:.2f}) VWAP({candle.get('vwap', 'N/A')}) Volume({candle.get('volume', 0)}) Total candles: {len(self.candles)}")

    def plot(self):
        df = self._pad_candles()
        if df.empty:
            self._logger.warning("No candle data to plot.")
            return
        fig = go.Figure()
        mask = df['open'].notnull()
        # Calculate y-axis range with padding
        if mask.any():
            min_price = min(df['low'][mask].min(), df['vwap'][mask].min())
            max_price = max(df['high'][mask].max(), df['vwap'][mask].max())
            padding = (max_price - min_price) * 0.05  # 5% padding
            y_range = [min_price - padding, max_price + padding]
            self._logger.info(f"Chart range calculated: {y_range[0]:.2f} to {y_range[1]:.2f}")
        else:
            y_range = None
            self._logger.warning("No valid price data for chart range calculation")
            
        # Improved OHLC candlestick chart
        fig.add_trace(go.Candlestick(
            x=df['timestamp'][mask],
            open=df['open'][mask],
            high=df['high'][mask],
            low=df['low'][mask],
            close=df['close'][mask],
            name='OHLC',
            increasing=dict(
                line=dict(color='#26a69a', width=1),
                fillcolor='rgba(38, 166, 154, 0.3)'
            ),
            decreasing=dict(
                line=dict(color='#ef5350', width=1),
                fillcolor='rgba(239, 83, 80, 0.3)'
            )
        ))
        
        # VWAP as proper black line
        fig.add_trace(go.Scatter(
            x=df['timestamp'][mask],
            y=df['vwap'][mask],
            mode='lines',
            name='VWAP',
            line=dict(color='black', width=2),
            connectgaps=True
        ))
        
        fig.update_layout(
            title="OHLC + VWAP Chart",
            xaxis_title="Time",
            yaxis_title="Price",
            xaxis=dict(
                type='category',
                tickmode='array',
                tickvals=df['timestamp'][mask],
                range=[df['timestamp'].iloc[0], df['timestamp'].iloc[-1]]
            ),
            yaxis=dict(
                range=y_range
            ) if y_range else {},
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        fig.show()
        self._logger.info("Static OHLC + VWAP chart displayed successfully.")

    def start_live_plot(self, interval=1000):
        app = Dash(__name__)
        app.layout = html.Div([
            dcc.Graph(id='live-candle-plot'),
            dcc.Interval(id='interval-component', interval=interval, n_intervals=0)
        ])

        @app.callback(
            Output('live-candle-plot', 'figure'),
            Input('interval-component', 'n_intervals')
        )
        def update_live_plot(n):
            df = self._pad_candles()
            fig = go.Figure()
            mask = df['open'].notnull()
            
            if mask.any():
                min_price = min(df['low'][mask].min(), df['vwap'][mask].min())
                max_price = max(df['high'][mask].max(), df['vwap'][mask].max())
                padding = (max_price - min_price) * 0.05
                y_range = [min_price - padding, max_price + padding]
                self._logger.debug(f"Live chart update {n}: range {y_range[0]:.2f} to {y_range[1]:.2f}, {mask.sum()} candles")
            else:
                y_range = None
                
            if not df.empty and mask.any():
                # Improved OHLC candlestick chart
                fig.add_trace(go.Candlestick(
                    x=df['timestamp'][mask],
                    open=df['open'][mask],
                    high=df['high'][mask],
                    low=df['low'][mask],
                    close=df['close'][mask],
                    name='OHLC',
                    increasing=dict(
                        line=dict(color='#26a69a', width=1),
                        fillcolor='rgba(38, 166, 154, 0.3)'
                    ),
                    decreasing=dict(
                        line=dict(color='#ef5350', width=1),
                        fillcolor='rgba(239, 83, 80, 0.3)'
                    )
                ))
                
                # VWAP as proper black line
                fig.add_trace(go.Scatter(
                    x=df['timestamp'][mask],
                    y=df['vwap'][mask],
                    mode='lines',
                    name='VWAP',
                    line=dict(color='black', width=2),
                    connectgaps=True
                ))
                
            fig.update_layout(
                title="Live OHLC + VWAP Chart",
                xaxis_title="Time",
                yaxis_title="Price",
                xaxis=dict(
                    type='category',
                    tickmode='array',
                    tickvals=df['timestamp'][mask],
                    range=[df['timestamp'].iloc[0], df['timestamp'].iloc[-1]]
                ),
                yaxis=dict(
                    range=y_range
                ) if y_range else {},
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            return fig

        self._logger.info(f"Starting live plot server with interval={interval} ms on port 8080")
        app.run(debug=False, port=8080, host='0.0.0.0')
