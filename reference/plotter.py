import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from mplfinance.original_flavor import candlestick_ohlc
from datetime import datetime, timedelta
from pytz import timezone
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import csv
from pathlib import Path

# Timezone setup
IST = timezone('Asia/Kolkata')

class CandlePlotter:
    def __init__(self, output_file="logs/OHLC_VWAP_chart.html", log_dir="logs"):
        self.output_file = output_file
        self.log_dir = Path(log_dir)
        self.data = []
        self.trades = []  # Store trade information
        self.df = pd.DataFrame()
        self.order_logs = self._load_order_logs()

    def add_trade(self, timestamp, side, entry_price, exit_price=None, exit_reason=None):
        """Add trade information to be displayed on the chart"""
        # Convert timestamps to IST if they have timezone info
        if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(IST) if str(timestamp.tzinfo) != 'Asia/Kolkata' else timestamp
        elif isinstance(timestamp, datetime):
            timestamp = IST.localize(timestamp)
            
        self.trades.append({
            'timestamp': timestamp,
            'side': side,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'exit_reason': exit_reason
        })

    def handle_candle(self, name, candle):
        # Convert timestamp to IST if it's timezone-naive
        ts = candle['timestamp']
        if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
            # If timestamp has timezone info, convert to IST
            ts = ts.astimezone(IST) if str(ts.tzinfo) != 'Asia/Kolkata' else ts
        else:
            # If no timezone info, assume it's already in IST
            ts = IST.localize(ts) if isinstance(ts, datetime) else ts
            
        self.data.append({
            'timestamp': ts,
            'open': candle['open'],
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'vwap': candle.get('vwap'),
            'volume': candle.get('volume', 0)
        })

    def _load_order_logs(self):
        """Load order logs from CSV files in the log directory"""
        order_logs = []
        log_files = list(self.log_dir.glob('order_log*.csv'))
        
        if not log_files:
            print("No order log files found in", self.log_dir)
            return pd.DataFrame()
            
        for log_file in sorted(log_files):  # Sort to process in order
            try:
                print(f"Loading order log: {log_file}")
                df = pd.read_csv(log_file)
                
                # Ensure required columns exist
                required_columns = ['timestamp', 'event_type', 'side', 'entry_price']
                if not all(col in df.columns for col in required_columns):
                    print(f"Warning: Missing required columns in {log_file}")
                    continue
                    
                order_logs.append(df)
                print(f"  Loaded {len(df)} rows")
                
            except Exception as e:
                print(f"Error reading log file {log_file}: {e}")
        
        if not order_logs:
            print("No valid order logs found")
            return pd.DataFrame()
            
        # Combine all logs into a single DataFrame
        df = pd.concat(order_logs, ignore_index=True)
        print(f"Total order log entries: {len(df)}")
        
        # Convert timestamp to datetime with timezone
        if 'timestamp' in df.columns:
            print("Converting timestamps...")
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            # If timezone-naive, localize to IST
            if df['timestamp'].dt.tz is None:
                print("Localizing timestamps to IST...")
                df['timestamp'] = df['timestamp'].dt.tz_localize('Asia/Kolkata')
            
            # Print timestamp range for debugging
            print(f"Order log timestamp range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df

    def _process_order_logs(self):
        """Process order logs to extract entry/exit points"""
        if self.order_logs.empty:
            print("No order logs to process")
            return []
            
        print(f"Processing {len(self.order_logs)} order log entries...")
        trades = {}
        
        # Process all rows and group by order_id
        for _, row in self.order_logs.iterrows():
            try:
                order_id = row.get('order_id')
                if not order_id:
                    continue
                    
                if order_id not in trades:
                    trades[order_id] = {}
                    
                if row['event_type'] == 'ENTRY':
                    trades[order_id].update({
                        'entry_ts': row['timestamp'],
                        'entry_price': float(row['entry_price']) if 'entry_price' in row and row['entry_price'] else None,
                        'side': row.get('side', 'BUY').upper(),
                        'instrument': row.get('instrument', '')
                    })
                elif row['event_type'] == 'EXIT':
                    trades[order_id].update({
                        'exit_ts': row['timestamp'],
                        'exit_price': float(row['exit_price']) if 'exit_price' in row and row['exit_price'] else None,
                        'exit_reason': row.get('exit_reason', ''),
                        'pnl': float(row.get('pnl_amount', 0)) if 'pnl_amount' in row and row['pnl_amount'] else 0,
                        'pnl_pct': float(str(row.get('pnl_percent', '0')).replace('%', '')) if 'pnl_percent' in row and row['pnl_percent'] else 0
                    })
            except Exception as e:
                print(f"Error processing order log row: {e}")
                continue
        
        # Convert to list and filter out incomplete trades
        complete_trades = [
            trade for trade in trades.values() 
            if 'entry_ts' in trade and 'exit_ts' in trade
        ]
        
        print(f"Found {len(complete_trades)} complete trades")
        return complete_trades

    def plot_candles(self):
        """Plot OHLC candles with VWAP and volume using Plotly."""
        if self.df.empty or self.df.isnull().all().all():
            print("No data to plot")
            return

        # Create a copy of the dataframe to avoid modifying the original
        df = self.df.copy()
        
        # Ensure we have a proper datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'timestamp' in df.columns:
                # Convert to datetime and set as index
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            elif 'date' in df.columns:
                # Convert to datetime and set as index
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
        
        # Ensure index is timezone-aware
        if df.index.tz is None:
            # If index is timezone-naive, localize to IST
            df.index = df.index.tz_localize('Asia/Kolkata')
        else:
            # If index has timezone info, convert to IST
            df.index = df.index.tz_convert('Asia/Kolkata')
        
        # Load and process order logs
        self.trades = self._process_order_logs()
        
        # Create a single plot (no volume subplot)
        fig = go.Figure()
        
        # Format timestamps for display
        if isinstance(df.index, pd.DatetimeIndex):
            # Format with timezone abbreviation (IST)
            formatted_dates = [ts.strftime('%Y-%m-%d %H:%M:%S IST') for ts in df.index]
        else:
            formatted_dates = [str(i) for i in df.index]
        
        # Add candlestick trace with custom hover text
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='OHLC',
                hovertext=formatted_dates,
                hoverinfo='text+x+y',
                hoverlabel=dict(
                    namelength=-1,  # Show full name
                    font_size=12,
                    font_family="Arial"
                )
            )
        )
        
        # Add VWAP line if available
        if 'vwap' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['vwap'],
                    name='VWAP',
                    line=dict(color='purple', width=2)
                )
            )
        
        # No volume subplot
        
        # Add trade markers from order logs
        print(f"Processing {len(self.trades)} trades...")
        print(f"Candle data range: {df.index[0]} to {df.index[-1]}")
        
        for i, trade in enumerate(self.trades, 1):
            if 'entry_ts' in trade and 'exit_ts' in trade and trade['entry_ts'] and trade['exit_ts']:
                try:
                    # Convert timestamps to pandas Timestamp and ensure timezone
                    entry_ts = pd.to_datetime(trade['entry_ts'])
                    exit_ts = pd.to_datetime(trade['exit_ts'])
                    
                    if entry_ts.tzinfo is None:
                        entry_ts = entry_ts.tz_localize('Asia/Kolkata')
                    if exit_ts.tzinfo is None:
                        exit_ts = exit_ts.tz_localize('Asia/Kolkata')
                    
                    # Find nearest candle indices
                    entry_idx = df.index.get_indexer([entry_ts], method='nearest')[0]
                    exit_idx = df.index.get_indexer([exit_ts], method='nearest')[0]
                    
                    # Get the actual timestamps from the candle data
                    entry_ts_candle = df.index[entry_idx]
                    exit_ts_candle = df.index[exit_idx]
                    
                    # Get prices from the candle data
                    entry_price = trade['entry_price']
                    exit_price = trade['exit_price']
                    
                    print(f"\nTrade {i}:")
                    print(f"  Entry: {entry_ts} (nearest candle: {entry_ts_candle}) at {entry_price}")
                    print(f"  Exit:  {exit_ts} (nearest candle: {exit_ts_candle}) at {exit_price} ({trade.get('exit_reason', '')})")
                    
                    # Add entry marker
                    is_buy = trade.get('side', 'BUY').upper() == 'BUY'
                    entry_symbol = 'triangle-up' if is_buy else 'triangle-down'
                    entry_color = 'green' if is_buy else 'red'
                    
                    fig.add_trace(
                        go.Scatter(
                            x=[entry_ts_candle],
                            y=[entry_price],
                            mode='markers+text',
                            marker=dict(
                                symbol=entry_symbol,
                                color=entry_color,
                                size=12,
                                line=dict(width=1, color='black')
                            ),
                            text=['ENTRY'],
                            textposition='top center',
                            textfont=dict(color='black', size=10),
                            name=f"{trade.get('side', '')} Entry",
                            showlegend=False,
                            xaxis='x',
                            yaxis='y'
                        )
                    )
                    
                    # Add exit marker
                    exit_symbol = 'triangle-down' if is_buy else 'triangle-up'
                    exit_color = 'red' if is_buy else 'green'
                    
                    fig.add_trace(
                        go.Scatter(
                            x=[exit_ts_candle],
                            y=[exit_price],
                            mode='markers+text',
                            marker=dict(
                                symbol=exit_symbol,
                                color=exit_color,
                                size=12,
                                line=dict(width=1, color='black')
                            ),
                            text=[f"EXIT ({trade.get('exit_reason', '')})"],
                            textposition='bottom center',
                            textfont=dict(color='black', size=10),
                            name=f"{trade.get('side', '')} Exit",
                            showlegend=False,
                            xaxis='x',
                            yaxis='y'
                        )
                    )
                    
                    # Add trade line connecting entry and exit
                    fig.add_shape(
                        type="line",
                        x0=entry_ts_candle,
                        y0=entry_price,
                        x1=exit_ts_candle,
                        y1=exit_price,
                        line=dict(
                            color='rgba(100, 100, 100, 0.5)',
                            width=1,
                            dash='dash'
                        ),
                        xref='x',
                        yref='y'
                    )
                    
                    # Add PnL annotation
                    pnl = trade.get('pnl', 0)
                    pnl_pct = trade.get('pnl_pct', 0)
                    mid_idx = (entry_idx + exit_idx) // 2
                    
                    if mid_idx < len(df.index):
                        fig.add_annotation(
                            x=df.index[mid_idx],
                            y=(trade['entry_price'] + trade['exit_price']) / 2,
                            text=f"PnL: {pnl:+.2f} ({pnl_pct:+.2f}%)",
                            showarrow=True,
                            arrowhead=2,
                            arrowsize=1,
                            arrowwidth=2,
                            arrowcolor='black',
                            ax=0,
                            ay=-40,
                            bgcolor='rgba(255, 255, 0, 0.7)',
                            bordercolor='black',
                            borderwidth=1,
                            borderpad=4,
                            opacity=0.8,
                            font=dict(size=10)
                        )
                except Exception as e:
                    print(f"Error plotting trade: {e}")
                    continue
        
        # Calculate time range for x-axis formatting
        if isinstance(df.index, pd.DatetimeIndex) and len(df) > 0:
            # Use already converted IST timestamps
            time_range = (df.index[-1] - df.index[0]).total_seconds()
        else:
            # Fallback to default if not a datetime index
            time_range = 86400  # Default to 1 day
        
        # Set tick format based on time range
        if time_range > 86400 * 30:  # > 30 days
            tickformat = "%Y-%m-%d"
            dtick = "D1"
        elif time_range > 86400:  # > 1 day
            tickformat = "%m-%d %H:%M"
            dtick = 3600000 * 6  # 6 hours
        else:  # < 1 day
            tickformat = "%H:%M:%S"
            dtick = 3600000  # 1 hour
        
        # Update layout
        fig.update_layout(
            title='OHLC with VWAP and Volume',
            xaxis_title='Date/Time (IST)',
            yaxis_title='Price',
            xaxis=dict(
                type='date',
                tickformat=tickformat,
                dtick=dtick,
                rangeslider_visible=False,
                showgrid=True,
                gridcolor='lightgrey',
                tickfont=dict(size=10),
                tickformatstops=[
                    dict(dtickrange=[None, 1000], value="%H:%M:%S.%L"),
                    dict(dtickrange=[1000, 60000], value="%H:%M:%S"),
                    dict(dtickrange=[60000, 3600000], value="%H:%M"),
                    dict(dtickrange=[3600000, 86400000], value="%b %d %H:%M"),
                    dict(dtickrange=[86400000, "M1"], value="%b %d, %Y"),
                    dict(dtickrange=["M1", None], value="%Y")
                ]
            ),
            yaxis=dict(
                gridcolor='lightgrey'
            ),
            height=800,
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            margin=dict(l=50, r=50, t=80, b=50),
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Arial"
            )
        )
        
        # Update y-axes title
        fig.update_yaxes(title_text="Price")
        
        # Store the figure
        self.fig = fig

    def save_plot(self, max_points=1000):
        if not self.data:
            print("No data to plot.")
            return

        self.df = pd.DataFrame(self.data)
        # Convert timestamps to datetime, handling timezone-naive and timezone-aware timestamps
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'], utc=True).dt.tz_convert(None)
        
        # Resample data if too many points
        if len(self.df) > max_points:
            # Calculate the resampling frequency to get close to max_points
            freq = f'{int(len(self.df) / max_points)}min'
            self.df = self.df.set_index('timestamp')
            self.df = self.df.resample(freq).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum',
                'vwap': 'mean'
            }).dropna().reset_index()
            
        self.df['date_num'] = mdates.date2num(self.df['timestamp'])

        self.plot_candles()
        
        # Save figure with optimized settings
        output_dir = os.path.dirname(self.output_file)
        if output_dir:  # Only create directory if path is not empty
            os.makedirs(output_dir, exist_ok=True)
        
        # Save as HTML for interactivity
        html_file = os.path.splitext(self.output_file)[0] + '.html'
        try:
            self.fig.write_html(
                html_file,
                full_html=True,
                include_plotlyjs='cdn',
                auto_open=False
            )
            print(f"Saved interactive plot to: {html_file}")
            
            # Also save as static image
            img_file = os.path.splitext(self.output_file)[0] + '.png'
            self.fig.write_image(
                img_file,
                format='png',
                width=1600,
                height=900,
                scale=1.0
            )
            print(f"Saved static image to: {img_file}")
            
        except Exception as e:
            print(f"Error saving plot: {e}")
            try:
                # Fallback to basic HTML if image export fails
                self.fig.write_html(
                    html_file,
                    full_html=True,
                    include_plotlyjs='cdn',
                    auto_open=False
                )
                print(f"Saved basic interactive plot to: {html_file}")
            except Exception as e2:
                print(f"Failed to save any plot format: {e2}")
