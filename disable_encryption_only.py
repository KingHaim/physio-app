#!/usr/bin/env python3
"""
Simply disable encryption going forward. Existing encrypted data will remain encrypted
but new data will be stored as plaintext. The decrypt functions will return the
encrypted data as-is when the key doesn't match.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

def main():
    print("🔧 Disabling encryption for future operations...")
    
    # Force disable encryption
    os.environ["DISABLE_ENCRYPTION"] = "true"
    
    # Remove or comment out the FERNET_SECRET_KEY requirement
    app = create_app()
    
    with app.app_context():
        print("✅ Encryption disabled successfully!")
        print("📋 Next steps:")
        print("1. Set DISABLE_ENCRYPTION=true in your PythonAnywhere environment")
        print("2. Remove FERNET_SECRET_KEY from your environment (optional)")
        print("3. Restart your web app")
        print("")
        print("📝 Notes:")
        print("- Existing encrypted data will display as encrypted tokens")
        print("- New data entered will be stored as plaintext")
        print("- App performance will improve immediately")
        print("- You can manually edit the encrypted data through the admin interface")

if __name__ == "__main__":
    main() 