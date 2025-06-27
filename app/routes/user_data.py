from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, request
from flask_login import login_required, current_user, logout_user
from app import db
from datetime import datetime
import logging

user_data = Blueprint('user_data', __name__)

@user_data.route('/my-data')
@login_required
def my_data():
    user = current_user
    # Add more fields as needed
    user_info = {
        'username': user.email,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else None,
        'sex': user.sex,
        'license_number': user.license_number,
        'clinic_name': user.clinic_name,
        'clinic_address': user.clinic_address,
        'clinic_phone': user.clinic_phone,
        'clinic_email': user.clinic_email,
        'clinic_website': user.clinic_website,
        'clinic_description': user.clinic_description,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'consent_given': user.consent_given,
        'consent_date': user.consent_date.isoformat() if user.consent_date else None,
        'is_deleted': user.is_deleted,
    }
    return render_template('user_data/my_data.html', user_info=user_info)

@user_data.route('/export_data')
@login_required
def export_data():
    user = current_user
    data = {
        'username': user.email,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else None,
        'sex': user.sex,
        'license_number': user.license_number,
        'clinic_name': user.clinic_name,
        'clinic_address': user.clinic_address,
        'clinic_phone': user.clinic_phone,
        'clinic_email': user.clinic_email,
        'clinic_website': user.clinic_website,
        'clinic_description': user.clinic_description,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'consent_given': user.consent_given,
        'consent_date': user.consent_date.isoformat() if user.consent_date else None,
        'is_deleted': user.is_deleted,
    }
    return jsonify(data)

@user_data.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    """Soft delete account - marks for deletion but preserves data"""
    user = current_user
    user.is_deleted = True
    db.session.commit()
    logout_user()
    flash('Your account has been marked for deletion. If this was a mistake, contact support.', 'info')
    return redirect(url_for('auth.login'))

@user_data.route('/delete_account_permanent', methods=['POST'])
@login_required
def delete_account_permanent():
    """Permanently delete user account and all associated data"""
    user_id = current_user.id
    user_email = current_user.email
    
    try:
        # Import models here to avoid circular imports
        from app.models import (Patient, Treatment, TriggerPoint, PatientReport, 
                               RecurringAppointment, UnmatchedCalendlyBooking, 
                               PracticeReport, Location, UserSubscription, 
                               FixedCost, DataProcessingActivity, UserConsent, 
                               SecurityLog)
        
        # 1. Handle patients owned by this user (physio)
        owned_patients = Patient.query.filter_by(user_id=user_id).all()
        for patient in owned_patients:
            # Delete patient reports
            PatientReport.query.filter_by(patient_id=patient.id).delete()
            
            # Delete recurring appointments
            RecurringAppointment.query.filter_by(patient_id=patient.id).delete()
            
            # Delete treatments and their trigger points
            treatments = Treatment.query.filter_by(patient_id=patient.id).all()
            for treatment in treatments:
                TriggerPoint.query.filter_by(treatment_id=treatment.id).delete()
                db.session.delete(treatment)
            
            # Delete user consents related to this patient
            UserConsent.query.filter_by(patient_id=patient.id).delete()
            
            # Unlink any matched Calendly bookings
            UnmatchedCalendlyBooking.query.filter_by(matched_patient_id=patient.id).update({'matched_patient_id': None})
            
            # Delete the patient record
            db.session.delete(patient)
        
        # 2. Handle if this user is also a patient (portal user)
        if current_user.patient_record:
            patient_record = current_user.patient_record
            # Delete patient reports
            PatientReport.query.filter_by(patient_id=patient_record.id).delete()
            
            # Delete recurring appointments
            RecurringAppointment.query.filter_by(patient_id=patient_record.id).delete()
            
            # Delete treatments and their trigger points
            treatments = Treatment.query.filter_by(patient_id=patient_record.id).all()
            for treatment in treatments:
                TriggerPoint.query.filter_by(treatment_id=treatment.id).delete()
                db.session.delete(treatment)
            
            # Delete user consents related to this patient
            UserConsent.query.filter_by(patient_id=patient_record.id).delete()
            
            # Delete the patient record
            db.session.delete(patient_record)
        
        # 3. Delete user's practice reports
        PracticeReport.query.filter_by(user_id=user_id).delete()
        
        # 4. Delete user's locations
        Location.query.filter_by(user_id=user_id).delete()
        
        # 5. Delete user subscriptions (but preserve for billing history if needed)
        # Note: In production, you might want to mark subscriptions as deleted rather than delete them
        # for compliance with payment processing regulations
        UserSubscription.query.filter_by(user_id=user_id).delete()
        
        # 6. Delete user's fixed costs
        FixedCost.query.filter_by(user_id=user_id).delete()
        
        # 7. Delete data processing activities
        DataProcessingActivity.query.filter_by(user_id=user_id).delete()
        
        # 8. Delete user consents (where user is the practitioner)
        UserConsent.query.filter_by(user_id=user_id).delete()
        
        # 9. Handle unmatched Calendly bookings (nullify user_id but keep records for audit)
        UnmatchedCalendlyBooking.query.filter_by(user_id=user_id).update({'user_id': None})
        
        # 10. Handle security logs (keep for audit trail but anonymize)
        SecurityLog.query.filter_by(user_id=user_id).update({'user_id': None})
        
        # 11. Finally, delete the user account
        user = current_user
        
        # Log the deletion for audit trail
        logging.info(f"Permanent account deletion completed for user {user_email} (ID: {user_id})")
        
        # Logout before deleting
        logout_user()
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        flash('Your account and all associated data have been permanently deleted. Thank you for using our service.', 'success')
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error during permanent account deletion for user {user_email}: {str(e)}")
        flash('An error occurred while deleting your account. Please contact support.', 'danger')
        return redirect(url_for('main.user_settings'))

@user_data.route('/user/profile', methods=['GET'])
@login_required
def get_user_profile():
    user = current_user
    return jsonify({
        'id': user.id,
        'email': user.email,
        'username': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else None,
        'sex': user.sex,
        'license_number': user.license_number,
        'clinic_name': user.clinic_name,
        'clinic_address': user.clinic_address,
        'clinic_phone': user.clinic_phone,
        'clinic_email': user.clinic_email,
        'clinic_website': user.clinic_website,
        'clinic_description': user.clinic_description,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'consent_given': user.consent_given,
        'consent_date': user.consent_date.isoformat() if user.consent_date else None,
        'is_deleted': user.is_deleted,
        'is_admin': user.is_admin,
    })