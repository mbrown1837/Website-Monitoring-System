#!/usr/bin/env python
"""Test script to check which Greenflare implementation is being used."""
import os
import sys
import inspect

# Ensure the src directory is in the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Import CrawlerModule first
from src.crawler_module import CrawlerModule

# Then try to get the GreenflareBot class
try:
    from src.gflare_tk import Crawler as GreenflareBot
except ImportError:
    try:
        from greenflare.greenflare import Crawler as GreenflareBot
    except ImportError:
        try:
            from greenflare.core.crawler import Crawler as GreenflareBot
        except ImportError:
            from greenflare import Crawler as GreenflareBot

def main():
    """Check which Greenflare implementation is being used."""
    print("Checking Greenflare implementation...")
    
    # Get the module where GreenflareBot is defined
    module = inspect.getmodule(GreenflareBot)
    print(f"GreenflareBot is imported from: {module.__name__}")
    print(f"Module file path: {module.__file__}")
    
    # Check if it's our local implementation
    is_local = "src.gflare_tk" in module.__name__
    print(f"Using local implementation: {is_local}")
    
    # Initialize the crawler
    crawler = CrawlerModule()
    bot = crawler.bot
    print(f"Bot class: {bot.__class__.__name__}")
    print(f"Bot methods: {[m for m in dir(bot) if not m.startswith('_')]}")
    
    # Check which methods are being used
    print("\nChecking key methods...")
    for method_name in ['configure', 'run', 'crawl', 'fetch']:
        if hasattr(bot, method_name):
            method = getattr(bot, method_name)
            method_module = inspect.getmodule(method)
            print(f"Method '{method_name}' is from: {method_module.__name__}")
        else:
            print(f"Method '{method_name}' is not available")

if __name__ == "__main__":
    main() 