from datetime import datetime, timedelta
from flask import current_app
from app.models import Treatment, Patient, db
from sqlalchemy import func

def mark_past_treatments_as_completed(user_id=None):
    """Mark past treatments with status 'Scheduled' as 'Completed'"""
    today = datetime.now().date()
    
    query = Treatment.query.filter(
        Treatment.created_at < today,
        Treatment.status == 'Scheduled'
    )

    if user_id:
        query = query.join(Patient).filter(Patient.user_id == user_id)
        
    past_treatments = query.all()
    
    count = 0
    for treatment in past_treatments:
        treatment.status = 'Completed'
        count += 1
    
    if count > 0:
        db.session.commit()
        current_app.logger.info(
            "Automatically marked %s past treatments as Completed (user_id: %s)",
            count,
            user_id if user_id else 'global'
        )
    
    return count


def mark_inactive_patients(user_id=None):
    """Mark patients as 'Inactive' if they haven't had a booking in the last 2 months"""
    today = datetime.now().date()
    two_months_ago = today - timedelta(days=60)
    
    patient_query = Patient.query.filter_by(status='Active')
    if user_id:
        patient_query = patient_query.filter_by(user_id=user_id)
        
    active_patients = patient_query.all()
    
    count = 0
    for patient in active_patients:
        # When checking latest_treatment, it should also be implicitly filtered by user if patient list is filtered.
        # However, for clarity or if patient list wasn't pre-filtered, you might join Treatment and filter by Patient.user_id here too.
        # For now, relying on the active_patients list being correctly filtered.
        latest_treatment = Treatment.query.filter_by(patient_id=patient.id).order_by(Treatment.created_at.desc()).first()
        
        if not latest_treatment or latest_treatment.created_at.date() < two_months_ago:
            patient.status = 'Inactive'
            count += 1
    
    if count > 0:
        db.session.commit()
        current_app.logger.info(
            "Automatically marked %s patients as Inactive (user_id: %s)",
            count,
            user_id if user_id else 'global'
        )
    
    return count
