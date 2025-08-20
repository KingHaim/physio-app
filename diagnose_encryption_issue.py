#!/usr/bin/env python3
import os
import sys
import base64

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cryptography.fernet import Fernet
from app import create_app, db
from app.models import Patient

def test_encryption_key():
    """Test if the key works for basic encryption/decryption"""
    key = "XXvMEPzOwlhXJ97dWW3Sln8u118o7cCeCabCac_1EnI="
    
    try:
        f = Fernet(key.encode())
        test_text = "Hello World"
        encrypted = f.encrypt(test_text.encode())
        encrypted_b64 = base64.b64encode(encrypted).decode()
        print(f"✅ Key works for new encryption: {test_text} -> {encrypted_b64[:50]}...")
        
        # Try to decrypt it back
        decrypted_bytes = base64.b64decode(encrypted_b64.encode())
        decrypted_text = f.decrypt(decrypted_bytes).decode()
        print(f"✅ Key works for decryption: {decrypted_text}")
        return True
    except Exception as e:
        print(f"❌ Key doesn't work: {e}")
        return False

def test_existing_data():
    """Test decryption of existing database data"""
    key = "XXvMEPzOwlhXJ97dWW3Sln8u118o7cCeCabCac_1EnI="
    f = Fernet(key.encode())
    
    app = create_app()
    with app.app_context():
        # Get a sample patient with encrypted data
        patient = Patient.query.filter(Patient._name.isnot(None)).first()
        if not patient:
            print("❌ No patients with encrypted names found")
            return
        
        encrypted_name = patient._name
        print(f"🔍 Testing encrypted name: {encrypted_name[:50]}...")
        
        try:
            # Try different decoding approaches
            
            # Method 1: Direct base64 decode
            try:
                token_bytes = base64.b64decode(encrypted_name.encode())
                decrypted = f.decrypt(token_bytes).decode()
                print(f"✅ Method 1 success: {decrypted}")
                return
            except Exception as e:
                print(f"❌ Method 1 failed: {e}")
            
            # Method 2: Check if it's double-encoded
            try:
                # Maybe it's base64 encoded twice?
                first_decode = base64.b64decode(encrypted_name.encode()).decode()
                second_decode = base64.b64decode(first_decode.encode())
                decrypted = f.decrypt(second_decode).decode()
                print(f"✅ Method 2 (double-encoded) success: {decrypted}")
                return
            except Exception as e:
                print(f"❌ Method 2 failed: {e}")
            
            # Method 3: Raw bytes
            try:
                decrypted = f.decrypt(encrypted_name.encode()).decode()
                print(f"✅ Method 3 (raw) success: {decrypted}")
                return
            except Exception as e:
                print(f"❌ Method 3 failed: {e}")
                
        except Exception as e:
            print(f"❌ All methods failed: {e}")

def main():
    print("🔍 Diagnosing encryption issue...")
    
    # Set the key
    os.environ["FERNET_SECRET_KEY"] = "XXvMEPzOwlhXJ97dWW3Sln8u118o7cCeCabCac_1EnI="
    
    print("\n1. Testing if the key works for new encryption:")
    if test_encryption_key():
        print("\n2. Testing existing database data:")
        test_existing_data()
    else:
        print("❌ The key itself doesn't work!")

if __name__ == "__main__":
    main() 