import os
import sys
import time
import threading
from datetime import datetime
from typing import Dict, List
import curses
from collections import defaultdict
import json

from src.logger_factory import get_logger


class TradingDashboard:
    """Real-time CLI dashboard reading from IPC files."""
    
    def __init__(self):
        self._logger = get_logger("TradingDashboard", console_output=True)
        
        # Data storage
        self.recent_quotes = {}
        self.recent_candles = {}
        self.recent_signals = []
        self.active_positions = {}  # Add missing attribute
        self.system_stats = {
            'quotes_received': 0,
            'candles_generated': 0,
            'entry_signals': 0,
            'exit_signals': 0,
            'orders_executed': 0,
            'total_pnl': 0.0
        }
        self.start_time = datetime.now()
        self.running = False
        
        # IPC file paths for reading live data
        self._quote_file = "data/live_quotes.json"
        self._event_file = "data/live_events.json"
        
        self._logger.info("✅ TradingDashboard initialized for IPC file reading")

    def _read_live_quotes(self):
        """Read live quotes from IPC file."""
        try:
            if os.path.exists(self._quote_file):
                with open(self._quote_file, 'r') as f:
                    quotes_data = json.load(f)
                
                for symbol, quote_data in quotes_data.items():
                    # Parse timestamp
                    try:
                        timestamp_str = quote_data.get('timestamp', '')
                        if timestamp_str:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        else:
                            timestamp = datetime.now()
                    except:
                        timestamp = datetime.now()
                    
                    self.recent_quotes[symbol] = {
                        'symbol': symbol,
                        'ltp': quote_data.get('ltp', 0.0),
                        'ltq': quote_data.get('ltq', 0.0),
                        'timestamp': timestamp,
                        'source': quote_data.get('source', 'Unknown')
                    }
                    
                # Update stats
                self.system_stats['quotes_received'] = len(self.recent_quotes)
                
        except Exception as e:
            self._logger.debug(f"Could not read quotes file: {e}")

    def _read_live_events(self):
        """Read latest event from IPC file."""
        try:
            if os.path.exists(self._event_file):
                with open(self._event_file, 'r') as f:
                    event_data = json.load(f)
                
                event_type = event_data.get('type', '')
                if event_type == 'CandleGenerated':
                    # Process candle event
                    data = event_data.get('data', {})
                    symbol = data.get('symbol', 'Unknown')
                    self.recent_candles[symbol] = {
                        'symbol': symbol,
                        'timestamp': datetime.fromisoformat(event_data.get('timestamp', datetime.now().isoformat())),
                        'open': data.get('open', 0.0),
                        'high': data.get('high', 0.0),
                        'low': data.get('low', 0.0),
                        'close': data.get('close', 0.0),
                        'volume': data.get('volume', 0.0),
                        'vwap': data.get('vwap', 0.0)
                    }
                    self.system_stats['candles_generated'] += 1
                    
        except Exception as e:
            self._logger.debug(f"Could not read events file: {e}")

    def start_curses_dashboard(self):
        """Start the curses-based dashboard."""
        try:
            curses.wrapper(self._curses_main)
        except KeyboardInterrupt:
            self._logger.info("Dashboard stopped by user")
        except Exception as e:
            self._logger.error(f"Dashboard error: {e}")
        finally:
            self.running = False

    def _curses_main(self, stdscr):
        """Main curses loop."""
        self.running = True
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(1)   # Non-blocking input
        stdscr.timeout(1000)  # 1 second timeout
        
        # Color pairs
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Profit
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)    # Loss
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK) # Warning
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)   # Info
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)   # Header
        
        while self.running:
            try:
                stdscr.clear()
                self._draw_dashboard(stdscr)
                stdscr.refresh()
                
                # Check for exit
                key = stdscr.getch()
                if key == ord('q') or key == ord('Q'):
                    break
                    
            except Exception as e:
                self._logger.error(f"Dashboard draw error: {e}")
                time.sleep(1)

    def _draw_dashboard(self, stdscr):
        """Draw the dashboard interface."""
        # Read latest data from IPC files FIRST
        self._read_live_quotes()
        self._read_live_events()
        
        height, width = stdscr.getmaxyx()
        row = 0
        
        # Header
        title = f"VWAP Trading Dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        stdscr.addstr(row, 0, title.center(width), curses.color_pair(5) | curses.A_BOLD)
        row += 2
        
        # System Stats
        uptime = datetime.now() - self.start_time
        stats_line = f"Uptime: {uptime} | Quotes: {self.system_stats['quotes_received']} | " \
                    f"Candles: {self.system_stats['candles_generated']} | " \
                    f"Entries: {self.system_stats['entry_signals']} | " \
                    f"Exits: {self.system_stats['exit_signals']} | " \
                    f"Total P&L: ${self.system_stats['total_pnl']:.2f}"
        
        if row < height:
            stdscr.addstr(row, 0, stats_line[:width-1])
        row += 2
        
        # Debug: Show IPC file status
        quote_file_exists = os.path.exists(self._quote_file)
        event_file_exists = os.path.exists(self._event_file)
        
        if row < height:
            ipc_status = f"IPC Files: Quotes={quote_file_exists} Events={event_file_exists} Count={len(self.recent_quotes)}"
            stdscr.addstr(row, 0, ipc_status[:width-1], curses.color_pair(4))
        row += 1
        
        # Live Market Data Header - Show Symbol, LTP, LTQ
        if row < height:
            stdscr.addstr(row, 0, "LIVE MARKET DATA", curses.A_BOLD)
        row += 1
        
        if row < height:
            header = f"{'Symbol':<12} {'LTP':<10} {'LTQ':<10} {'Source':<12} {'Time':<8} {'Status':<6}"
            stdscr.addstr(row, 0, header[:width-1], curses.A_UNDERLINE)
        row += 1
        
        # Live Market Data - Show all quotes
        if self.recent_quotes:
            for symbol, quote in self.recent_quotes.items():
                if row >= height - 10:  # Leave space for other sections
                    break
                    
                # Calculate data freshness
                age = (datetime.now() - quote['timestamp']).total_seconds()
                if age < 5:
                    color = curses.color_pair(1)  # Green for fresh
                    status = "LIVE"
                elif age < 30:
                    color = curses.color_pair(3)  # Yellow for recent
                    status = "OK"
                else:
                    color = curses.color_pair(2)  # Red for stale
                    status = "STALE"
                
                time_str = quote['timestamp'].strftime('%H:%M:%S')
                
                quote_line = f"{symbol:<12} {quote['ltp']:<10.2f} {quote['ltq']:<10.4f} " \
                            f"{quote['source'][:11]:<12} {time_str:<8} {status:<6}"
                
                if row < height:
                    stdscr.addstr(row, 0, quote_line[:width-1], color)
                row += 1
        else:
            if row < height:
                stdscr.addstr(row, 0, "❌ No market data - check main system status", curses.color_pair(2))
            row += 1
        
        row += 1
        
        # Active Positions Header
        if row < height:
            stdscr.addstr(row, 0, "ACTIVE POSITIONS", curses.A_BOLD)
        row += 1
        
        if row < height:
            header = f"{'Symbol':<10} {'Side':<4} {'Entry':<8} {'Current':<8} {'P&L':<8} {'P&L%':<6} {'Qty':<4} {'Status':<8} {'Time':<8}"
            stdscr.addstr(row, 0, header[:width-1], curses.A_UNDERLINE)
        row += 1
        
        # Active Positions - now properly initialized
        if self.active_positions:
            for symbol, pos in self.active_positions.items():
                if row >= height - 5:  # Leave space for other sections
                    break
                    
                pnl_color = curses.color_pair(1) if pos['pnl_pct'] >= 0 else curses.color_pair(2)
                time_str = pos['entry_time'].strftime('%H:%M:%S')
                
                pos_line = f"{symbol:<10} {pos['side']:<4} {pos['entry_price']:<8.2f} " \
                          f"{pos['current_ltp']:<8.2f} {pos['unrealized_pnl']:<8.2f} " \
                          f"{pos['pnl_pct']:<6.1f} {pos['quantity']:<4} " \
                          f"{pos['status']:<8} {time_str:<8}"
                
                if row < height:
                    stdscr.addstr(row, 0, pos_line[:width-1], pnl_color)
                row += 1
        else:
            if row < height:
                stdscr.addstr(row, 0, "No active positions", curses.color_pair(3))
            row += 1
        
        row += 1
        
        # Recent Signals
        if row < height:
            stdscr.addstr(row, 0, "RECENT SIGNALS", curses.A_BOLD)
        row += 1
        
        if self.recent_signals:
            for signal in self.recent_signals[-8:]:  # Last 8 signals
                if row >= height - 2:
                    break
                    
                signal_line = f"{signal['timestamp'].strftime('%H:%M:%S')} " \
                             f"{signal['type']:<5} {signal['symbol']:<10} " \
                             f"{signal.get('side', 'N/A'):<4} @ {signal['price']:<8.2f}"
                
                if 'reason' in signal:
                    signal_line += f" ({signal['reason']})"
                
                if row < height:
                    color = curses.color_pair(1) if signal['type'] == 'ENTRY' else curses.color_pair(2)
                    stdscr.addstr(row, 0, signal_line[:width-1], color)
                row += 1
        else:
            if row < height:
                stdscr.addstr(row, 0, "No recent signals", curses.color_pair(3))
            row += 1
        
        # Help text
        if height > 10:
            help_text = "Press 'q' to quit"
            stdscr.addstr(height-1, 0, help_text, curses.color_pair(4))

    def start_simple_dashboard(self):
        """Start a simple text-based dashboard (no curses)."""
        self.running = True
        print("Starting VWAP Trading Dashboard...")
        print("Press Ctrl+C to exit\n")
        
        try:
            while self.running:
                self._print_simple_dashboard()
                time.sleep(2)  # Update every 2 seconds
        except KeyboardInterrupt:
            print("\nDashboard stopped by user")
            self.running = False

    def _print_simple_dashboard(self):
        """Print simple dashboard to console with live IPC data."""
        # Read latest data from IPC files
        self._read_live_quotes()
        self._read_live_events()
        
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print("=" * 80)
        print(f"📊 VWAP Trading Dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # System Stats
        uptime = datetime.now() - self.start_time
        print(f"⏱️  Uptime: {uptime} | 📈 Quotes: {self.system_stats['quotes_received']} | "
              f"🕯️  Candles: {self.system_stats['candles_generated']} | "
              f"💰 Total P&L: ${self.system_stats['total_pnl']:.2f}")
        print()
        
        # IPC Connection Status with more detail
        quote_file_exists = os.path.exists(self._quote_file)
        event_file_exists = os.path.exists(self._event_file)
        
        print(f"🔌 IPC Status: Quotes File={quote_file_exists}, Events File={event_file_exists}")
        print(f"📊 Data Loaded: {len(self.recent_quotes)} quotes, {len(self.recent_candles)} candles")
        
        # Debug: Show raw file contents if no quotes
        if not self.recent_quotes and quote_file_exists:
            try:
                with open(self._quote_file, 'r') as f:
                    raw_data = f.read()[:200]  # First 200 chars
                print(f"🔍 Quote file preview: {raw_data}")
            except:
                print("🔍 Could not read quote file")
        print()
        
        # Live Market Data - Show Symbol, LTP, LTQ
        print("🌐 LIVE MARKET DATA (via IPC):")
        print("-" * 80)
        if self.recent_quotes:
            print(f"{'Symbol':<12} {'LTP':<12} {'LTQ':<12} {'Source':<15} {'Time':<10} {'Status'}")
            print("-" * 80)
            
            # Show ALL quotes, not just last 10
            for symbol, quote in self.recent_quotes.items():
                ltp_str = f"${quote['ltp']:.2f}"
                ltq_str = f"{quote['ltq']:.4f}" if quote['ltq'] > 0 else "0.0000"
                time_str = quote['timestamp'].strftime('%H:%M:%S')
                source_str = quote.get('source', 'Unknown')[:14]
                
                # Add status indicator for recent data
                age = (datetime.now() - quote['timestamp']).total_seconds()
                if age < 5:
                    status = "🟢 LIVE"
                elif age < 30:
                    status = "🟡 RECENT"
                else:
                    status = "🔴 STALE"
                
                print(f"{symbol:<12} {ltp_str:<12} {ltq_str:<12} {source_str:<15} {time_str:<10} {status}")
        else:
            print("❌ No market data available...")
            print("💡 Debug info:")
            print(f"   Quote file exists: {quote_file_exists}")
            print(f"   Event file exists: {event_file_exists}")
            print(f"   Quote file path: {self._quote_file}")
            print(f"   Recent quotes count: {len(self.recent_quotes)}")
        
        print()
        
        # Active Positions
        print("📋 ACTIVE POSITIONS:")
        print("-" * 80)
        if self.active_positions:
            print(f"{'Symbol':<10} {'Side':<4} {'Entry':<8} {'Current':<8} {'P&L':<8} {'P&L%':<6} {'Status':<8}")
            for symbol, pos in self.active_positions.items():
                pnl_indicator = "📈" if pos['pnl_pct'] >= 0 else "📉"
                print(f"{symbol:<10} {pos['side']:<4} {pos['entry_price']:<8.2f} "
                      f"{pos['current_ltp']:<8.2f} {pos['unrealized_pnl']:<8.2f} "
                      f"{pos['pnl_pct']:<6.1f} {pos['status']:<8} {pnl_indicator}")
        else:
            print("No active positions")
        
        print()
        
        # Recent Candles
        if self.recent_candles:
            print("🕯️  RECENT CANDLES:")
            print("-" * 80)
            print(f"{'Symbol':<12} {'Open':<8} {'High':<8} {'Low':<8} {'Close':<8} {'Volume':<8} {'VWAP':<8}")
            print("-" * 80)
            for symbol, candle in list(self.recent_candles.items())[-5:]:
                print(f"{symbol:<12} {candle['open']:<8.2f} {candle['high']:<8.2f} "
                      f"{candle['low']:<8.2f} {candle['close']:<8.2f} {candle['volume']:<8.2f} "
                      f"{candle['vwap']:<8.2f}")
            print()
        
        # Recent Signals
        if self.recent_signals:
            print("📡 RECENT SIGNALS:")
            print("-" * 80)
            for signal in self.recent_signals[-5:]:  # Show last 5 signals
                signal_time = signal['timestamp'].strftime('%H:%M:%S')
                signal_type = signal['type']
                symbol = signal['symbol']
                price = signal['price']
                
                signal_indicator = "🔵" if signal_type == 'ENTRY' else "🔴"
                print(f"{signal_time} {signal_indicator} {signal_type} {symbol} @ ${price:.2f}")
            print()
        
        print("💡 Reading live data via IPC files | Press Ctrl+C to exit")

def start_dashboard(use_curses=True):
    """Start the trading dashboard."""
    dashboard = TradingDashboard()
    
    if use_curses:
        try:
            dashboard.start_curses_dashboard()
        except Exception as e:
            print(f"Curses not available: {e}")
            print("Falling back to simple dashboard...")
            dashboard.start_simple_dashboard()
    else:
        dashboard.start_simple_dashboard()
    
    return dashboard


if __name__ == "__main__":
    start_dashboard()
    if self.recent_quotes:
        print(f"{'Symbol':<12} {'LTP':<12} {'LTQ':<12} {'Source':<15} {'Time':<10} {'Status'}")
        print("-" * 80)
        for symbol, quote in list(self.recent_quotes.items())[-10:]:  # Show last 10 quotes
            ltp_str = f"${quote['ltp']:.2f}"
            ltq_str = f"{quote['ltq']:.4f}" if quote['ltq'] > 0 else "0.0000"
            time_str = quote['timestamp'].strftime('%H:%M:%S')
            source_str = quote.get('source', 'Unknown')[:14]
            
            # Add status indicator for recent data
            age = (datetime.now() - quote['timestamp']).total_seconds()
            if age < 5:
                status = "🟢 LIVE"
            elif age < 30:
                status = "🟡 RECENT"
            else:
                status = "🔴 STALE"
            
            print(f"{symbol:<12} {ltp_str:<12} {ltq_str:<12} {source_str:<15} {time_str:<10} {status}")
    else:
        print("❌ No market data received yet...")
        print("💡 Troubleshooting steps:")
        print("   1. Ensure main system is running: python3 -m src.main")
        print("   2. Check if BinanceStreamer is publishing events")
        print("   3. Verify EventBus connection in main system")
        print("   4. Check for any errors in the main system logs")
    
    print()
    
    # Active Positions
    print("📋 ACTIVE POSITIONS:")
    print("-" * 80)
    if self.active_positions:
        print(f"{'Symbol':<10} {'Side':<4} {'Entry':<8} {'Current':<8} {'P&L':<8} {'P&L%':<6} {'Status':<8}")
        for symbol, pos in self.active_positions.items():
            pnl_indicator = "📈" if pos['pnl_pct'] >= 0 else "📉"
            print(f"{symbol:<10} {pos['side']:<4} {pos['entry_price']:<8.2f} "
                  f"{pos['current_ltp']:<8.2f} {pos['unrealized_pnl']:<8.2f} "
                  f"{pos['pnl_pct']:<6.1f} {pos['status']:<8} {pnl_indicator}")
    else:
        print("No active positions")
    
    print()
    
    # Recent Signals
    if self.recent_signals:
        print("📡 RECENT SIGNALS:")
        print("-" * 80)
        for signal in self.recent_signals[-5:]:  # Show last 5 signals
            signal_time = signal['timestamp'].strftime('%H:%M:%S')
            signal_type = signal['type']
            symbol = signal['symbol']
            price = signal['price']
            
            signal_indicator = "🔵" if signal_type == 'ENTRY' else "🔴"
            print(f"{signal_time} {signal_indicator} {signal_type} {symbol} @ ${price:.2f}")
        print()
    
    print("💡 Commands: --demo (demo data) | --live (live system) | Ctrl+C (exit)")
