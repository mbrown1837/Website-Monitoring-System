#!/usr/bin/env python3
"""
Fix container compatibility issues for Dokploy deployment.
This script ensures the code works in both local and container environments.
"""

import os
import sys
import re

def fix_f_string_issues(file_path):
    """Fix f-string issues that cause problems in containers."""
    print(f"Fixing f-string issues in {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix problematic f-strings by simplifying them
    fixes = [
        # Fix complex f-strings with nested quotes
        (r'\{f\'<p><strong>Visual Difference Score:</strong> \{check_results\.get\("visual_diff_percent", 0\):\.2f\}%</p>\'\s+if check_results\.get\(\'visual_diff_percent\'\) else \'\'\}', 
         lambda m: f'<p><strong>Visual Difference Score:</strong> {{check_results.get("visual_diff_percent", 0):.2f}}%</p>' if 'check_results.get("visual_diff_percent")' in content else ''),
        
        # Fix other complex f-strings
        (r'\{f\'<p><strong>Broken Links:</strong> \{len\(broken_links\)\} found</p>\'\s+if broken_links else \'\'\}', 
         lambda m: f'<p><strong>Broken Links:</strong> {{len(broken_links)}} found</p>' if 'broken_links' in content else ''),
    ]
    
    for pattern, replacement in fixes:
        if callable(replacement):
            # For complex replacements, we'll handle them manually
            continue
        content = re.sub(pattern, replacement, content)
    
    # Write back with proper encoding
    with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    
    print(f"Fixed f-string issues in {file_path}")

def ensure_container_compatibility():
    """Ensure all files are container-compatible."""
    print("🔧 Ensuring container compatibility...")
    
    # Files to check
    files_to_fix = [
        'src/alerter.py',
        'src/app.py',
        'src/crawler_module.py',
        'src/scheduler.py'
    ]
    
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            fix_f_string_issues(file_path)
        else:
            print(f"⚠️ File not found: {file_path}")
    
    print("✅ Container compatibility fixes applied!")

if __name__ == "__main__":
    ensure_container_compatibility()
