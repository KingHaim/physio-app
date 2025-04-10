from datetime import datetime, timedelta
from app.models import Treatment, Patient, db
from sqlalchemy import func

def mark_past_treatments_as_completed():
    """Mark all past treatments with status 'Scheduled' as 'Completed'"""
    today = datetime.now().date()
    
    # Find all past treatments that are still marked as Scheduled
    past_treatments = Treatment.query.filter(
        Treatment.date < today,
        Treatment.status == 'Scheduled'
    ).all()
    
    count = 0
    for treatment in past_treatments:
        treatment.status = 'Completed'
        count += 1
    
    if count > 0:
        db.session.commit()
        print(f"Automatically marked {count} past treatments as Completed")
    
    return count

def mark_inactive_patients():
    """Mark patients as 'Inactive' if they haven't had a booking in the last 2 months"""
    today = datetime.now().date()
    two_months_ago = today - timedelta(days=60)
    
    # Find all active patients
    active_patients = Patient.query.filter_by(status='Active').all()
    
    count = 0
    for patient in active_patients:
        # Get the latest treatment date for this patient
        latest_treatment = Treatment.query.filter_by(patient_id=patient.id).order_by(Treatment.date.desc()).first()
        
        # If no treatments or latest treatment is older than 2 months, mark as inactive
        if not latest_treatment or latest_treatment.date.date() < two_months_ago:
            patient.status = 'Inactive'
            count += 1
    
    if count > 0:
        db.session.commit()
        print(f"Automatically marked {count} patients as Inactive")
    
    return count 