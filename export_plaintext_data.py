#!/usr/bin/env python3
import os
import sys
import json
import base64
import re
from datetime import datetime

# Ensure project path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cryptography.fernet import Fernet
from app import create_app
from app.models import Patient, Treatment, User, Location, TriggerPoint, UnmatchedCalendlyBooking


BASE64_RE = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')


def try_decrypt(value: str):
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    # Attempt decrypt only if key exists and value looks like Fernet token
    key = os.environ.get('FERNET_SECRET_KEY')
    if not key:
        return value
    try:
        if len(value) < 20 or not BASE64_RE.match(value):
            return value
        token = base64.b64decode(value.encode())
        f = Fernet(key.encode())
        return f.decrypt(token).decode()
    except Exception:
        return value


def serialize_patient(p: Patient):
    return {
        "id": p.id,
        "user_id": p.user_id,
        "portal_user_id": p.portal_user_id,
        "name": try_decrypt(p._name),
        "email": try_decrypt(p._email),
        "phone": try_decrypt(p._phone),
        "notes": try_decrypt(p._notes),
        "anamnesis": try_decrypt(getattr(p, "_anamnesis", None)),
        "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
        "contact": p.contact,
        "diagnosis": p.diagnosis,
        "treatment_plan": p.treatment_plan,
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "address_line1": p.address_line1,
        "address_line2": p.address_line2,
        "city": p.city,
        "postcode": p.postcode,
        "preferred_location": p.preferred_location,
        "ai_suggested_tests": p.ai_suggested_tests,
        "ai_red_flags": p.ai_red_flags,
        "ai_yellow_flags": p.ai_yellow_flags,
        "ai_clinical_notes": p.ai_clinical_notes,
        "ai_analysis_date": p.ai_analysis_date.isoformat() if p.ai_analysis_date else None,
    }


def serialize_treatment(t: Treatment):
    return {
        "id": t.id,
        "patient_id": t.patient_id,
        "treatment_type": t.treatment_type,
        "assessment": t.assessment,
        "notes": try_decrypt(t._notes),
        "status": t.status,
        "provider": t.provider,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "body_chart_url": t.body_chart_url,
        "pain_level": t.pain_level,
        "movement_restriction": t.movement_restriction,
        "evaluation_data": t.evaluation_data,
        "location": t.location,
        "location_id": t.location_id,
        "visit_type": t.visit_type,
        "fee_charged": t.fee_charged,
        "payment_method": t.payment_method,
        "calendly_invitee_uri": t.calendly_invitee_uri,
        "google_calendar_event_id": t.google_calendar_event_id,
        "google_calendar_event_summary": t.google_calendar_event_summary,
        "clinic_share": t.clinic_share,
        "therapist_share": t.therapist_share,
    }


def serialize_user(u: User):
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "is_admin": u.is_admin,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "email_verified": u.email_verified,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "date_of_birth": u.date_of_birth.isoformat() if u.date_of_birth else None,
        "sex": u.sex,
        "license_number": u.license_number,
        "college_acronym": u.college_acronym,
        "clinic_name": u.clinic_name,
        "clinic_address": u.clinic_address,
        "clinic_phone": u.clinic_phone,
        "clinic_email": u.clinic_email,
        "clinic_website": u.clinic_website,
        "clinic_description": u.clinic_description,
        "contribution_base": u.contribution_base,
        "clinic_first_session_fee": u.clinic_first_session_fee,
        "clinic_subsequent_session_fee": u.clinic_subsequent_session_fee,
        "clinic_percentage_agreement": u.clinic_percentage_agreement,
        "clinic_percentage_amount": u.clinic_percentage_amount,
        "currency_symbol": u.currency_symbol,
        "revenue_currency_symbol": u.revenue_currency_symbol,
        # Export tokens decrypted/plain for backup
        "calendly_api_token": try_decrypt(u.calendly_api_token_encrypted) if u.calendly_api_token_encrypted else u.calendly_api_key,
        "calendly_user_uri": u.calendly_user_uri,
        "google_calendar_token": try_decrypt(u.google_calendar_token_encrypted),
        "google_calendar_refresh_token": try_decrypt(u.google_calendar_refresh_token_encrypted),
        "google_calendar_enabled": u.google_calendar_enabled,
        "google_calendar_primary_calendar_id": u.google_calendar_primary_calendar_id,
        "google_calendar_last_sync": u.google_calendar_last_sync.isoformat() if u.google_calendar_last_sync else None,
        "google_calendar_client_id": u.google_calendar_client_id,
        "google_calendar_client_secret": try_decrypt(u.google_calendar_client_secret_encrypted),
        "google_calendar_redirect_uri": u.google_calendar_redirect_uri,
        "role": u.role,
        "language": u.language,
        "consent_given": u.consent_given,
        "consent_date": u.consent_date.isoformat() if u.consent_date else None,
        "oauth_provider": u.oauth_provider,
        "oauth_id": u.oauth_id,
        "avatar_url": u.avatar_url,
        "is_deleted": u.is_deleted,
        "has_unlimited_access": u.has_unlimited_access,
        "is_new_user": u.is_new_user,
    }


def serialize_location(l: Location):
    return {
        "id": l.id,
        "user_id": l.user_id,
        "name": l.name,
        "address": l.address,
        "phone": l.phone,
        "email": l.email,
        "first_session_fee": l.first_session_fee,
        "subsequent_session_fee": l.subsequent_session_fee,
        "fee_percentage": l.fee_percentage,
        "location_type": l.location_type,
        "is_active": l.is_active,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }


def serialize_trigger_point(tp: TriggerPoint):
    return {
        "id": tp.id,
        "treatment_id": tp.treatment_id,
        "location_x": tp.location_x,
        "location_y": tp.location_y,
        "type": tp.type,
        "muscle": tp.muscle,
        "intensity": tp.intensity,
        "symptoms": tp.symptoms,
        "referral_pattern": tp.referral_pattern,
    }


def serialize_unmatched_calendly(b: UnmatchedCalendlyBooking):
    return {
        "id": b.id,
        "user_id": b.user_id,
        "name": b.name,
        "email": b.email,
        "event_type": b.event_type,
        "start_time": b.start_time.isoformat() if b.start_time else None,
        "calendly_invitee_id": b.calendly_invitee_id,
        "status": b.status,
        "matched_patient_id": b.matched_patient_id,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


def main():
    app = create_app()
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(out_dir, f"export_plaintext_{timestamp}.json")

    with app.app_context():
        data = {
            "patients": [serialize_patient(p) for p in Patient.query.all()],
            "treatments": [serialize_treatment(t) for t in Treatment.query.all()],
            "users": [serialize_user(u) for u in User.query.all()],
            "locations": [serialize_location(l) for l in Location.query.all()],
            "trigger_points": [serialize_trigger_point(tp) for tp in TriggerPoint.query.all()],
            "unmatched_calendly_bookings": [serialize_unmatched_calendly(b) for b in UnmatchedCalendlyBooking.query.all()],
        }

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ Exported decrypted data to {out_file}")


if __name__ == "__main__":
    main() 