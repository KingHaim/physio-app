#!/usr/bin/env python3
"""
Rewrite encrypted data to plaintext by reading via properties (which decrypt) and writing back while DISABLE_ENCRYPTION is true.
This allows dropping crypto entirely while keeping data readable.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Patient, Treatment, User


def migrate_patients_to_plaintext():
    print("Migrating Patient fields to plaintext...")
    count = 0
    patients = Patient.query.all()
    for p in patients:
        try:
            # Read via properties (auto-decrypt) and assign back to store plaintext
            if p._name:
                p.name = p.name
            if p._email:
                p.email = p.email
            if p._phone:
                p.phone = p.phone
            if p._notes:
                p.notes = p.notes
            if hasattr(p, "_anamnesis") and p._anamnesis:
                p.anamnesis = p.anamnesis
            count += 1
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
                t.notes = t.notes
            count += 1
        except Exception as e:
            print(f"  Failed treatment {t.id}: {e}")
    db.session.commit()
    print(f"✅ Treatments migrated: {count}")


def migrate_user_tokens_to_plaintext():
    print("Migrating User token fields to plaintext (keeping in existing columns)...")
    count = 0
    users = User.query.all()
    for u in users:
        try:
            # Calendly
            token = u.calendly_api_token
            if token:
                u.calendly_api_token = token
            # Google tokens
            gtok = u.google_calendar_token
            if gtok:
                u.google_calendar_token = gtok
            grtok = u.google_calendar_refresh_token
            if grtok:
                u.google_calendar_refresh_token = grtok
            gcsec = u.google_calendar_client_secret
            if gcsec:
                u.google_calendar_client_secret = gcsec
            count += 1
        except Exception as e:
            print(f"  Failed user {u.id}: {e}")
    db.session.commit()
    print(f"✅ Users migrated: {count}")


def main():
    # Force disable encryption
    os.environ.setdefault("DISABLE_ENCRYPTION", "true")
    app = create_app()
    with app.app_context():
        migrate_patients_to_plaintext()
        migrate_treatments_to_plaintext()
        migrate_user_tokens_to_plaintext()


if __name__ == "__main__":
    main() 