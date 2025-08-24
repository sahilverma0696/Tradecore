import os
import sys
import time
import threading
from datetime import datetime
from typing import Dict, List
import curses
from collections import defaultdict

from src.core.event_bus import EventBus, Subscriber, QuoteReceived, CandleGenerated, EntrySignal, ExitSignal, OrderExecuted
from src.logger_factory import get_logger


class TradingDashboard(Subscriber):
    """Real-time CLI dashboard for monitoring trading activity."""
    
    def __init__(self):
        super().__init__()
        self._logger = get_logger("TradingDashboard")
        self.active_positions = {}
        self.recent_quotes = {}
        self.recent_candles = {}
        self.recent_signals = []
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
        
        # Subscribe to all relevant events
        self.subscribe_to_event(QuoteReceived, self._on_quote_received)
        self.subscribe_to_event(CandleGenerated, self._on_candle_generated)
        self.subscribe_to_event(EntrySignal, self._on_entry_signal)
        self.subscribe_to_event(ExitSignal, self._on_exit_signal)
        self.subscribe_to_event(OrderExecuted, self._on_order_executed)
        
        self._logger.info("TradingDashboard initialized")

    def _on_quote_received(self, event: QuoteReceived):
        """Handle quote received events."""
        self.recent_quotes[event.symbol] = {
            'ltp': event.ltp,
            'volume': event.volume,
            'change': event.change,
            'timestamp': event.timestamp,
            'source': event.source
        }
        self.system_stats['quotes_received'] += 1
        
        # Update active positions with current LTP
        if event.symbol in self.active_positions:
            pos = self.active_positions[event.symbol]
            pos['current_ltp'] = event.ltp
            pos['last_update'] = event.timestamp
            self._calculate_pnl(event.symbol)
        
        # Log live market data to console for debugging
        if hasattr(event, 'raw_data') and event.raw_data.get('stream_type') == 'markPrice':
            mark_price = event.raw_data.get('mark_price', event.ltp)
            index_price = event.raw_data.get('index_price', 0)
            self._logger.debug(f"Live market data: {event.symbol} Mark=${mark_price:.2f} Index=${index_price:.2f}")

    def _on_candle_generated(self, event: CandleGenerated):
        """Handle candle generated events."""
        self.recent_candles[event.symbol] = {
            'candle_data': event.candle_data,
            'timeframe': event.timeframe,
            'timestamp': event.timestamp
        }
        self.system_stats['candles_generated'] += 1

    def _on_entry_signal(self, event: EntrySignal):
        """Handle entry signal events."""
        self.active_positions[event.symbol] = {
            'symbol': event.symbol,
            'side': event.side,
            'entry_price': event.entry_price,
            'entry_vwap': event.entry_vwap,
            'quantity': event.quantity,
            'entry_time': event.timestamp,
            'current_ltp': event.entry_price,
            'unrealized_pnl': 0.0,
            'pnl_pct': 0.0,
            'status': 'ACTIVE',
            'exit_steps': event.exit_steps,
            'last_update': event.timestamp
        }
        
        self.recent_signals.append({
            'type': 'ENTRY',
            'symbol': event.symbol,
            'side': event.side,
            'price': event.entry_price,
            'timestamp': event.timestamp
        })
        
        # Keep only last 20 signals
        if len(self.recent_signals) > 20:
            self.recent_signals.pop(0)
            
        self.system_stats['entry_signals'] += 1

    def _on_exit_signal(self, event: ExitSignal):
        """Handle exit signal events."""
        if event.symbol in self.active_positions:
            pos = self.active_positions[event.symbol]
            pos['exit_price'] = event.exit_price
            pos['exit_reason'] = event.exit_reason
            pos['exit_time'] = event.timestamp
            pos['status'] = 'CLOSED'
            
            # Calculate final PnL
            self._calculate_pnl(event.symbol, final=True)
            
            # Move to closed positions after some time
            threading.Timer(30.0, lambda: self.active_positions.pop(event.symbol, None)).start()
        
        self.recent_signals.append({
            'type': 'EXIT',
            'symbol': event.symbol,
            'price': event.exit_price,
            'reason': event.exit_reason,
            'timestamp': event.timestamp
        })
        
        if len(self.recent_signals) > 20:
            self.recent_signals.pop(0)
            
        self.system_stats['exit_signals'] += 1

    def _on_order_executed(self, event: OrderExecuted):
        """Handle order executed events."""
        self.system_stats['orders_executed'] += 1

    def _calculate_pnl(self, symbol: str, final: bool = False):
        """Calculate P&L for a position."""
        if symbol not in self.active_positions:
            return
            
        pos = self.active_positions[symbol]
        entry_price = pos['entry_price']
        current_price = pos.get('exit_price' if final else 'current_ltp', entry_price)
        quantity = pos['quantity']
        side = pos['side']
        
        if side == 'BUY':
            pnl = (current_price - entry_price) * quantity
        else:  # SELL
            pnl = (entry_price - current_price) * quantity
            
        pnl_pct = (pnl / (entry_price * quantity)) * 100 if entry_price > 0 else 0
        
        pos['unrealized_pnl'] = pnl
        pos['pnl_pct'] = pnl_pct
        
        if final:
            pos['realized_pnl'] = pnl
            self.system_stats['total_pnl'] += pnl

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
        
        # Active Positions Header
        if row < height:
            stdscr.addstr(row, 0, "ACTIVE POSITIONS", curses.A_BOLD)
        row += 1
        
        if row < height:
            header = f"{'Symbol':<10} {'Side':<4} {'Entry':<8} {'Current':<8} {'P&L':<8} {'P&L%':<6} {'Qty':<4} {'Status':<8} {'Time':<8}"
            stdscr.addstr(row, 0, header[:width-1], curses.A_UNDERLINE)
        row += 1
        
        # Active Positions
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
        
        row += 1
        
        # Recent Quotes
        if row < height:
            stdscr.addstr(row, 0, "RECENT QUOTES", curses.A_BOLD)
        row += 1
        
        for symbol, quote in list(self.recent_quotes.items())[-5:]:  # Last 5 quotes
            if row >= height - 10:
                break
                
            quote_line = f"{symbol:<10} LTP: {quote['ltp']:<8.2f} " \
                        f"Vol: {quote['volume']:<8} Change: {quote['change']:<6.2f}% " \
                        f"{quote['timestamp'].strftime('%H:%M:%S')}"
            
            if row < height:
                color = curses.color_pair(1) if quote['change'] >= 0 else curses.color_pair(2)
                stdscr.addstr(row, 0, quote_line[:width-1], color)
            row += 1
        
        row += 1
        
        # Recent Signals
        if row < height:
            stdscr.addstr(row, 0, "RECENT SIGNALS", curses.A_BOLD)
        row += 1
        
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
        """Print simple dashboard to console with enhanced live data display."""
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
        
        # Live Market Data (Enhanced)
        print("🌐 LIVE MARKET DATA:")
        print("-" * 80)
        if self.recent_quotes:
            print(f"{'Symbol':<12} {'Price':<12} {'Source':<15} {'Volume':<10} {'Time':<10} {'Status'}")
            print("-" * 80)
            for symbol, quote in list(self.recent_quotes.items())[-10:]:  # Show last 10 quotes
                price_str = f"${quote['ltp']:.2f}"
                volume_str = f"{quote['volume']:,}" if quote['volume'] > 0 else "N/A"
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
                
                print(f"{symbol:<12} {price_str:<12} {source_str:<15} {volume_str:<10} {time_str:<10} {status}")
        else:
            print("No market data received yet...")
            print("💡 Make sure the streamer is running and publishing quote events")
        
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
