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
                               SecurityLog, Clinic, ClinicMembership, ClinicSubscription)
        
        logging.info(f"Starting permanent account deletion for user {user_email} (ID: {user_id})")
        
        # 1. Handle clinic memberships first
        try:
            clinic_memberships = ClinicMembership.query.filter_by(user_id=user_id).all()
            for membership in clinic_memberships:
                db.session.delete(membership)
            logging.info(f"Deleted {len(clinic_memberships)} clinic memberships")
        except Exception as e:
            logging.error(f"Error deleting clinic memberships: {str(e)}")
            raise
        
        # 2. Handle patients owned by this user (physio)
        try:
            owned_patients = Patient.query.filter_by(user_id=user_id).all()
            logging.info(f"Found {len(owned_patients)} patients to delete")

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
            logging.info(f"Deleted {len(owned_patients)} patients and their data")
        except Exception as e:
            logging.error(f"Error deleting patients for user {user_id}: {e}")
            raise
        
        # 3. Handle if this user is also a patient (portal user)
        try:
            if hasattr(current_user, 'patient_record') and current_user.patient_record:
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
                logging.info("Deleted user's patient record")
        except Exception as e:
            logging.error(f"Error deleting user patient record: {str(e)}")
            raise
        
        # 4. Delete user's practice reports
        try:
            practice_reports_deleted = PracticeReport.query.filter_by(user_id=user_id).delete()
            logging.info(f"Deleted {practice_reports_deleted} practice reports")
        except Exception as e:
            logging.error(f"Error deleting practice reports: {str(e)}")
            raise
        
        # 5. Delete user's locations
        try:
            locations_deleted = Location.query.filter_by(user_id=user_id).delete()
            logging.info(f"Deleted {locations_deleted} locations")
        except Exception as e:
            logging.error(f"Error deleting locations: {str(e)}")
            raise
        
        # 6. Delete user subscriptions
        try:
            subscriptions_deleted = UserSubscription.query.filter_by(user_id=user_id).delete()
            logging.info(f"Deleted {subscriptions_deleted} user subscriptions")
        except Exception as e:
            logging.error(f"Error deleting user subscriptions: {str(e)}")
            raise
        
        # 7. Delete user's fixed costs
        try:
            costs_deleted = FixedCost.query.filter_by(user_id=user_id).delete()
            logging.info(f"Deleted {costs_deleted} fixed costs")
        except Exception as e:
            logging.error(f"Error deleting fixed costs: {str(e)}")
            raise
        
        # 8. Delete data processing activities
        try:
            activities_deleted = DataProcessingActivity.query.filter_by(user_id=user_id).delete()
            logging.info(f"Deleted {activities_deleted} data processing activities")
        except Exception as e:
            logging.error(f"Error deleting data processing activities: {str(e)}")
            raise
        
        # 9. Delete user consents (where user is the practitioner)
        try:
            consents_deleted = UserConsent.query.filter_by(user_id=user_id).delete()
            logging.info(f"Deleted {consents_deleted} user consents")
        except Exception as e:
            logging.error(f"Error deleting user consents: {str(e)}")
            raise
        
        # 10. Handle unmatched Calendly bookings (nullify user_id but keep records for audit)
        try:
            bookings_updated = UnmatchedCalendlyBooking.query.filter_by(user_id=user_id).update({'user_id': None})
            logging.info(f"Anonymized {bookings_updated} calendly bookings")
        except Exception as e:
            logging.error(f"Error anonymizing calendly bookings: {str(e)}")
            raise
        
        # 11. Handle security logs (keep for audit trail but anonymize)
        try:
            logs_updated = SecurityLog.query.filter_by(user_id=user_id).update({'user_id': None})
            logging.info(f"Anonymized {logs_updated} security logs")
        except Exception as e:
            logging.error(f"Error anonymizing security logs: {str(e)}")
            raise
        
        # 12. Finally, delete the user account
        try:
            # Import User model to get the actual instance
            from app.models import User
            # Get the actual User instance from database (not the LocalProxy)
            user = User.query.get(user_id)
            if not user:
                raise Exception(f"User with ID {user_id} not found in database")
            # Logout before deleting
            logout_user()
            # Delete the user instance
            db.session.delete(user)
            # Commit all changes
            db.session.commit()
            logging.info(f"Permanent account deletion completed for user {user_email} (ID: {user_id})")
            flash('Your account and all associated data have been permanently deleted. Thank you for using our service.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            logging.error(f"Error deleting user account: {str(e)}")
            raise
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Error during permanent account deletion for user {user_email}: {str(e)}"
        logging.error(error_msg)
        # Print to console for debugging
        print(error_msg)
        flash(f'An error occurred while deleting your account: {str(e)}. Please contact support.', 'danger')
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