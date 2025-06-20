#!/usr/bin/env python3
"""
Script to check and fix syntax issues in config.py
Run this on PythonAnywhere to identify the exact issue.
"""

import ast
import sys

def check_config_syntax():
    """Check if config.py has syntax errors and identify the issue."""
    try:
        with open('config.py', 'r') as f:
            content = f.read()
        
        # Try to parse the file
        ast.parse(content)
        print("✅ config.py has valid syntax")
        return True
        
    except SyntaxError as e:
        print(f"❌ Syntax error in config.py:")
        print(f"   Line {e.lineno}: {e.text}")
        print(f"   Error: {e.msg}")
        
        # Show the problematic line
        lines = content.split('\n')
        if e.lineno <= len(lines):
            print(f"   Problematic line: {lines[e.lineno - 1]}")
        
        return False
    except Exception as e:
        print(f"❌ Error reading config.py: {e}")
        return False

def fix_common_issues():
    """Fix common syntax issues in config.py."""
    try:
        with open('config.py', 'r') as f:
            content = f.read()
        
        # Common fixes
        fixes = [
            # Fix leading zeros in numbers
            ('03600', '3600'),
            ('07200', '7200'),
            # Fix trailing commas
            (',\n    WTF_CSRF_SSL_STRICT = False', '\n    WTF_CSRF_SSL_STRICT = False'),
            # Fix any other common issues
        ]
        
        original_content = content
        for old, new in fixes:
            content = content.replace(old, new)
        
        if content != original_content:
            with open('config.py', 'w') as f:
                f.write(content)
            print("✅ Fixed common syntax issues in config.py")
            return True
        else:
            print("ℹ️  No common syntax issues found")
            return False
            
    except Exception as e:
        print(f"❌ Error fixing config.py: {e}")
        return False

if __name__ == '__main__':
    print("🔍 Checking config.py syntax...")
    
    if check_config_syntax():
        print("✅ config.py is syntactically correct")
    else:
        print("\n🔧 Attempting to fix common issues...")
        if fix_common_issues():
            print("\n🔍 Re-checking syntax...")
            check_config_syntax()
        else:
            print("\n❌ Please manually check line 43 in config.py")
            print("   Common issues:")
            print("   - Leading zeros in numbers (03600 → 3600)")
            print("   - Trailing commas")
            print("   - Invalid characters") 