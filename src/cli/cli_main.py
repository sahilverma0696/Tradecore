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
    parser.add_argument('--standalone', action='store_true',
                       help='Run dashboard in standalone mode (demo data)')
    
    args = parser.parse_args()
    
    logger = get_logger("CLI")
    logger.info("Starting VWAP Trading Dashboard...")
    
    if args.standalone:
        # Run with demo data
        from src.cli.demo_data import start_demo_data_generator
        demo_thread = threading.Thread(target=start_demo_data_generator, daemon=True)
        demo_thread.start()
        time.sleep(1)  # Let demo data start
    
    # Start dashboard
    use_curses = not args.no_curses
    start_dashboard(use_curses=use_curses)


if __name__ == "__main__":
    main()
