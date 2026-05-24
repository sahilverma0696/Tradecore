#!/usr/bin/env python3
"""CLI main entry point for the trading dashboard."""

import sys
import argparse
import threading
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.logger_factory import get_logger


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='Tradecore Trading Dashboard')
    parser.add_argument('--no-curses', action='store_true', 
                       help='Use simple text dashboard instead of curses')
    parser.add_argument('--demo', action='store_true',
                       help='Run dashboard with demo data generation')
    parser.add_argument('--live', action='store_true',
                       help='Connect to live trading system')
    
    args = parser.parse_args()
    
    logger = get_logger("CLI", console_output=True)
    logger.info("Starting Tradecore Trading Dashboard...")
    
    # CRITICAL: Initialize EventBus connection BEFORE creating dashboard
    if args.live:
        logger.info("🔌 Connecting to live system via IPC files...")
        logger.info("💡 Dashboard will read live data from data/live_quotes.json")
        logger.info("💡 Ensure main system is running: python3 -m src.main")
    
    elif args.demo:
        logger.info("🎭 Starting demo data generation...")
        try:
            from src.cli.demo_data import start_demo_data_generator
            demo_thread = threading.Thread(target=start_demo_data_generator, daemon=True)
            demo_thread.start()
            time.sleep(1)  # Let demo data start
        except Exception as e:
            logger.error(f"❌ Failed to start demo data: {e}")
            return 1
    
    # Import and start dashboard - now uses IPC instead of EventBus
    try:
        from src.cli.dashboard import start_dashboard
        
        use_curses = not args.no_curses
        logger.info(f"🖥️  Starting dashboard (curses={'enabled' if use_curses else 'disabled'})")
        
        if args.live:
            logger.info("📡 Dashboard will read live data via IPC files...")
        
        start_dashboard(use_curses=use_curses)
        
    except Exception as e:
        logger.error(f"❌ Dashboard error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

