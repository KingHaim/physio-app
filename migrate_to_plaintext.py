#!/usr/bin/env python3
"""
Rewrite encrypted data to plaintext by decrypting directly, then writing back while DISABLE_ENCRYPTION is true.
"""
import os
import sys
import base64
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cryptography.fernet import Fernet
from app import create_app, db
from app.models import Patient, Treatment, User


BASE64_RE = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')


def force_decrypt(value: str):
    """Force decrypt regardless of app config"""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    
    # Get key directly from environment
    key = os.environ.get('FERNET_SECRET_KEY')
    if not key:
        print(f"Warning: No FERNET_SECRET_KEY, returning as-is: {value[:50]}...")
        return value
    
    try:
        # Check if it looks like a Fernet token
        if len(value) < 20 or not BASE64_RE.match(value):
            return value
        
        # Try to decrypt
        token = base64.b64decode(value.encode())
        f = Fernet(key.encode())
        decrypted = f.decrypt(token).decode()
        print(f"  Decrypted: {value[:30]}... -> {decrypted[:30]}...")
        return decrypted
    except Exception as e:
        print(f"  Failed to decrypt {value[:30]}...: {e}")
        return value


def migrate_patients_to_plaintext():
    print("Migrating Patient fields to plaintext...")
    count = 0
    patients = Patient.query.all()
    for p in patients:
        try:
            changed = False
            if p._name:
                decrypted = force_decrypt(p._name)
                if decrypted != p._name:
                    p._name = decrypted
                    changed = True
            
            if p._email:
                decrypted = force_decrypt(p._email)
                if decrypted != p._email:
                    p._email = decrypted
                    changed = True
            
            if p._phone:
                decrypted = force_decrypt(p._phone)
                if decrypted != p._phone:
                    p._phone = decrypted
                    changed = True
            
            if p._notes:
                decrypted = force_decrypt(p._notes)
                if decrypted != p._notes:
                    p._notes = decrypted
                    changed = True
            
            if hasattr(p, "_anamnesis") and p._anamnesis:
                decrypted = force_decrypt(p._anamnesis)
                if decrypted != p._anamnesis:
                    p._anamnesis = decrypted
                    changed = True
            
            if changed:
                count += 1
                print(f"  Updated patient {p.id}")
                
        except Exception as e:
            print(f"  Failed patient {p.id}: {e}")
    
    db.session.commit()
    print(f"✅ Patients migrated: {count}")


def migrate_treatments_to_plaintext():
    print("Migrating Treatment fields to plaintext...")
    count = 0
    treatments = Treatment.query.all()
    for t in treatments:
        try:
            if t._notes:
                decrypted = force_decrypt(t._notes)
                if decrypted != t._notes:
                    t._notes = decrypted
                    count += 1
                    print(f"  Updated treatment {t.id}")
        except Exception as e:
            print(f"  Failed treatment {t.id}: {e}")
    
    db.session.commit()
    print(f"✅ Treatments migrated: {count}")


def migrate_user_tokens_to_plaintext():
    print("Migrating User token fields to plaintext...")
    count = 0
    users = User.query.all()
    for u in users:
        try:
            changed = False
            
            # Calendly token
            if u.calendly_api_token_encrypted:
                decrypted = force_decrypt(u.calendly_api_token_encrypted)
                if decrypted != u.calendly_api_token_encrypted:
                    u.calendly_api_token_encrypted = decrypted
                    changed = True
            
            # Google tokens
            if u.google_calendar_token_encrypted:
                decrypted = force_decrypt(u.google_calendar_token_encrypted)
                if decrypted != u.google_calendar_token_encrypted:
                    u.google_calendar_token_encrypted = decrypted
                    changed = True
            
            if u.google_calendar_refresh_token_encrypted:
                decrypted = force_decrypt(u.google_calendar_refresh_token_encrypted)
                if decrypted != u.google_calendar_refresh_token_encrypted:
                    u.google_calendar_refresh_token_encrypted = decrypted
                    changed = True
            
            if u.google_calendar_client_secret_encrypted:
                decrypted = force_decrypt(u.google_calendar_client_secret_encrypted)
                if decrypted != u.google_calendar_client_secret_encrypted:
                    u.google_calendar_client_secret_encrypted = decrypted
                    changed = True
            
            if changed:
                count += 1
                print(f"  Updated user {u.id}")
                
        except Exception as e:
            print(f"  Failed user {u.id}: {e}")
    
    db.session.commit()
    print(f"✅ Users migrated: {count}")


def main():
    # Ensure we have the key for decryption
    if not os.environ.get('FERNET_SECRET_KEY'):
        print("❌ FERNET_SECRET_KEY required for decryption!")
        return
    
    # Force disable encryption for the app behavior
    os.environ.setdefault("DISABLE_ENCRYPTION", "true")
    app = create_app()
    
    with app.app_context():
        migrate_patients_to_plaintext()
        migrate_treatments_to_plaintext()
        migrate_user_tokens_to_plaintext()


if __name__ == "__main__":
    main() 