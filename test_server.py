#!/usr/bin/env python3

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import create_app
    print("✓ App import successful")
    
    app = create_app()
    print("✓ App creation successful")
    
    print("Starting server on port 5003...")
    app.run(debug=True, host='0.0.0.0', port=5003)
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc() 