#!/usr/bin/env python3
"""CLI Dashboard entry point."""

import sys
import argparse
import threading
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.cli.dashboard import start_dashboard
from src.logger_factory import get_logger


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='VWAP Trading Dashboard')
    parser.add_argument('--no-curses', action='store_true', 
                       help='Use simple text dashboard instead of curses')
    parser.add_argument('--demo', action='store_true',
                       help='Run dashboard with demo data generation')
    parser.add_argument('--live', action='store_true',
                       help='Connect to live trading system')
    
    args = parser.parse_args()
    
    logger = get_logger("CLI", console_output=True)
    logger.info("Starting VWAP Trading Dashboard...")
    
    if args.demo:
        # Run with demo data
        logger.info("Starting demo data generation...")
        from src.cli.demo_data import start_demo_data_generator
        demo_thread = threading.Thread(target=start_demo_data_generator, daemon=True)
        demo_thread.start()
        time.sleep(1)  # Let demo data start
    elif args.live:
        logger.info("Connecting to live trading system EventBus...")
        # CLI will automatically subscribe to EventBus when dashboard starts
    
    # Start dashboard
    use_curses = not args.no_curses
    logger.info(f"Starting dashboard (curses={'enabled' if use_curses else 'disabled'})")
    start_dashboard(use_curses=use_curses)


if __name__ == "__main__":
    main()
