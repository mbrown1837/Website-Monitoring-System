#!/usr/bin/env python3
"""
Test script for enhanced screenshot functionality
"""

import sys
import os
sys.path.append('src')

from src.snapshot_tool import save_visual_snapshot
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_enhanced_screenshot():
    """Test the enhanced screenshot functionality"""
    
    # Test URLs with different characteristics
    test_urls = [
        "https://example.com",  # Simple site
        "https://httpbin.org/html",  # Basic HTML
    ]
    
    site_id = "test_enhanced_001"
    
    for url in test_urls:
        logger.info(f"Testing enhanced screenshot for: {url}")
        
        try:
            # Test regular screenshot
            result = save_visual_snapshot(
                site_id=site_id,
                url=url,
                timestamp=datetime.now(),
                is_baseline=False
            )
            
            if result:
                logger.info(f"✅ Enhanced screenshot successful: {result}")
            else:
                logger.error(f"❌ Enhanced screenshot failed for: {url}")
                
        except Exception as e:
            logger.error(f"❌ Error testing enhanced screenshot for {url}: {e}")

if __name__ == "__main__":
    logger.info("Testing Enhanced Screenshot Features")
    logger.info("=" * 50)
    
    test_enhanced_screenshot()
    
    logger.info("=" * 50)
    logger.info("Enhanced Screenshot Test Complete")
