#!/usr/bin/env python3
from app import create_app
from flask import render_template

app = create_app()

with app.app_context():
    try:
        print("Testing privacy policy template...")
        result = render_template('legal/privacy_policy.html')
        print("✅ Privacy policy template rendered successfully")
    except Exception as e:
        print(f"❌ Error rendering privacy policy: {e}")
    
    try:
        print("Testing terms template...")
        result = render_template('legal/terms_and_conditions.html')
        print("✅ Terms template rendered successfully")
    except Exception as e:
        print(f"❌ Error rendering terms: {e}") 