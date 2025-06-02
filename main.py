#!/usr/bin/env python
"""Main entry point for the Website Monitoring System CLI."""
import os
import sys

# Ensure the src directory is in the Python path
# This allows running the CLI from the project root (e.g., python main.py ...)
# without needing to install the package or modify PYTHONPATH externally.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

# Now that src is in path, we can import from our modules
from src.cli import cli
from src.config_loader import load_config # Ensure config is loaded before CLI commands might need it
from src.logger_setup import setup_logging # Ensure logger is set up

if __name__ == '__main__':
    # It's good practice to ensure config is loaded and logger is set up 
    # before any CLI command that might depend on them is executed.
    # Though individual modules already call setup_logging and get_config,
    # calling them here ensures they run once at the very start if this is the entry point.
    load_config() 
    setup_logging()
    cli() 