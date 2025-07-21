#!/usr/bin/env python
"""Test script to check if the official greenflare package has the required API."""
import os
import sys
import importlib.util
import inspect

def check_module_exists(module_name):
    """Check if a module exists."""
    return importlib.util.find_spec(module_name) is not None

def main():
    """Check if the official greenflare package has the required API."""
    print("Checking official greenflare package...")
    
    # Check if greenflare is installed
    if not check_module_exists('greenflare'):
        print("Official greenflare package is not installed.")
        return
        
    print("Official greenflare package is installed.")
    
    # Try to import from different possible locations
    possible_modules = [
        'greenflare',
        'greenflare.greenflare',
        'greenflare.core.crawler',
        'greenflare.core'
    ]
    
    crawler_class = None
    module_name = None
    
    for module_path in possible_modules:
        try:
            module = importlib.import_module(module_path)
            if hasattr(module, 'Crawler'):
                crawler_class = module.Crawler
                module_name = module_path
                print(f"Found Crawler class in {module_path}")
                break
        except ImportError:
            print(f"Could not import {module_path}")
    
    if crawler_class is None:
        print("Could not find Crawler class in greenflare package.")
        return
    
    # Check if the Crawler class has the required methods
    print(f"\nCrawler class from {module_name}:")
    
    required_methods = ['configure', 'run', 'crawl', 'fetch']
    
    for method_name in required_methods:
        has_method = hasattr(crawler_class, method_name)
        print(f"Has '{method_name}' method: {has_method}")
    
    # Try to instantiate the Crawler class
    try:
        crawler = crawler_class()
        print("\nSuccessfully instantiated Crawler class.")
        
        # Print available methods
        methods = [m for m in dir(crawler) if not m.startswith('_')]
        print(f"Available methods: {methods}")
        
    except Exception as e:
        print(f"\nError instantiating Crawler class: {e}")

if __name__ == "__main__":
    main() 