#!/usr/bin/env python
"""Simple script to discover and run all unit tests in the 'tests' directory."""
import unittest
import os
import sys

# Ensure the src directory is in the Python path for imports within tests
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

if __name__ == '__main__':
    print(f"Discovering tests in: {os.path.join(PROJECT_ROOT, 'tests')}")
    # Create a TestLoader instance
    loader = unittest.TestLoader()
    
    # Discover tests in the 'tests' directory
    # The pattern 'test_*.py' will match files like test_config_loader.py
    suite = loader.discover(start_dir=os.path.join(PROJECT_ROOT, 'tests'), pattern='test_*.py')
    
    # Create a TextTestRunner instance
    # verbosity=2 provides more detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Run the tests
    result = runner.run(suite)
    
    # Exit with an appropriate code (0 for success, 1 for failure)
    if result.wasSuccessful():
        sys.exit(0)
    else:
        sys.exit(1) 