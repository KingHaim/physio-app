# app/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, current_app, session, send_file
from datetime import datetime, timedelta, date, time
from calendar import monthrange, day_name # Import day_name
from sqlalchemy import func, extract, or_, case, cast, Float, exc # Add exc import
from app.models import db, Patient, Treatment, TriggerPoint, UnmatchedCalendlyBooking, PatientReport, RecurringAppointment, User, PracticeReport, Plan  # Added Plan
import json
from app.utils import mark_past_treatments_as_completed, mark_inactive_patients
from flask_login import login_required, current_user, logout_user # Import current_user and logout_user
from io import BytesIO
from xhtml2pdf import pisa
import markdown
import os
from collections import defaultdict, Counter # Add Counter import
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash
import functools # Import functools for wraps
import requests
import pytz # <<< Import pytz
import traceback # Add traceback import
from flask_wtf import FlaskForm # Import FlaskForm
from flask_wtf.csrf import generate_csrf # Import generate_csrf
import stripe # Ensure stripe is imported if not already
from app.models import User, Plan, UserSubscription, Patient, Treatment, PatientReport # Make sure User, db are imported
from app.forms import UpdateEmailForm, ChangePasswordForm # Import the new forms

# Define timezones
UTC = pytz.utc
LOCAL_TZ = pytz.timezone('Europe/Madrid') # <<< Replace with your actual local timezone

main = Blueprint('main', __name__)

# --- Role Checking Decorator ---
def physio_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated: # Ensure user is logged in first
            return redirect(url_for('auth.login', next=request.url))
        if current_user.role == 'patient':
            # Redirect patients to their specific dashboard
            return redirect(url_for('main.patient_dashboard'))
        return f(*args, **kwargs)
    return decorated_function
# --- End Decorator ---

# Define the 2025 tax brackets based on the provided image
# Each dict represents a bracket with its lower/upper income bounds,
# description, and minimum contribution base.
TAX_BRACKETS_2025 = [
    {'lower': 0,       'upper': 670,      'desc': 'Hasta 670 €',              'base': 653.59},
    {'lower': 670,     'upper': 900,      'desc': 'Entre 670 € y 900 €',      'base': 718.95},
    {'lower': 900,     'upper': 1125.90,  'desc': 'Entre 900 € y 1.125,90 €', 'base': 849.67},
    {'lower': 1125.90, 'upper': 1300,     'desc': 'Entre 1.125,90 € y 1.300 €','base': 950.98},
    {'lower': 1300,    'upper': 1500,     'desc': 'Entre 1.300 € y 1.500 €',  'base': 960.78},
    {'lower': 1500,    'upper': 1700,     'desc': 'Entre 1.500 € y 1.700 €',  'base': 960.78},
    {'lower': 1700,    'upper': 1850,     'desc': 'Entre 1.700 € y 1.850 €',  'base': 1143.79},
    {'lower': 1850,    'upper': 2030,     'desc': 'Entre 1.850 € y 2.030 €',  'base': 1209.15},
    {'lower': 2030,    'upper': 2330,     'desc': 'Entre 2.030 € y 2.330 €',  'base': 1274.51}, # Adjusted range based on next
    {'lower': 2330,    'upper': 2760,     'desc': 'Entre 2.330 € y 2.760 €',  'base': 1356.21},
    {'lower': 2760,    'upper': 3190,     'desc': 'Entre 2.760 € y 3.190 €',  'base': 1437.91},
    {'lower': 3190,    'upper': 3620,     'desc': 'Entre 3.190 € y 3.620 €',  'base': 1519.61},
    {'lower': 3620,    'upper': 4050,     'desc': 'Entre 3.620 € y 4.050 €',  'base': 1601.31},
    {'lower': 4050,    'upper': float('inf'), 'desc': 'Más de 4.050 €',       'base': 1601.31} # Assumed last base applies
]

# --- Define Fixed Monthly Expenses (Placeholder - Update with your actuals) ---
# Expenses should be in EUR
FIXED_MONTHLY_EXPENSES = {
    'chatgpt': 24.20,
    'icloud': 9.99,
    'autonomos': 230.00,
    'other': 100.00 # Catch-all for other fixed costs
}
TOTAL_FIXED_MONTHLY_EXPENSES = sum(FIXED_MONTHLY_EXPENSES.values())
# --- End Fixed Monthly Expenses ---

# --- Define Constants and Brackets (Ideally move to config/helpers) ---
AUTONOMO_CONTRIBUTION_RATE = 0.314
MONTHLY_FIXED_EXPENSES = 250 # Or get from config/db if dynamic
# Define brackets for the relevant year (e.g., 2024 - update as needed)
# Example structure - Make sure this matches the one in financials route
BRACKETS_2024 = {
     1: {'lower': -float('inf'), 'upper': 670, 'base': 950.98},
     2: {'lower': 670, 'upper': 900, 'base': 960.78},
     3: {'lower': 900, 'upper': 1166.70, 'base': 960.78}, # Example: Same base for Tramo 3 Reducido
     4: {'lower': 1166.70, 'upper': 1300, 'base': 1013.07},
     5: {'lower': 1300, 'upper': 1500, 'base': 1029.41},
     6: {'lower': 1500, 'upper': 1700, 'base': 1045.75},
     7: {'lower': 1700, 'upper': 1850, 'base': 1078.43},
     8: {'lower': 1850, 'upper': 2030, 'base': 1111.11},
     9: {'lower': 2030, 'upper': 2330, 'base': 1143.79},
    10: {'lower': 2330, 'upper': 2760, 'base': 1176.47},
    11: {'lower': 2760, 'upper': 3190, 'base': 1241.83},
    12: {'lower': 3190, 'upper': 3620, 'base': 1307.19},
    13: {'lower': 3620, 'upper': 4050, 'base': 1372.55},
    14: {'lower': 4050, 'upper': 6000, 'base': 1454.25},
    15: {'lower': 6000, 'upper': float('inf'), 'base': 1732.03}
}
# --- End Constants and Brackets ---

# Helper function to find the correct bracket
def find_bracket(net_revenue, brackets):
    for bracket in brackets:
        # Check if revenue is within the lower (inclusive) and upper (exclusive) bounds
        if net_revenue >= bracket['lower'] and net_revenue < bracket['upper']:
            return bracket
    # If revenue is exactly the lower bound of the highest bracket or more
    # Use >= for the last bracket's lower bound check
    if net_revenue >= brackets[-1]['lower']:
         return brackets[-1]
    # Should not happen if 0 is the lowest bound, but return None as fallback
    return None

def get_relative_date_string(target_date):
    today = date.today()
    tomorrow = today + timedelta(days=1)
    days_diff = (target_date - today).days

    if days_diff == 0:
        return "Today"
    elif days_diff == 1:
        return "Tomorrow"
    elif 1 < days_diff <= 7:
        # Return the day name (e.g., "Monday", "Tuesday")
        return day_name[target_date.weekday()]
    else:
        # For dates further out, return the standard date format
        return target_date.strftime("%Y-%m-%d")

@main.route('/')
@login_required
@physio_required # <<< ADD DECORATOR
def index():
    user_id_for_utils = None
    if current_user.is_authenticated and current_user.role != 'patient':
        user_id_for_utils = current_user.id

    # Run utility functions only if user is physio/admin and ID is available
    if user_id_for_utils:
        mark_past_treatments_as_completed(user_id=user_id_for_utils)
        mark_inactive_patients(user_id=user_id_for_utils)

    total_patients = Patient.query.filter_by(user_id=current_user.id).count() if current_user.is_authenticated and current_user.role != 'patient' else 0
    active_patients = Patient.query.filter_by(user_id=current_user.id, status='Active').count() if current_user.is_authenticated and current_user.role != 'patient' else 0
    today = datetime.utcnow().date() 
    week_end = today + timedelta(days=6 - today.weekday()) 
    month_end = today.replace(day=monthrange(today.year, today.month)[1])

    # Initialize subscription variables to avoid UnboundLocalError if user is not authenticated or has no sub
    current_plan_name = "N/A"
    current_subscription_status = "N/A"
    current_subscription_ends_at = None
    
    # Patient usage details
    current_patients_count = 0
    patient_plan_limit = None
    if current_user.is_authenticated:
        current_patients_count, patient_plan_limit = current_user.patient_usage_details

    # --- Correctly calculate Today's Appointments --- 
    # Convert today to a datetime object for the start of the day in UTC
    today_start_utc = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC)
    # Convert today to a datetime object for the end of the day in UTC
    today_end_utc = datetime.combine(today, datetime.max.time()).replace(tzinfo=UTC)

    todays_appointments_query = Treatment.query.join(Patient).filter(
        Patient.user_id == current_user.id,
        Treatment.status == 'Scheduled',
        Treatment.created_at >= today_start_utc,
        Treatment.created_at <= today_end_utc
    )
    today_appointments_count = todays_appointments_query.count()

    # --- Calculate Pending Review Count (e.g., Unmatched Calendly Bookings) ---
    pending_review_count = 0
    if current_user.is_admin:
        pending_review_count = UnmatchedCalendlyBooking.query.filter_by(status='Pending').count()
    elif current_user.role == 'physio':
        if current_user.calendly_api_token and current_user.calendly_user_uri:
            pending_review_count = UnmatchedCalendlyBooking.query.filter_by(
                status='Pending',
                user_id=current_user.id
            ).count()
    # Add other conditions for pending review if necessary, e.g. Patient status

    # --- Upcoming Appointments (Next 7 days, for current user only) --- 
    upcoming_appointments_query = Treatment.query.join(Patient).filter(
        Patient.user_id == current_user.id,
        Treatment.status == 'Scheduled',
        Treatment.created_at >= today,
        Treatment.created_at < week_end
    ).order_by(Treatment.created_at).limit(5).all()

    # Process upcoming appointments to add relative date string and LOCAL time
    upcoming_appointments_processed = []
    for apt in upcoming_appointments_query:
        # Make the UTC time timezone-aware
        utc_time = apt.created_at.replace(tzinfo=UTC)
        # Convert to local time
        local_time = utc_time.astimezone(LOCAL_TZ)
        
        apt_date = local_time.date() # Use local date for relative string
        relative_date = get_relative_date_string(apt_date)
        apt_time_str = local_time.strftime("%H:%M") # Format local time
        patient_name = apt.patient.name if apt.patient else "Unknown Patient"
        
        upcoming_appointments_processed.append({
            'treatment': apt, 
            'relative_date': relative_date,
            'time': apt_time_str, # Use the formatted local time string
            'patient_name': patient_name
        })

    # Get recent treatments
    recent_treatments = Treatment.query.filter(
        Treatment.patient_id == current_user.id,
        Treatment.created_at < today,
        Treatment.status == 'Scheduled'
    ).order_by(Treatment.created_at.desc()).limit(5).all()

    # --- Subscription Status --- 
    if current_user.is_authenticated:
        sub = current_user.current_subscription
        if sub:
            if sub.plan:
                current_plan_name = sub.plan.name
            current_subscription_status = sub.status.replace('_', ' ').title() # e.g., 'Past Due'
            
            if sub.status == 'trialing' and sub.trial_ends_at:
                current_subscription_ends_at = sub.trial_ends_at
            elif sub.current_period_ends_at:
                current_subscription_ends_at = sub.current_period_ends_at
    # --- End Subscription Status ---

    return render_template('index.html',
                           total_patients=total_patients,
                           active_patients=active_patients,
                           today_appointments=today_appointments_count, # Use the calculated count
                           upcoming_appointments=upcoming_appointments_processed, 
                           recent_treatments=recent_treatments,
                           today=today, 
                           week_end=week_end,
                           month_end=month_end,
                           # Subscription info
                           current_plan_name=current_plan_name,
                           current_subscription_status=current_subscription_status,
                           current_subscription_ends_at=current_subscription_ends_at,
                           current_patients_count=current_patients_count, 
                           patient_plan_limit=patient_plan_limit,
                           pending_review_count=pending_review_count, # Pass pending review count
                           # Data for weekly appointments chart
                           # weekly_appointment_labels=weekly_appointment_labels, # Removed
                           # weekly_appointment_counts=weekly_appointment_counts, # Removed
                           )

@main.route('/api/treatment/<int:id>')
@login_required # Assuming API endpoints also need login
# Decide if API endpoints need role check - for now, assume yes if it modifies/reveals sensitive data
def get_treatment_details(id):
    treatment = Treatment.query.get_or_404(id)
    # Add access check: Only physio or the correct patient
    if current_user.role == 'patient' and current_user.patient_id != treatment.patient_id:
        return jsonify({'error': 'Forbidden'}), 403
    try:
        # --- Fix Indentation Start --- Removed extra comment line
        # Get trigger points for this treatment
        trigger_points = [{
            'x': point.location_x,
            'y': point.location_y,
            'type': point.type,
            'muscle': point.muscle,
            'intensity': point.intensity,
            'symptoms': point.symptoms,
            'referral': point.referral_pattern
        } for point in treatment.trigger_points]

        # Return all fields that might be needed by the frontend
        return jsonify({
            'id': treatment.id,
            'date': treatment.created_at.isoformat() if treatment.created_at else None,
            'description': treatment.treatment_type,
            'progress_notes': treatment.notes,
            'pain_level': treatment.pain_level,
            'movement_restriction': treatment.movement_restriction,
            'evaluation_data': treatment.evaluation_data,
            'trigger_points': trigger_points,
            'treatment_type': treatment.treatment_type,
            'provider': treatment.provider,
            'notes': treatment.notes,
            'assessment': treatment.assessment,
            'status': treatment.status,
            'body_chart_url': treatment.body_chart_url,
            'patient_id': treatment.patient_id,
            'patient_name': treatment.patient.name if treatment.patient else None
        })
        # --- Fix Indentation End --- Removed extra comment line
    except Exception as e: # Added except block
        print(f"Error getting treatment details: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve treatment details',
            'message': str(e)
        }), 500

@main.route('/api/treatment/<int:id>', methods=['DELETE'])
@login_required
@physio_required # Physio/admin only
def delete_treatment(id):
    try:
        treatment = Treatment.query.get_or_404(id)
        
        # First delete associated trigger points
        TriggerPoint.query.filter_by(treatment_id=id).delete()
        
        # Then delete the treatment
        db.session.delete(treatment)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Treatment deleted successfully'})
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        print(f"Database error: {str(e)}")  # For debugging
        return jsonify({'success': False, 'message': 'Database error occurred'}), 500
    except Exception as e:
        db.session.rollback()
        print(f"General error: {str(e)}")  # For debugging
        return jsonify({'success': False, 'message': 'An error occurred'}), 500

@main.route('/patient/<int:id>')
@login_required
def patient_detail(id):
    patient = Patient.query.get_or_404(id)
    
    # --- Access Control ---
    if not current_user.is_admin:  # Admins have full access
        if current_user.role == 'physio':
            # Physios can only access patients linked to their user_id
            if patient.user_id != current_user.id:
                flash('You do not have permission to view this patient\'s details.', 'danger') # Indented
                return redirect(url_for('main.patients_list')) # Indented
        elif current_user.role == 'patient':
            # Patients should view their details via their own dashboard.
            if not current_user.patient_record or current_user.patient_record.id != patient.id:
                flash('Please access your details via the patient dashboard.', 'info')
                return redirect(url_for('main.patient_dashboard'))
            # If it IS their record, and they somehow land here, it's okay or redirect.
            # For consistency, you might redirect them to their dashboard anyway.
            # else:
            #    return redirect(url_for('main.patient_dashboard'))

        else: # Other non-admin, non-physio roles
            flash('Access Denied.', 'danger')
            return redirect(url_for('main.index'))
    # --- End Access Control ---

    print(f"Treatments for patient {patient.name}:")
    treatments = Treatment.query.filter_by(patient_id=id).options(joinedload(Treatment.patient)).all()
    for treatment in treatments:
        print(f"Treatment Created At: {treatment.created_at}")

    today = datetime.now()
    
    past_treatments = Treatment.query.filter(
        Treatment.patient_id == id,
        Treatment.created_at < today,
        Treatment.status == 'Scheduled'
    ).all()

    if past_treatments:
        count = 0
        for treatment_item in past_treatments: # Renamed to avoid conflict
            treatment_item.status = 'Completed'
            count += 1
        if count > 0:
            try:
                db.session.commit()
                flash(f"{count} past treatment(s) automatically marked as completed.", "info")
            except Exception as e:
                db.session.rollback()
                print(f"Error auto-completing treatments for patient {id}: {e}")
                flash("Error updating past treatment statuses.", "danger")

    treatment_count = db.session.query(Treatment.id).filter(Treatment.patient_id == id).count()
    is_first_visit = treatment_count == 0
    print(f"Is first visit for patient {id}? {is_first_visit}")

    return render_template('patient_detail.html', 
                           patient=patient, 
                           today=today, 
                           treatments=treatments,
                          is_first_visit=is_first_visit)

@main.route('/patient/<int:patient_id>/treatment', methods=['POST'])
@login_required
@physio_required # <<< ADD DECORATOR
def add_treatment(patient_id):
    print("--- add_treatment route START ---")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # Get form data
    treatment_type = request.form.get('treatment_type')
    print(f"DEBUG: treatment_type = {treatment_type}")
    assessment = request.form.get('assessment')
    print(f"DEBUG: assessment = {assessment}")
    notes = request.form.get('notes')
    print(f"DEBUG: notes = {notes}")
    status = request.form.get('status')
    print(f"DEBUG: status = {status}")
    provider = request.form.get('provider')
    print(f"DEBUG: provider = {provider}")
    
    # --- Location Logic ---
    location = request.form.get('location')
    print(f"DEBUG: location from form = {location}")
    sync_with_calendly = request.form.get('sync_with_calendly') == 'true' # Check if Calendly sync enabled
    
    if not location or location.strip() == "": # If no location explicitly provided
        if sync_with_calendly:
            location = 'Home Visit' # Default for Calendly sync
            print(f"DEBUG: Defaulting location to 'Home Visit' due to Calendly sync for patient {patient_id}")
        else:
            location = 'CostaSpine Clinic' # Default for manual entry without explicit selection
            print(f"DEBUG: Defaulting location to 'CostaSpine Clinic' for patient {patient_id}")
    else:
         print(f"DEBUG: Using provided location: {location} for patient {patient_id}")
    # --- End Location Logic ---
    
    # Get optional fields
    pain_level_str = request.form.get('pain_level')
    print(f"DEBUG: pain_level from form = {pain_level_str}")
    if pain_level_str and pain_level_str.strip() != '':  # Only convert to int if a value was provided
        try:
            pain_level = int(pain_level_str)
        except ValueError:
            print(f"WARNING: Could not convert pain_level '{pain_level_str}' to int. Setting to None.")
            pain_level = None
    else:
        pain_level = None  # Set to None if not provided
    print(f"DEBUG: Parsed pain_level = {pain_level}")
    
    movement_restriction = request.form.get('movement_restriction')
    print(f"DEBUG: movement_restriction = {movement_restriction}")
    body_chart_url = request.form.get('body_chart_url')
    print(f"DEBUG: body_chart_url = {body_chart_url}")
    
    # Get new financial fields (these might be set by the location logic or form)
    visit_type = request.form.get('visit_type') 
    print(f"DEBUG: visit_type from form = {visit_type}")
    fee_str = request.form.get('fee_charged')
    print(f"DEBUG: fee_charged from form = {fee_str}")
    try:
        fee_charged = float(fee_str) if fee_str and fee_str.strip() != '' else None
    except ValueError:
        print(f"WARNING: Could not convert fee_charged '{fee_str}' to float. Setting to None.")
        fee_charged = None
    print(f"DEBUG: Parsed fee_charged = {fee_charged}")
    payment_method = request.form.get('payment_method')
    print(f"DEBUG: payment_method from form = {payment_method}")
    
    # Get trigger points / evaluation data
    evaluation_data = None
    trigger_data_str = request.form.get('trigger_points_data') or request.form.get('evaluation_data')
    print(f"DEBUG: trigger_points_data/evaluation_data from form = {trigger_data_str}")
    if trigger_data_str:
        try:
            evaluation_data = json.loads(trigger_data_str)
            print(f"DEBUG: Parsed evaluation_data: {evaluation_data}")
        except json.JSONDecodeError as json_err:
            print(f"ERROR: Invalid JSON for trigger points data for patient {patient_id}: {json_err}")
            flash('Error decoding trigger points data.', 'danger')
            evaluation_data = None 
    
    # Get date field if provided
    date_str = request.form.get('date')
    print(f"DEBUG: Raw date from form: '{date_str}'")
    created_at = None
    if date_str:
        try:
             created_at = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
             print(f"DEBUG: Parsed date as datetime: {created_at}")
        except ValueError as date_err:
            print(f"ERROR: Could not parse date string '{date_str}': {date_err}")
            # Correctly format the f-string for the flash message
            flash(f"Invalid date format ('{date_str}'). Using current date/time.", 'warning') 
            created_at = datetime.now()
    else:
        print("DEBUG: No date string provided, using current datetime.")
        created_at = datetime.now()
    
    # --- Validation --- 
    if not treatment_type:
        print("ERROR: treatment_type is missing or empty!")
        if is_ajax:
            return jsonify({'success': False, 'message': 'Treatment Type is required.'}), 400
        flash('Treatment Type is required.', 'danger')
        return redirect(url_for('main.patient_detail', id=patient_id))
        
    # Create new treatment object (before adding to session)
    print("DEBUG: Creating Treatment object...")
    treatment = Treatment(
        patient_id=patient_id,
        treatment_type=treatment_type,
        assessment=assessment,
        notes=notes,
        status=status,
        provider=provider,
        pain_level=pain_level,  
        movement_restriction=movement_restriction,
        body_chart_url=body_chart_url,
        created_at=created_at,
        evaluation_data=evaluation_data,  
        location=location,               
        visit_type=visit_type,            
        fee_charged=fee_charged,          
        payment_method=payment_method     
    )
    print(f"DEBUG: Treatment object created: {treatment.__dict__}") # Log object state
    
    # --- Add and commit treatment and trigger points within a try/except block ---
    try:
        print("DEBUG: Adding treatment to session...")
        db.session.add(treatment)
        print("DEBUG: Committing treatment...")
        db.session.commit() # First commit for the treatment itself
        print(f"DEBUG: Treatment committed successfully. ID: {treatment.id}")
        
        # If we have trigger points data, create those records too after the treatment is saved
        if evaluation_data and isinstance(evaluation_data, list):
            print(f"DEBUG: Processing {len(evaluation_data)} trigger points...")
            for point_data in evaluation_data:
                if isinstance(point_data, dict):
                    # Add more robust default handling and type checking
                    intensity_val = None
                    intensity_str = point_data.get('intensity')
                    if intensity_str and str(intensity_str).strip() != '':
                        try: 
                           intensity_val = int(intensity_str)
                        except (ValueError, TypeError):
                           print(f"WARNING: Could not convert intensity '{intensity_str}' to int for point {point_data.get('id')}")
                    
                    location_x_val = 0.0
                    location_x_str = point_data.get('x')
                    if location_x_str is not None:
                       try:
                           location_x_val = float(location_x_str)
                       except (ValueError, TypeError):
                           print(f"WARNING: Could not convert location_x '{location_x_str}' to float for point {point_data.get('id')}")
                    
                    location_y_val = 0.0
                    location_y_str = point_data.get('y')
                    if location_y_str is not None:
                        try:
                            location_y_val = float(location_y_str)
                        except (ValueError, TypeError):
                            print(f"WARNING: Could not convert location_y '{location_y_str}' to float for point {point_data.get('id')}")

                    trigger_point = TriggerPoint(
                        treatment_id=treatment.id,
                        location_x=location_x_val,
                        location_y=location_y_val,
                        type=point_data.get('type', 'unknown'),
                        muscle=point_data.get('muscle', ''),
                        intensity=intensity_val,
                        symptoms=point_data.get('symptoms', ''),
                        referral_pattern=point_data.get('referral', '')
                    )
                    print(f"DEBUG: Adding TriggerPoint object: {trigger_point.__dict__}")
                    db.session.add(trigger_point)
            print("DEBUG: Committing trigger points...")
            db.session.commit() # Second commit for trigger points
            print("DEBUG: Trigger points committed.")
        
        success_message = 'Treatment added successfully'
        if is_ajax:
            # For AJAX, also return some event data if possible, or just success
            new_event_data = {
                'id': treatment.id,
                'title': f"{treatment.patient.name} - {treatment.treatment_type if treatment.treatment_type else 'Appointment'}",
                'start': treatment.created_at.isoformat(),
                'end': (treatment.created_at + timedelta(hours=1)).isoformat(), # Match calendar logic
                 # Add color logic similar to get_calendar_appointments if desired
            }
            return jsonify({'success': True, 'message': success_message, 'event': new_event_data})
        flash(success_message, 'success')
        print("--- add_treatment route END (Success) ---")
        return redirect(url_for('main.patient_detail', id=patient_id))

    except Exception as e:
        db.session.rollback() # Rollback any potential partial changes
        tb_str = traceback.format_exc()
        current_app.logger.error(f"!!! ERROR in add_treatment for patient {patient_id} !!!\n{tb_str}")
        error_message = 'An internal error occurred while adding the treatment. Please try again later.'
        if is_ajax:
            return jsonify({'success': False, 'message': error_message, 'details': str(e)}), 500
        flash(error_message, 'danger') # Generic message
        print("--- add_treatment route END (Error) ---") # Keep print here for server log clarity on error path
        return redirect(url_for('main.patient_detail', id=patient_id))

@main.route('/patient/<int:patient_id>/recurring/new', methods=['GET', 'POST'])
@login_required
@physio_required # <<< ADD DECORATOR
def new_recurring_appointment(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    if request.method == 'POST':
        try:
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            time_str = request.form.get('time_of_day')
            
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
            time_of_day = datetime.strptime(time_str, '%H:%M').time() if time_str else None
            
            recurrence_type = request.form.get('recurrence_type')
            treatment_type = request.form.get('treatment_type')
            notes = request.form.get('notes')
            location = request.form.get('location')
            provider = request.form.get('provider')
            fee_str = request.form.get('fee_charged')
            fee_charged = float(fee_str) if fee_str else None
            payment_method = request.form.get('payment_method')
            is_active = request.form.get('is_active') == 'on' # Checkbox value

            if not all([start_date, time_of_day, recurrence_type, treatment_type]):
                flash('Start Date, Time, Recurrence Type, and Treatment Type are required.', 'danger')
            else:
                new_rule = RecurringAppointment(
                    patient_id=patient_id,
                    start_date=start_date,
                    end_date=end_date,
                    recurrence_type=recurrence_type,
                    time_of_day=time_of_day,
                    treatment_type=treatment_type,
                    notes=notes,
                    location=location,
                    provider=provider,
                    fee_charged=fee_charged,
                    payment_method=payment_method,
                    is_active=is_active
                )
                db.session.add(new_rule)
                db.session.commit()
                flash('Recurring appointment rule created successfully!', 'success')
                return redirect(url_for('main.patient_detail', id=patient_id))

        except ValueError:
             flash('Invalid date or time format. Please use YYYY-MM-DD and HH:MM.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating recurring rule: {e}', 'danger')
            print(f"Error creating recurring rule: {e}")
            
    # GET request
    return render_template('new_recurring_appointment.html', patient=patient)

@main.route('/recurring/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@physio_required # <<< ADD DECORATOR
def edit_recurring_appointment(id):
    rule = RecurringAppointment.query.get_or_404(id)
    patient = Patient.query.get_or_404(rule.patient_id)

    # Ensure the current user owns this patient/rule
    if patient.user_id != current_user.id:
        flash('You are not authorized to edit this recurring appointment.', 'danger')
        return redirect(url_for('main.patients_list'))

    if request.method == 'POST':
        # ... (POST logic remains the same)
        rule.start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date_str = request.form.get('end_date')
        rule.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
        rule.recurrence_type = request.form['recurrence_type']
        rule.time_of_day = datetime.strptime(request.form['time_of_day'], '%H:%M').time()
        rule.treatment_type = request.form['treatment_type']
        rule.notes = request.form.get('notes')
        rule.location = request.form.get('location')
        rule.payment_method = request.form.get('payment_method')
        rule.provider = request.form.get('provider')
        fee_charged_str = request.form.get('fee_charged')
        rule.fee_charged = float(fee_charged_str) if fee_charged_str else None
        rule.is_active = 'is_active' in request.form

        try:
            db.session.commit()
            flash('Recurring appointment rule updated successfully!', 'success')
            return redirect(url_for('main.patient_detail', id=patient.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating rule: {str(e)}', 'danger')
    
    # For GET request, generate CSRF token and pass it to the template
    csrf_token_value = generate_csrf()
    return render_template('edit_recurring_appointment.html', 
                           rule=rule, 
                           patient=patient, 
                           csrf_token_value=csrf_token_value)

@main.route('/recurring/<int:id>/delete', methods=['POST'])
@login_required
@physio_required # <<< ADD DECORATOR
def delete_recurring_appointment(id):
    rule = RecurringAppointment.query.get_or_404(id)
    patient_id = rule.patient_id
    try:
        db.session.delete(rule)
        db.session.commit()
        flash('Recurring appointment rule deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting recurring rule: {e}', 'danger')
        print(f"Error deleting recurring rule {id}: {e}")
        
    return redirect(url_for('main.patient_detail', id=patient_id))

@main.route('/appointments')
@login_required
@physio_required # <<< ADD DECORATOR
def appointments():
    start_date = request.args.get('start_date',
                               datetime.now().date().isoformat())
    end_date = request.args.get('end_date',
                             (datetime.now() + timedelta(days=30)).date().isoformat())

    # Filter appointments based on user role
    appointments_query = Treatment.query.filter(
        Treatment.created_at.between(start_date, end_date)
    )
    if not current_user.is_admin and current_user.role == 'physio':
        appointments_query = appointments_query.join(Patient).filter(Patient.user_id == current_user.id)
    
    appointments = appointments_query.order_by(Treatment.created_at).all()

    # Filter patients based on user role for the modal
    if current_user.is_admin:
        patients = Patient.query.filter_by(status='Active').order_by(Patient.name).all()
    elif current_user.role == 'physio':
        patients = Patient.query.filter_by(user_id=current_user.id, status='Active').order_by(Patient.name).all()
    else: # Should not happen due to @physio_required, but as a fallback
        patients = []

    # Use the same logic as in review_calendly_bookings route
    calendly_configured_for_user = False # Default for non-admins
    if current_user.is_admin:
        calendly_configured_for_user = True # Admins are implicitly configured to see all
    elif current_user.role == 'physio':
        if current_user.calendly_api_token and current_user.calendly_user_uri:
            calendly_configured_for_user = True

    return render_template('appointments.html',
                           appointments=appointments,
                           patients=patients,
                           start_date=start_date,
                           end_date=end_date,
                           calendly_sync_enabled=calendly_configured_for_user)

@main.route('/api/appointments')
@login_required
@physio_required # <<< ADD DECORATOR
def get_appointments():
    # 1. Get date range from request args (ensure they are dates)
    try:
        start_str = request.args.get('start', datetime.now().date().isoformat())
        # Default end is 90 days from start for a reasonable lookahead
        start_date_obj = date.fromisoformat(start_str.split('T')[0])
        end_str = request.args.get('end', (start_date_obj + timedelta(days=90)).isoformat())
        
        # Parse start/end into date objects for comparison. FullCalendar sends dates or datetime strings.
        start_date = date.fromisoformat(start_str.split('T')[0])
        end_date = date.fromisoformat(end_str.split('T')[0])
    except ValueError:
        # Handle invalid date format
        return jsonify({"error": "Invalid date format for start or end parameter"}), 400
        
    events = []
    existing_treatments_datetimes = set() # Store (patient_id, datetime) tuples

    # 2. Fetch existing treatments within the broader range (datetime comparison)
    # Need to convert start/end dates to datetimes for comparison with Treatment.created_at
    start_dt = datetime.combine(start_date, time.min)
    # Make end_dt exclusive for the query to match FullCalendar's range typical behavior
    # Or ensure we include the full end_date by using time.max if necessary
    end_dt = datetime.combine(end_date, time.min) # Fetch treatments strictly *before* the end date's start

    treatments = Treatment.query.filter(
        Treatment.created_at >= start_dt,
        Treatment.created_at < end_dt # Use < end_dt
    ).options(joinedload(Treatment.patient)).all() # Eager load patient

    for apt in treatments:
        # Use patient name safely
        patient_name = apt.patient.name if apt.patient else "Unknown Patient"
        # Determine color based on status
        color = '#2980b9' # Default/Scheduled Blue
        if apt.status == 'Completed':
            color = '#27ae60' # Green
        elif apt.status == 'Cancelled':
             color = '#e74c3c' # Red
        elif apt.status == 'In Progress':
             color = '#f1c40f' # Yellow

        events.append({
        'id': apt.id,
            'title': f"{patient_name} - {apt.treatment_type}",
        'start': apt.created_at.isoformat(),
            'end': (apt.created_at + timedelta(minutes=45)).isoformat(), # Assuming 45 min duration
            'color': color,
            'textColor': 'white',
            'extendedProps': {
                'status': apt.status,
                'isRecurring': False,
                'treatmentId': apt.id, # Add real ID here
                'patientId': apt.patient_id
            }
        })
        # Store the combination of patient_id and datetime to check against recurring ones
        existing_treatments_datetimes.add((apt.patient_id, apt.created_at))

    # 3. Fetch active recurring appointments
    active_rules = RecurringAppointment.query.filter_by(is_active=True).options(joinedload(RecurringAppointment.patient)).all()

    # 4. Calculate future occurrences within the requested window [start_date, end_date)
    for rule in active_rules:
        # Ensure patient relationship is loaded
        if not rule.patient:
            print(f"Warning: Recurring rule ID {rule.id} missing patient relationship. Skipping.")
            continue
            
        patient_name = rule.patient.name

        # Start checking from the rule's start or window start, whichever is later
        current_check_date = max(start_date, rule.start_date) 
        # Determine the effective end date for this rule's calculation
        effective_rule_end = rule.end_date or end_date # Use rule's end if defined, else window's end

        while current_check_date < end_date and current_check_date <= effective_rule_end: 
            is_valid_occurrence = False
            
            # Check based on recurrence type
            if rule.recurrence_type == 'weekly':
                # Occurs if the current day's weekday matches the rule's start_date weekday
                if current_check_date.weekday() == rule.start_date.weekday():
                    is_valid_occurrence = True
            elif rule.recurrence_type == 'daily-mon-fri':
                # Occurs if the current day is Monday (0) to Friday (4)
                if current_check_date.weekday() < 5: 
                    is_valid_occurrence = True
            # Potential future expansion: Add monthly, specific days, etc.

            if is_valid_occurrence:
                # Combine date with the rule's time_of_day to get the exact datetime
                # Handle case where time_of_day might be None (though model requires it)
                if rule.time_of_day:
                    occurrence_datetime = datetime.combine(current_check_date, rule.time_of_day)
                    
                    # Check if a real treatment already exists for this patient/datetime
                    if (rule.patient_id, occurrence_datetime) not in existing_treatments_datetimes:
                        # Create event object for this potential/recurring occurrence
                        events.append({
                            'id': f'recurring_{rule.id}_{current_check_date.isoformat()}', # Unique ID for potential events
                            'title': f"{patient_name} - {rule.treatment_type} (Recurring)",
                            'start': occurrence_datetime.isoformat(),
                            'end': (occurrence_datetime + timedelta(minutes=45)).isoformat(), # Assuming 45 min duration
                            'color': '#f39c12', # Orange for recurring potential
                            'textColor': 'white',
                            'display': 'block', # Ensures it's treated like a normal event visually
                            'extendedProps': {
                                'status': 'Recurring (Potential)',
                                'isRecurring': True,
                                'ruleId': rule.id,
                                'patientId': rule.patient_id
                            }
                            # Note: These events are not directly editable/deletable via standard event handlers
                            # unless specific JS logic is added to handle 'recurring_*' IDs
                        })
                else:
                     print(f"Warning: Rule {rule.id} has no time_of_day set for date {current_check_date}. Skipping occurrence.")


            # Move to the next day for the check loop
            current_check_date += timedelta(days=1)

    return jsonify(events)

@main.route('/appointments/update/<int:id>', methods=['POST'])
@login_required
@physio_required # <<< ADD DECORATOR
def update_appointment(id):
    treatment = Treatment.query.get_or_404(id)

    if request.form.get('action') == 'complete':
        treatment.status = 'Completed'
    elif request.form.get('action') == 'cancel':
        treatment.status = 'Cancelled'
    else:
        treatment.created_at = datetime.strptime(
            request.form['appointment_datetime'],
            '%Y-%m-%dT%H:%M'
        )
        treatment.treatment_type = request.form['appointment_type']
        treatment.notes = request.form['notes']

    db.session.commit()
    return jsonify({'success': True})

@main.route('/reports')
@login_required
@physio_required # <<< ADD DECORATOR
def reports():
    try:
        total_patients = Patient.query.count()
        active_patients = Patient.query.filter_by(status='Active').count()

        monthly_treatments_query = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.count(Treatment.id).label('count')
        ).group_by(func.strftime('%Y-%m', Treatment.created_at)) \
            .order_by(func.strftime('%Y-%m', Treatment.created_at).desc()) \
            .limit(12).all()

        monthly_treatments = [(row[0], row[1]) for row in monthly_treatments_query]

        conditions_query = db.session.query(
            Patient.diagnosis,
            func.count(Patient.id).label('count')
        ).group_by(Patient.diagnosis).all()

        conditions = [(row[0], row[1]) for row in conditions_query]

        completed_treatments = Treatment.query.filter_by(status='Completed').count()
        total_treatments = Treatment.query.count()
        completion_rate = (completed_treatments / total_treatments * 100) if total_treatments > 0 else 0

        avg_treatments = db.session.query(
            func.count(Treatment.id) / func.count(func.distinct(Treatment.patient_id))
        ).scalar() or 0

        recent_activity = (
            Treatment.query
            .join(Patient)
            .order_by(Treatment.created_at.desc())
            .limit(10)
            .all()
        )

        return render_template('reports.html',
                               total_patients=total_patients,
                               active_patients=active_patients,
                               monthly_treatments=monthly_treatments,
                               conditions=conditions,
                               completion_rate=completion_rate,
                               avg_treatments=float(avg_treatments),
                               recent_activity=recent_activity)
    except Exception as e:
        print("Error in reports:", e)  # For debugging
        flash('Error generating report. Please try again.', 'danger')
        return redirect(url_for('main.index'))

@main.route('/api/reports/treatments-by-month')
@login_required
@physio_required # <<< ADD DECORATOR
def treatments_by_month():
    treatments = db.session.query(
        func.strftime('%Y-%m', Treatment.created_at).label('month'),
        func.count(Treatment.id).label('count')
    ).group_by(func.strftime('%Y-%m', Treatment.created_at)) \
        .order_by(func.strftime('%Y-%m', Treatment.created_at)) \
        .all()

    return jsonify({
        'labels': [t[0] for t in treatments],
        'data': [t[1] for t in treatments]
    })

@main.route('/patient/<int:id>/treatments')
@login_required
def patient_treatments(id):
    patient = Patient.query.get_or_404(id)
    
    # --- Access Control ---
    if not current_user.is_admin: # Admins have full access
        if current_user.role == 'physio':
            if patient.user_id != current_user.id:
                flash('You do not have permission to view these treatments.', 'danger')
                return redirect(url_for('main.patients_list'))
        elif current_user.role == 'patient':
            if not current_user.patient_record or current_user.patient_record.id != patient.id:
                flash('You do not have permission to view these treatments.', 'danger')
                return redirect(url_for('main.patient_dashboard')) # Indent this line
            # If it IS their record, they are allowed through to see treatments.
            # No 'else' needed here for this specific condition if access is granted.
        else: # Other roles (this 'else' correctly pairs with 'if current_user.role == 'physio':')
            flash('Access Denied.', 'danger')
            return redirect(url_for('main.index'))
    # --- End Access Control ---
    
    treatments = Treatment.query.filter_by(patient_id=id).order_by(Treatment.created_at.desc()).all()
    return render_template('treatments.html', patient=patient, treatments=treatments)

@main.route('/search')
@login_required
# @physio_required # <<< Consider if patients should search? Restrict for now
def search():
    # --- Add Access Control --- 
    if current_user.role == 'patient':
        flash('Search function not available for patient accounts.', 'warning')
        return jsonify([]) # Return empty list for patients
    # --- End Access Control ---
    query = request.args.get('q', '')
    patients = Patient.query.filter(
        or_(
            Patient.name.ilike(f'%{query}%'),
            Patient.diagnosis.ilike(f'%{query}%')
        )
    ).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'diagnosis': p.diagnosis,
        'status': p.status
    } for p in patients])

@main.route('/patients')
@login_required
@physio_required # <<< ADD DECORATOR
def patients_list():
    search = request.args.get('search', '')
    status_filter = request.args.get('status', 'all')

    # Get patient usage details
    current_patients_count = 0
    patient_plan_limit = None
    if current_user.is_authenticated: # Should always be true due to @login_required
        current_patients_count, patient_plan_limit = current_user.patient_usage_details

    # query = Patient.query # Old query
    # Query only patients belonging to the current user
    query = Patient.query.filter_by(user_id=current_user.id)

    if search:
        query = query.filter(
            or_(
                Patient.name.ilike(f'%{search}%'),
                Patient.diagnosis.ilike(f'%{search}%'),
                Patient.notes.ilike(f'%{search}%')
            )
        )

    if status_filter != 'all':
        query = query.filter(Patient.status == status_filter)

    patients = query.order_by(Patient.name).all()

    return render_template('patients_list.html',
                           patients=patients,
                           search=search,
                           status_filter=status_filter,
                           current_patients_count=current_patients_count,
                           patient_plan_limit=patient_plan_limit
                           )

@main.route('/patient/<int:patient_id>/reports_list', methods=['GET'])
@login_required
def patient_reports_list(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    # Basic access control (similar to patient_detail)
    if not current_user.is_admin and current_user.role == 'physio' and patient.user_id != current_user.id:
        flash('You do not have permission to view these reports.', 'danger')
        return redirect(url_for('main.patients_list'))
    elif current_user.role == 'patient' and (not current_user.patient_record or current_user.patient_record.id != patient_id):
        flash('You do not have permission to view these reports.', 'danger')
        return redirect(url_for('main.patient_dashboard'))

    report_id = request.args.get('report_id', type=int)
    selected_report = None
    
    all_patient_reports = PatientReport.query.filter_by(patient_id=patient_id)\
                                       .order_by(PatientReport.generated_date.desc()).all()

    if report_id:
        selected_report = PatientReport.query.filter_by(id=report_id, patient_id=patient_id).first()
        if not selected_report:
            flash('Specified report not found for this patient.', 'warning')
            # Fallback to latest or just show list without a pre-selected one
            selected_report = all_patient_reports[0] if all_patient_reports else None 
    elif all_patient_reports:
        selected_report = all_patient_reports[0] # Default to the latest report
    
    return render_template('patient_report.html',
                           patient=patient,
                           report=selected_report, # The specific report to display (or latest)
                           all_reports=all_patient_reports) # All reports for the dropdown

@main.route('/calendly/review')
@login_required
@physio_required # <<< ADD DECORATOR
def review_calendly_bookings():
    unmatched_bookings_list = []
    calendly_configured_for_user = False # Default for non-admins

    if current_user.is_admin:
        unmatched_bookings_list = UnmatchedCalendlyBooking.query.filter_by(status='Pending').all()
        calendly_configured_for_user = True # Admins are implicitly configured to see all
    elif current_user.role == 'physio':
        if current_user.calendly_api_token and current_user.calendly_user_uri:
            calendly_configured_for_user = True
            unmatched_bookings_list = UnmatchedCalendlyBooking.query.filter_by(
                status='Pending',
                user_id=current_user.id
            ).all()
        # Else, unmatched_bookings_list remains empty and calendly_configured_for_user is False
    
    # --- DEBUGGING PRINT --- 
    print(f"--- DEBUG: /calendly/review route ---")
    print(f"User: {current_user.email}, Is Admin: {current_user.is_admin}, Role: {current_user.role}")
    print(f"Calendly Configured for this user context: {calendly_configured_for_user}")
    print(f"Count of UnmatchedBookings being passed to template: {len(unmatched_bookings_list)}")
    if unmatched_bookings_list:
        print(f"First item details (if any): ID: {unmatched_bookings_list[0].id}, Name: {unmatched_bookings_list[0].name}, UserID: {unmatched_bookings_list[0].user_id}")
    # --- END DEBUGGING PRINT ---
    
    return render_template('review_calendly_bookings.html', 
                           unmatched_bookings=unmatched_bookings_list,
                           calendly_configured_for_user=calendly_configured_for_user)

@main.route('/calendly/match_booking/<int:booking_id>', methods=['GET', 'POST'])
@login_required
@physio_required
def match_booking_to_patient(booking_id):
    booking = UnmatchedCalendlyBooking.query.get_or_404(booking_id)

    # Ensure the booking belongs to the current user if not admin
    if not current_user.is_admin and booking.user_id != current_user.id:
        flash('You are not authorized to access this booking.', 'danger')
        return redirect(url_for('main.review_calendly_bookings'))

    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        if not patient_id:
            flash('No patient selected.', 'warning')
            return redirect(url_for('main.match_booking_to_patient', booking_id=booking_id))

        patient = Patient.query.get_or_404(patient_id)
        # Ensure selected patient belongs to the current user if not admin
        if not current_user.is_admin and patient.user_id != current_user.id:
            flash('Invalid patient selection.', 'danger')
            return redirect(url_for('main.match_booking_to_patient', booking_id=booking_id))

        try:
            booking.matched_patient_id = patient.id
            booking.status = 'Matched'
            
            # Create a corresponding treatment
            new_treatment = Treatment(
                patient_id=patient.id,
                treatment_type=booking.event_type or "Calendly Booking", 
                notes=f"Booked via Calendly. Invitee: {booking.name} ({booking.email}). Matched by {current_user.username}.",
                status='Scheduled', # Or determine based on booking.start_time
                provider=current_user.username, # Or map from booking if available
                created_at=booking.start_time or datetime.utcnow(), # Use booking start_time
                calendly_invitee_uri=booking.calendly_invitee_id # Assuming you store the URI or a unique ID from Calendly
            )
            db.session.add(new_treatment)
            db.session.commit()
            flash(f'Booking for {booking.name} successfully matched to patient {patient.name}. A new treatment has been scheduled.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error matching booking: {str(e)}', 'danger')
        return redirect(url_for('main.review_calendly_bookings'))

    # GET request:
    if current_user.is_admin:
        patients = Patient.query.order_by(Patient.name).all()
    else:
        patients = Patient.query.filter_by(user_id=current_user.id).order_by(Patient.name).all()
    
    return render_template('match_calendly_booking.html',
                           booking=booking,
                           patients=patients,
                           title="Match Calendly Booking")

@main.route('/calendly/create_patient_from_booking/<int:booking_id>', methods=['POST']) # Should be POST only
@login_required
@physio_required
def create_patient_from_booking(booking_id):
    booking = UnmatchedCalendlyBooking.query.get_or_404(booking_id)

    # Ensure the booking belongs to the current user if not admin
    if not current_user.is_admin and booking.user_id != current_user.id:
        flash('You are not authorized to process this booking.', 'danger')
        return redirect(url_for('main.review_calendly_bookings'))

    try:
        # Check if a patient with this email already exists for this physio (or globally for admin)
        existing_patient_query = Patient.query.filter_by(email=booking.email)
        if not current_user.is_admin:
            existing_patient_query = existing_patient_query.filter_by(user_id=current_user.id)
        existing_patient = existing_patient_query.first()

        if existing_patient:
            # If patient exists, match to this patient instead of creating a new one
            booking.matched_patient_id = existing_patient.id
            booking.status = 'Matched'
            patient_to_link = existing_patient
            action_message = f'Booking for {booking.name} matched to existing patient {patient_to_link.name}.'
        else:
            # Create new patient
            new_patient = Patient(
                name=booking.name,
                email=booking.email,
                user_id=current_user.id, # Associate with the current physio
                # Add other fields as necessary, e.g., phone from booking if available
                # phone=booking.phone (if you add a phone field to UnmatchedCalendlyBooking)
                status='Active' 
            )
            db.session.add(new_patient)
            db.session.flush() # To get new_patient.id for the treatment and booking update

            booking.matched_patient_id = new_patient.id
            booking.status = 'Matched'
            patient_to_link = new_patient
            action_message = f'New patient {patient_to_link.name} created from booking and booking matched.'

        # Create a corresponding treatment for the linked patient
        new_treatment = Treatment(
            patient_id=patient_to_link.id,
            treatment_type=booking.event_type or "Calendly Booking",
            notes=f"Booked via Calendly. Invitee: {booking.name} ({booking.email}). Auto-created/matched by {current_user.username}.",
            status='Scheduled', # Or determine based on booking.start_time
            provider=current_user.username, # Or map from booking if available
            created_at=booking.start_time or datetime.utcnow(), # Use booking start_time
            calendly_invitee_uri=booking.calendly_invitee_id # Store unique calendly ID
        )
        db.session.add(new_treatment)
        db.session.commit()
        flash(f'{action_message} A new treatment has been scheduled.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating patient from booking: {str(e)}', 'danger')
        current_app.logger.error(f"Error in create_patient_from_booking for booking_id {booking_id}: {e}")
        current_app.logger.error(traceback.format_exc())


    return redirect(url_for('main.review_calendly_bookings'))

@main.route('/treatment/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@physio_required # <<< ADD DECORATOR
def edit_treatment(id):
    treatment = Treatment.query.get_or_404(id)
    patient = treatment.patient
    # REMOVED form instantiation
    
    print(f"DEBUG: Raw treatment.evaluation_data for ID {id}: {treatment.evaluation_data!r}") 
    
    if request.method == 'POST':
        # --- POST request logic starts here ---
        # Update date field
        if request.form.get('date'):
            treatment.created_at = datetime.strptime(request.form['date'], '%Y-%m-%d')

        # Update treatment_type field
        if request.form.get('treatment_type'):
            treatment.treatment_type = request.form['treatment_type']
        # For backward compatibility - map description to treatment_type if provided
        elif request.form.get('description'):
            treatment.treatment_type = request.form['description']
        
        # Update notes field
        if request.form.get('notes'):
            treatment.notes = request.form['notes']
        # For backward compatibility - map progress_notes to notes if provided
        elif request.form.get('progress_notes'):
            treatment.notes = request.form['progress_notes']
            
        treatment.status = request.form['status']
        
        # Handle created_at (Seems redundant if date is handled above? Check logic if needed)
        # if request.form.get('created_at'):
        #     treatment.created_at = datetime.strptime(
        #         request.form['created_at'], '%Y-%m-%d'
        #     )
            
        # Handle pain level if provided
        if request.form.get('pain_level'):
            treatment.pain_level = int(request.form['pain_level']) # Consider adding try-except for int conversion
            
        # Handle movement restriction if provided
        if request.form.get('movement_restriction'):
            treatment.movement_restriction = request.form['movement_restriction']
        
        # Handle new financial fields
        treatment.location = request.form.get('location')
        treatment.visit_type = request.form.get('visit_type')
        fee_str = request.form.get('fee_charged')
        try:
             treatment.fee_charged = float(fee_str) if fee_str else None
        except (ValueError, TypeError):
             flash(f'Invalid fee format: {fee_str}', 'warning')
             treatment.fee_charged = None # Or keep old value?
        treatment.payment_method = request.form.get('payment_method')
        
        # Handle trigger points data
        if request.form.get('trigger_points_data'):
            trigger_data_string = request.form.get('trigger_points_data')
            print(f"DEBUG: Received trigger_points_data: {trigger_data_string}") 
            try:
                new_evaluation_data = json.loads(trigger_data_string)
                if not isinstance(new_evaluation_data, list):
                     raise ValueError("Evaluation data must be a list.")
                
                treatment.evaluation_data = new_evaluation_data
                
                # Update or create trigger points in the database
                TriggerPoint.query.filter_by(treatment_id=treatment.id).delete()
                for point_data in treatment.evaluation_data:
                    # Add more robust validation/conversion here if needed
                    trigger_point = TriggerPoint(
                        treatment_id=treatment.id,
                        location_x=float(point_data['x']), # Add try-except
                        location_y=float(point_data['y']), # Add try-except
                        type=point_data.get('type', 'unknown'),
                        muscle=point_data.get('muscle', ''),
                        intensity=int(point_data['intensity']) if point_data.get('intensity') else None, # Add try-except
                        symptoms=point_data.get('symptoms', ''),
                        referral_pattern=point_data.get('referral', '')
                    )
                    db.session.add(trigger_point)
                
            except (json.JSONDecodeError, ValueError, TypeError) as e: # Catch potential errors
                print(f"ERROR: Processing trigger points for treatment {id}: {e}")
                print(f"ERROR_STRING: {trigger_data_string}")
                flash('Error processing trigger point data. Please check format.', 'danger')
                db.session.rollback() # Rollback changes made so far in the POST
                # --- Explicitly generate CSRF token for re-render ---
                csrf_token_value_on_post_error = generate_csrf()
                # ---------------------------------------------------
                # Re-render form with original data (or potentially partially updated data before rollback)
                original_treatment_data = Treatment.query.get(id) # Re-fetch original state
                has_past_treatments_on_error = db.session.query(Treatment.id).filter(Treatment.patient_id == patient.id, Treatment.id != id).first() is not None
                # REMOVE passing form or csrf_token_value
                return render_template('edit_treatment.html',
                                      treatment={ # Use original data if possible
                                          'id': original_treatment_data.id,
                                          'created_at': original_treatment_data.created_at,
                                          'description': original_treatment_data.treatment_type,
                                          'progress_notes': original_treatment_data.notes,
                                          'status': original_treatment_data.status,
                                          'pain_level': original_treatment_data.pain_level,
                                          'movement_restriction': original_treatment_data.movement_restriction,
                                          'location': original_treatment_data.location,
                                          'visit_type': original_treatment_data.visit_type,
                                          'fee_charged': original_treatment_data.fee_charged,
                                          'payment_method': original_treatment_data.payment_method,
                                          'evaluation_data': original_treatment_data.evaluation_data,
                                          'trigger_points': original_treatment_data.trigger_points,
                                          'body_chart_url': original_treatment_data.body_chart_url
                                      },
                                      patient=patient,
                                      has_past_treatments=has_past_treatments_on_error)

        # Final commit for all changes (if no trigger point errors occurred)
        try:
            db.session.commit()
            flash(f'Treatment session on {treatment.created_at.strftime("%Y-%m-%d")} updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error saving treatment changes. Please try again.', 'danger')
            print(f"Error committing changes for treatment {id}: {e}")
            # --- Explicitly generate CSRF token for re-render ---
            csrf_token_value_on_commit_error = generate_csrf()
            # ---------------------------------------------------
            # Re-render the edit form if commit fails - pass current (potentially unsaved) data
            has_past_treatments_on_error_commit = db.session.query(Treatment.id).filter(Treatment.patient_id == patient.id, Treatment.id != id).first() is not None
            # REMOVE passing form or csrf_token_value
            return render_template('edit_treatment.html',
                                  treatment={ 
                                      'id': treatment.id,
                                      'created_at': treatment.created_at,
                                      'description': treatment.treatment_type,
                                      'progress_notes': treatment.notes,
                                      'status': treatment.status,
                                      'pain_level': treatment.pain_level,
                                      'movement_restriction': treatment.movement_restriction,
                                      'location': treatment.location,
                                      'visit_type': treatment.visit_type,
                                      'fee_charged': treatment.fee_charged,
                                      'payment_method': treatment.payment_method,
                                      'evaluation_data': treatment.evaluation_data, # Show potentially invalid data that failed save
                                      'trigger_points': treatment.trigger_points,
                                      'body_chart_url': treatment.body_chart_url
                                  },
                                  patient=patient,
                                  has_past_treatments=has_past_treatments_on_error_commit)

        return redirect(url_for('main.patient_detail', id=patient.id))
    
    # --- GET Request Logic --- (This runs when the page is first loaded)
    # Check if patient has other treatments besides this one
    has_past_treatments = db.session.query(Treatment.id).filter(
        Treatment.patient_id == patient.id, 
        Treatment.id != id
    ).first() is not None
    print(f"DEBUG: Patient {patient.id} has past treatments (excluding current {id}): {has_past_treatments}")

    valid_evaluation_data = [] 
    if treatment.evaluation_data:
        if isinstance(treatment.evaluation_data, (list, dict)):
            valid_evaluation_data = treatment.evaluation_data
        elif isinstance(treatment.evaluation_data, str):
            try:
                parsed_data = json.loads(treatment.evaluation_data)
                if isinstance(parsed_data, list):
                    valid_evaluation_data = parsed_data
                else:
                    print(f"Warning: Parsed evaluation_data for treatment {id} is not a list.")
            except json.JSONDecodeError:
                print(f"Warning: evaluation_data for treatment {id} is invalid JSON.")
        else:
            print(f"Warning: evaluation_data for treatment {id} has unexpected type.")

    template_context = {
        'id': treatment.id,
        'created_at': treatment.created_at,
        'description': treatment.treatment_type,
        'progress_notes': treatment.notes,
        'status': treatment.status,
        'pain_level': treatment.pain_level,
        'movement_restriction': treatment.movement_restriction,
        'location': treatment.location,
        'visit_type': treatment.visit_type,
        'fee_charged': treatment.fee_charged,
        'payment_method': treatment.payment_method,
        'evaluation_data': valid_evaluation_data, 
        'trigger_points': treatment.trigger_points, 
        'body_chart_url': treatment.body_chart_url
    }

    # --- Explicitly generate CSRF token for GET request ---
    csrf_token_value_on_get = generate_csrf()
    # -----------------------------------------------------

    return render_template('edit_treatment.html', 
                          treatment=template_context, 
                          patient=patient,
                          has_past_treatments=has_past_treatments)

@main.route('/treatment/<int:id>/view')
@login_required
def view_treatment(id):
    treatment = Treatment.query.get_or_404(id)
    patient = treatment.patient
    
    # --- Access Control --- 
    if not current_user.is_admin: # Admins have full access
        if current_user.role == 'physio':
            if patient.user_id != current_user.id:
                flash('You do not have permission to view this treatment.', 'danger')
                return redirect(url_for('main.patients_list'))
        elif current_user.role == 'patient':
            if not current_user.patient_record or current_user.patient_record.id != patient.id:
                # VVVVV THESE LINES MUST BE INDENTED LIKE THIS VVVVV
                flash('You do not have permission to view this treatment.', 'danger')
                return redirect(url_for('main.patient_dashboard'))
            # If it IS their record, they are allowed through.
        else: # Other roles
            # VVVVV THESE LINES MUST BE INDENTED LIKE THIS VVVVV
            flash('Access Denied.', 'danger')
            return redirect(url_for('main.index')) # This was also mis-indented in the snippet
    # --- End Access Control ---
    
    print(f"Viewing treatment {id}: Type={treatment.treatment_type}, Notes={treatment.notes}, Status={treatment.status}")
    
    mapped_treatment = {
        'id': treatment.id,
        'created_at': treatment.created_at,
        'description': treatment.treatment_type,
        'progress_notes': treatment.notes,
        'treatment_type': treatment.treatment_type,
        'notes': treatment.notes,
        'status': treatment.status,
        'patient_id': treatment.patient_id,
        'pain_level': treatment.pain_level,
        'movement_restriction': treatment.movement_restriction,
        'assessment': treatment.assessment,
        'provider': treatment.provider,
        'body_chart_url': treatment.body_chart_url,
        'trigger_points': treatment.trigger_points,
        'evaluation_data': treatment.evaluation_data
    }
    
    return render_template('view_treatment.html', treatment=mapped_treatment, patient=patient)

@main.route('/test/edit-treatment/<int:id>')
@login_required
@physio_required # <<< ADD DECORATOR
def test_edit_treatment(id):
    treatment = Treatment.query.get_or_404(id)
    return f"""
    <html>
    <body>
        <h1>Test Edit Treatment</h1>
        <p>Treatment ID: {treatment.id}</p>
        <p>Date: {treatment.created_at}</p>
        <p>Description: {treatment.treatment_type}</p>
        <p>Patient: {treatment.patient.name}</p>
        <a href="/treatment/{treatment.id}/edit">Go to Edit Page</a>
    </body>
    </html>
    """

@main.route('/patient/<int:id>/edit-treatments')
@login_required
@physio_required # <<< ADD DECORATOR
def patient_edit_treatments(id):
    patient = Patient.query.get_or_404(id)
    treatments = Treatment.query.filter_by(patient_id=id).order_by(Treatment.created_at.desc()).all()
    return render_template('edit_treatments_list.html', patient=patient, treatments=treatments)

@main.route('/patient/<int:patient_id>/new_treatment_page', methods=['GET'])
@login_required
@physio_required # <<< ADD DECORATOR
def new_treatment_page(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    now = datetime.now() # Get current datetime
    # Check if patient has any treatments at all
    has_past_treatments = db.session.query(Treatment.id).filter(
        Treatment.patient_id == patient_id
    ).first() is not None
    print(f"DEBUG: Patient {patient_id} has past treatments (for new page): {has_past_treatments}")
    
    # --- Explicitly generate CSRF token ---
    csrf_token_value = generate_csrf()
    # -------------------------------------
    
    # Pass patient, now, the flag, AND THE EXPLICIT TOKEN to the template
    return render_template('new_treatment_page.html', 
                          patient=patient, 
                          now=now,
                          has_past_treatments=has_past_treatments,
                          csrf_token_value=csrf_token_value) # Pass explicit token

@main.route('/admin/fix-calendly-dates')
@login_required # Assuming only logged-in users (likely physio/admin) should access
@physio_required # <<< ADD DECORATOR
def fix_calendly_dates():
    # Get all treatments with "Booked via Calendly" in the notes
    calendly_treatments = Treatment.query.filter(
        Treatment.notes.like('%Booked via Calendly%')
    ).all()
    
    updated_count = 0
    for treatment in calendly_treatments:
        if treatment.created_at:
            updated_count += 1
    
    db.session.commit()
    
    return f"""
    <html>
    <body>
        <h1>Calendly Dates Fixed</h1>
        <p>Updated {updated_count} treatment records.</p>
        <a href="/">Return to Dashboard</a>
    </body>
    </html>
    """

# --- Helper function for DeepSeek ---
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions" # Or your specific endpoint

def generate_deepseek_report(analytics_data):
    if not DEEPSEEK_API_KEY:
        return "DeepSeek API key not configured. Please set the DEEPSEEK_API_KEY environment variable."

    # --- Prepare the prompt data (more structured) ---
    try:
        total_patients = analytics_data.get('total_patients', 'N/A')
        active_patients = analytics_data.get('active_patients', 'N/A')
        total_treatments = analytics_data.get('total_treatments', 'N/A')
        avg_treatments = analytics_data.get('avg_treatments', 'N/A')
        avg_revenue = analytics_data.get('avg_monthly_revenue', 0)

        # Common Diagnoses (list of dicts)
        common_diagnoses = analytics_data.get('common_diagnoses', [])
        common_diagnoses_str = ", ".join([f"{d.get('diagnosis','?')} ({d.get('count',0)})" for d in common_diagnoses]) or "N/A"

        # Revenue by Visit Type (list of dicts)
        revenue_by_type = analytics_data.get('revenue_by_visit_type', [])
        revenue_by_type_str = ", ".join([f"{r.get('type','?')}: £{r.get('revenue', 0):,.2f}" for r in revenue_by_type]) or "N/A"

        # Age Distribution (dict)
        age_dist = analytics_data.get('age_distribution', {})
        age_dist_str = ", ".join([f"{bracket}: {count}" for bracket, count in age_dist.items()]) or "N/A"
        
        # Treatment Trends (list of dicts)
        treatment_trends = analytics_data.get('treatments_by_month', [])
        treatment_trends_str = "See monthly data below." if treatment_trends else "N/A"
        treatment_months_detail = "\n".join([f"  - {t.get('month','?')}: {t.get('count',0)} treatments" for t in treatment_trends]) if treatment_trends else ""

        # Patient Trends (list of dicts)
        patient_trends = analytics_data.get('patients_by_month', [])
        patient_trends_str = "See monthly data below." if patient_trends else "N/A"
        patient_months_detail = "\n".join([f"  - {p.get('month','?')}: {p.get('count',0)} new patients" for p in patient_trends]) if patient_trends else ""
        
    except Exception as e:
        print(f"Error formatting data for DeepSeek prompt: {e}")
        return "Error: Could not format analytics data for AI report generation."

    # --- Updated, Detailed Prompt ---
    prompt = f"""
    Generate a comprehensive practice analytics report for a physiotherapist using the following data. 
    Focus on providing actionable insights and identifying interesting patterns.

    **Practice Overview:**
    - Total Patients: {total_patients}
    - Active Patients: {active_patients}
    - Total Treatments Logged: {total_treatments}
    - Average Treatments per Patient: {avg_treatments}
    - Average Monthly Revenue: £{avg_revenue:,.2f}

    **Patient Demographics:**
    - Age Distribution: {age_dist_str}

    **Clinical Insights:**
    - Most Common Diagnoses (Top 10): {common_diagnoses_str}
    - Revenue by Visit Type: {revenue_by_type_str}

    **Trends:**
    - Treatment Volume Trend: {treatment_trends_str}
    {treatment_months_detail}
    
    - New Patient Acquisition Trend: {patient_trends_str}
    {patient_months_detail}

    **Analysis Request:**
    Based *only* on the data provided above, please generate a report covering:
    1.  **Executive Summary:** A brief overview of the practice's current state.
    2.  **Key Findings:** Highlight the most significant data points (e.g., top 2-3 diagnoses, dominant age group, busiest months).
    3.  **Treatment Analysis:** Discuss the frequency and trends related to different treatment types (if discernible from revenue/diagnoses data).
    4.  **Potential Patterns & Correlations:** Explicitly look for and mention any surprising or interesting patterns, correlations, or outliers. Examples:
        *   Is there a peak season for certain injuries/diagnoses?
        *   Are specific diagnoses strongly correlated with particular age groups?
        *   Are there any unusual revenue patterns by treatment type or month?
        *   Are new patient numbers correlated with treatment volume?
    5.  **Actionable Insights/Curious Takeaways:** Offer 1-2 concrete, data-driven insights or thought-provoking observations the physiotherapist could consider for practice improvement or further investigation.

    Keep the tone professional, analytical, and insightful. Structure the report clearly with headings for each section (Executive Summary, Key Findings, Treatment Analysis, Patterns & Correlations, Actionable Insights).
    """

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "deepseek-chat", # Or the specific model you want to use
        "messages": [
            {"role": "system", "content": "You are an expert AI assistant analyzing physiotherapy practice data to provide insightful reports."}, # Updated system message
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 800, # Increased max_tokens for a more detailed report
        "temperature": 0.6, # Slightly increased temperature for potentially more nuanced insights
    }

    try:
        # ... (keep the existing API call and error handling logic) ...
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=45) # Increased timeout
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        
        result = response.json()
        
        # Check if the expected response structure is present
        if 'choices' in result and len(result['choices']) > 0 and 'message' in result['choices'][0] and 'content' in result['choices'][0]['message']:
            report_content = result['choices'][0]['message']['content'].strip()
            # Simple post-processing: Replace potential markdown list markers if needed
            report_content = report_content.replace("- ", "\n- ") # Ensure lists start on new lines
            return report_content
        else:
            # Log unexpected structure for debugging
            print(f"Unexpected DeepSeek API response structure: {result}")
            return "Error: Could not parse the report from the AI response."

    except requests.exceptions.RequestException as e:
        # Log the error for debugging
        print(f"Error calling DeepSeek API: {e}")
        # Provide a user-friendly error message
        if isinstance(e, requests.exceptions.Timeout):
            return "Error: The request to the AI service timed out."
        elif isinstance(e, requests.exceptions.HTTPError):
             return f"Error: Received an error from the AI service (Status Code: {response.status_code}). Please check your API key and endpoint."
        else:
            return "Error: Could not connect to the AI service to generate the report."
    except json.JSONDecodeError:
        # Log the raw response if it's not valid JSON
        print(f"Failed to decode JSON response from DeepSeek API: {response.text}")
        return "Error: Received an invalid response from the AI service."
    except Exception as e: # Catch any other unexpected errors
        print(f"An unexpected error occurred during AI report generation: {e}")
        return "An unexpected error occurred while generating the AI report."

# Helper function to calculate age
def calculate_age(born):
    if not born:
        return None
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

@main.route('/analytics')
@login_required
@physio_required
def analytics():
    # Fetch latest AI report from the database
    if current_user.is_admin:
        latest_report = PracticeReport.query.filter_by(user_id=None).order_by(PracticeReport.generated_at.desc()).first()
        # Optional: If you also want admins to see their own user-specific reports as a fallback or primary view, adjust logic here.
        # For now, admin sees global (user_id=None) reports.
    else:
        latest_report = PracticeReport.query.filter_by(user_id=current_user.id).order_by(PracticeReport.generated_at.desc()).first()

    ai_report_html = "" # Initialize as empty string
    ai_report_generated_at = None
    if latest_report:
        ai_report_generated_at = latest_report.generated_at
        try:
            ai_report_html = markdown.markdown(latest_report.content, extensions=['fenced_code', 'tables'])
        except Exception as e:
            print(f"Error converting practice report markdown: {e}")
            ai_report_html = "<p class=\"text-danger\">Error rendering report content.</p>"
    else:
        ai_report_html = "<p class=\"text-info\">No practice report generated yet. Click 'Generate New Report' to create one.</p>"

    # --- Data JUST for Summary Cards (Filtered for non-admins) ---
    if current_user.is_admin:
        total_patients = Patient.query.count()
        active_patients = Patient.query.filter(Patient.status == 'Active').count()
        total_treatments = Treatment.query.count()
        monthly_revenue_query = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.sum(Treatment.fee_charged).label('monthly_total')
        ).filter(Treatment.fee_charged.isnot(None)).group_by('month')
        costaspine_revenue_base_query = db.session.query(
            func.sum(Treatment.fee_charged).label('total_costaspine_revenue')
        ).filter(
            Treatment.location == 'CostaSpine Clinic',
            Treatment.fee_charged.isnot(None)
        )
        autonomo_base_query = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.strftime('%Y', Treatment.created_at).label('year'),
            func.sum(Treatment.fee_charged).label('monthly_total_revenue'),
            func.sum(
                case((Treatment.location == 'CostaSpine Clinic', Treatment.fee_charged), else_=0)
            ).label('monthly_costaspine_revenue')
        ).filter(
            Treatment.fee_charged.isnot(None),
            Treatment.created_at.isnot(None)
        ).group_by('year', 'month').order_by('year', 'month')
    else:
        total_patients = Patient.query.filter_by(user_id=current_user.id).count()
        active_patients = Patient.query.filter_by(user_id=current_user.id, status='Active').count()
        total_treatments = Treatment.query.join(Patient).filter(Patient.user_id == current_user.id).count()
        monthly_revenue_query = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.sum(Treatment.fee_charged).label('monthly_total')
        ).join(Patient).filter(Patient.user_id == current_user.id, Treatment.fee_charged.isnot(None)).group_by('month')
        costaspine_revenue_base_query = db.session.query(
            func.sum(Treatment.fee_charged).label('total_costaspine_revenue')
        ).join(Patient).filter(
            Patient.user_id == current_user.id,
            Treatment.location == 'CostaSpine Clinic',
            Treatment.fee_charged.isnot(None)
        )
        autonomo_base_query = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.strftime('%Y', Treatment.created_at).label('year'),
            func.sum(Treatment.fee_charged).label('monthly_total_revenue'),
            func.sum(
                case((Treatment.location == 'CostaSpine Clinic', Treatment.fee_charged), else_=0)
            ).label('monthly_costaspine_revenue')
        ).join(Patient).filter(
            Patient.user_id == current_user.id,
            Treatment.fee_charged.isnot(None),
            Treatment.created_at.isnot(None)
        ).group_by('year', 'month').order_by('year', 'month')

    inactive_patients = total_patients - active_patients
    avg_treatments = round(total_treatments / total_patients, 1) if total_patients else 0
    
    monthly_revenue = monthly_revenue_query.all()
    total_revenue = sum(m.monthly_total for m in monthly_revenue if m.monthly_total)
    num_months = len(monthly_revenue)
    avg_monthly_revenue = total_revenue / num_months if num_months else 0
    
    costaspine_revenue_data = costaspine_revenue_base_query.scalar() or 0
    # costaspine_service_fee_total = costaspine_revenue_data * 0.30 # This variable is not used in template
    
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    start_of_week_dt = datetime.combine(start_of_week, datetime.min.time())
    end_of_week_dt = datetime.combine(end_of_week, datetime.max.time())
    
    costaspine_revenue_weekly_query = costaspine_revenue_base_query.filter(
        Treatment.created_at >= start_of_week_dt,
        Treatment.created_at <= end_of_week_dt
    )
    costaspine_revenue_weekly_data = costaspine_revenue_weekly_query.scalar() or 0
    costaspine_service_fee_weekly = costaspine_revenue_weekly_data * 0.30
    
    total_autonomo_contribution = 0
    monthly_data_autonomo = autonomo_base_query.all()

    for month_data in monthly_data_autonomo:
        # ... autonomo calculation loop ...
        current_brackets = TAX_BRACKETS_2025 
        revenue = month_data.monthly_total_revenue or 0
        cs_revenue = month_data.monthly_costaspine_revenue or 0
        costaspine_fee = cs_revenue * 0.30
        net_revenue_before_contrib = revenue - costaspine_fee - MONTHLY_FIXED_EXPENSES 
        bracket_info = find_bracket(net_revenue_before_contrib, current_brackets)
        min_base = bracket_info.get('base', 0) if bracket_info else 0
        monthly_contribution = min_base * AUTONOMO_CONTRIBUTION_RATE if min_base > 0 else 0
        total_autonomo_contribution += monthly_contribution
    # --- End Summary Card Data Fetching ---
    
    # Render Template (Only pass data needed for cards and AI report)
    return render_template('analytics.html',
                          # Pass summary card data
                          total_patients=total_patients,
                          active_patients=active_patients,
                          inactive_patients=inactive_patients,
                          total_treatments=total_treatments,
                          avg_treatments=avg_treatments,
                          avg_monthly_revenue=avg_monthly_revenue,
                          costaspine_revenue=costaspine_revenue_data, # Keep total revenue for modal/other use
                          costaspine_service_fee_weekly=costaspine_service_fee_weekly, # Pass weekly fee for the card
                          total_autonomo_contribution=total_autonomo_contribution,
                          # Chart data is no longer passed here
                          ai_report_html=ai_report_html, 
                          ai_report_generated_at=ai_report_generated_at
                          )

@main.route('/api/analytics/costaspine-fee-data')
@login_required
@physio_required # <<< ADD DECORATOR
def get_costaspine_fee_data():
    """Returns the date, fee, and patient name for all treatments at CostaSpine Clinic with a fee."""
    try:
        fee_data = db.session.query(
            Treatment.created_at,
            Treatment.fee_charged,
            Patient.name
        ).join(Patient, Treatment.patient_id == Patient.id) \
         .filter(
            Treatment.location == 'CostaSpine Clinic',
            Treatment.fee_charged.isnot(None)
        ).order_by(Treatment.created_at).all()
        
        # Convert to a list of dictionaries with ISO formatted dates
        results = [
            {'date': record.created_at.isoformat(), 
             'fee': float(record.fee_charged),
             'patient_name': record.name} # Add patient name
            for record in fee_data
        ]
        
        return jsonify(results)
    except Exception as e:
        print(f"Error fetching CostaSpine fee data: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500

@main.route('/admin/update-treatments')
@login_required # Assuming only logged-in users should access
@physio_required # <<< ADD DECORATOR
def update_treatments_demo():
    """Update all treatments with sample data for demonstration purposes."""
    treatments = Treatment.query.all()
    
    treatment_types = [
        "Initial Assessment", "Follow-up", "Deep Tissue Massage", 
        "Sports Massage", "Trigger Point Therapy", "Myofascial Release",
        "Joint Mobilization", "Rehabilitation Exercise", "Manual Therapy"
    ]
    
    assessment_templates = [
        "Patient presents with {location} pain rated {pain}/10. Range of motion is {rom}.",
        "Follow-up assessment shows {improvement} improvement since last session. Pain now at {pain}/10.",
        "Initial evaluation indicates {condition} with associated {symptoms}.",
        "Patient reports {change} in symptoms since previous treatment."
    ]
    
    notes_templates = [
        "Treatment focused on {area}. Patient responded well to {technique}.",
        "Used {technique} on {area}. Patient reported immediate relief.",
        "Performed {technique}. Recommended home exercises for {area}.",
        "Patient showed {response} to treatment. Advised to continue with {advice}."
    ]
    
    locations = ["lower back", "neck", "shoulder", "knee", "hip", "ankle", "wrist"]
    rom_states = ["limited", "moderately restricted", "slightly restricted", "normal"]
    improvements = ["significant", "moderate", "slight", "minimal"]
    conditions = ["muscle strain", "joint dysfunction", "postural imbalance", "overuse syndrome"]
    symptoms = ["pain", "stiffness", "reduced mobility", "muscle spasms", "nerve impingement"]
    changes = ["improvement", "slight improvement", "no change", "worsening"]
    areas = ["cervical spine", "lumbar region", "thoracic spine", "shoulder complex", "hip complex", "knee joint"]
    techniques = ["soft tissue manipulation", "joint mobilization", "trigger point release", "myofascial release", "proprioceptive neuromuscular facilitation"]
    responses = ["positive response", "good improvement", "moderate improvement", "limited improvement"]
    advice = ["stretching routine", "strengthening exercises", "postural correction", "activity modification", "rest and ice"]
    
    providers = ["Dr. Smith", "Dr. Johnson", "Dr. Williams", "Dr. Brown", "Dr. Jones"]
    
    import random
    from datetime import timedelta
    
    count = 0
    for treatment in treatments:
        # Only update treatments with default/empty values
        if treatment.treatment_type == "Unknown" or not treatment.treatment_type:
            treatment.treatment_type = random.choice(treatment_types)
            count += 1
        
        # Generate assessment if empty
        if not treatment.assessment:
            template = random.choice(assessment_templates)
            pain = treatment.pain_level if treatment.pain_level else random.randint(1, 9)
            
            if "{location}" in template:
                template = template.replace("{location}", random.choice(locations))
            if "{pain}" in template:
                template = template.replace("{pain}", str(pain))
            if "{rom}" in template:
                template = template.replace("{rom}", random.choice(rom_states))
            if "{improvement}" in template:
                template = template.replace("{improvement}", random.choice(improvements))
            if "{condition}" in template:
                template = template.replace("{condition}", random.choice(conditions))
            if "{symptoms}" in template:
                template = template.replace("{symptoms}", random.choice(symptoms))
            if "{change}" in template:
                template = template.replace("{change}", random.choice(changes))
                
            treatment.assessment = template
        
        # Generate notes if empty
        if not treatment.notes:
            template = random.choice(notes_templates)
            
            if "{area}" in template:
                template = template.replace("{area}", random.choice(areas))
            if "{technique}" in template:
                template = template.replace("{technique}", random.choice(techniques))
            if "{response}" in template:
                template = template.replace("{response}", random.choice(responses))
            if "{advice}" in template:
                template = template.replace("{advice}", random.choice(advice))
                
            treatment.notes = template
        
        # Add provider if empty
        if not treatment.provider or treatment.provider == "none":
            treatment.provider = random.choice(providers)
        
        # Make sure pain level is set
        if not treatment.pain_level:
            treatment.pain_level = random.randint(1, 9)
        
        # Set movement restriction if empty
        if not treatment.movement_restriction or treatment.movement_restriction == "none":
            treatment.movement_restriction = random.choice(rom_states)
    
    db.session.commit()
    
    return f"""
    <html>
    <body>
        <h1>Treatment Data Updated</h1>
        <p>Updated {count} treatment records with meaningful data.</p>
        <a href="/">Return to Dashboard</a>
    </body>
    </html>
    """

@main.route('/report/<int:report_id>/pdf')
@login_required
def download_report_pdf(report_id):
    report = PatientReport.query.get_or_404(report_id)
    patient = report.patient
    
    # --- Access Control ---
    if not current_user.is_admin: # Admins have full access
        if current_user.role == 'physio':
            if patient.user_id != current_user.id:
                flash('You do not have permission to download this report.', 'danger')
                return redirect(url_for('main.patients_list'))
        elif current_user.role == 'patient':
            if not current_user.patient_record or current_user.patient_record.id != patient.id:
                flash('You do not have permission to download this report.', 'danger')
                return redirect(url_for('main.patient_dashboard'))
        else: # Other roles
            flash('Access Denied.', 'danger')
            return redirect(url_for('main.index'))
    # --- End Access Control ---

    report_html_content = ""
    try:
        report_html_content = markdown.markdown(report.content)
    except Exception as e:
        print(f"Error converting markdown for report {report_id}: {e}")
        flash('Error generating PDF: Could not parse report content.', 'danger')
        return redirect(url_for('main.patient_report', id=patient.id, report_id=report.id))

    css_content = ""
    try:
        css_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'report.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
    except FileNotFoundError:
        print("Warning: report.css not found. PDF will have basic styling.")
    except Exception as e:
        print(f"Error reading report.css: {e}")

    full_html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Report: {patient.name}</title>
        <style>
            {css_content}
        </style>
    </head>
    <body>
        <div class="report-content">
            {report_html_content}
        </div>
    </body>
    </html>
    """

    pdf_file = BytesIO()
    try:
        pisa_status = pisa.CreatePDF(full_html_content, dest=pdf_file)
        if pisa_status.err:
            raise Exception(f"pisa error: {pisa_status.err}")
    except Exception as e:
        print(f"Error creating PDF for report {report_id}: {e}")
        flash('Error generating PDF. Please check report content or server logs.', 'danger')
        return redirect(url_for('main.patient_report', id=patient.id, report_id=report.id))

    pdf_file.seek(0)
    response = make_response(pdf_file.read())
    response.headers['Content-Type'] = 'application/pdf'
    filename = f"Report_{patient.name.replace(' ', '_')}_{report.generated_date.strftime('%Y%m%d')}.pdf"
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@main.route('/homework/<int:report_id>')
@login_required
def view_homework(report_id):
    report = PatientReport.query.get_or_404(report_id)
    # Permission check: Ensure the logged-in user (or patient) is allowed to see this report.
    # If current_user is the patient themselves (and report belongs to them):
    is_patient_self = False
    if current_user.role == 'patient' and current_user.patient_record and current_user.patient_record.id == report.patient_id:
        is_patient_self = True
    
    # If current_user is the clinician for this patient:
    is_clinician_of_patient = False
    if current_user.role == 'physio' and report.patient.user_id == current_user.id: # Assuming Patient.user_id links to clinician
        is_clinician_of_patient = True

    if not is_patient_self and not is_clinician_of_patient and not current_user.is_admin:
        flash('You do not have permission to view this report.', 'danger')
        # Redirect to a safe page, e.g., patient dashboard if patient, or main index if physio
        if current_user.role == 'patient':
            return redirect(url_for('main.patient_dashboard'))
        else:
            return redirect(url_for('main.index'))
            
    if report.report_type != 'Exercise Homework':
        flash('This report is not a homework assignment.', 'warning')
        # Decide where to redirect, perhaps back to patient detail or a report list
        return redirect(url_for('main.patient_detail', id=report.patient_id))

    return render_template('view_homework.html', report=report)

# --- Bulk Update Endpoint --- 
@main.route('/api/treatments/bulk-update', methods=['POST'])
@login_required
@physio_required # <<< ADD DECORATOR
def bulk_update_treatments():
    """Updates location or payment method for a list of treatment IDs.
       If location is set to 'CostaSpine Clinic', it also sets the fee
       (€80 for the patient's first ever treatment, €70 otherwise)."""
    data = request.get_json()
    
    treatment_ids = data.get('treatment_ids')
    field_to_update = data.get('field')
    new_value = data.get('value')
    
    if not all([treatment_ids, field_to_update, new_value]):
        return jsonify({'success': False, 'message': 'Missing required data (treatment_ids, field, value).'}), 400
        
    if field_to_update not in ['location', 'payment_method']:
        return jsonify({'success': False, 'message': 'Invalid field specified. Can only update "location" or "payment_method".'}), 400
        
    # Basic validation for known values (can be expanded)
    if field_to_update == 'location' and new_value not in ['CostaSpine Clinic', 'Home Visit']:
        return jsonify({'success': False, 'message': 'Invalid location value.'}), 400
    if field_to_update == 'payment_method' and new_value not in ['Cash', 'Card']:
         return jsonify({'success': False, 'message': 'Invalid payment_method value.'}), 400

    try:
        updated_count = 0
        earliest_treatment_id = None
        patient_id_for_check = None

        # --- Determine if auto-fee logic applies ---
        is_costaspine_auto_fee = (field_to_update == 'location' and new_value == 'CostaSpine Clinic')

        # --- Get patient ID and earliest treatment if auto-fee applies --- 
        if is_costaspine_auto_fee:
            # Find the patient ID from the first treatment ID in the list
            first_treatment_check = Treatment.query.options(db.joinedload(Treatment.patient)).get(treatment_ids[0])
            if not first_treatment_check:
                 return jsonify({'success': False, 'message': 'Invalid treatment ID found in list.'}), 400
            patient_id_for_check = first_treatment_check.patient_id
            
            # Find the earliest treatment for this specific patient
            earliest_patient_treatment = Treatment.query.filter_by(patient_id=patient_id_for_check)\
                                                 .order_by(Treatment.created_at.asc(), Treatment.id.asc())\
                                                 .first()
            earliest_treatment_id = earliest_patient_treatment.id if earliest_patient_treatment else None

        # --- Query and update selected treatments --- 
        treatments_to_update = Treatment.query.filter(Treatment.id.in_(treatment_ids)).all()
        
        for treatment in treatments_to_update:
            # Consistency check: Ensure all selected treatments belong to the same patient if auto-fee applies
            if patient_id_for_check is not None and treatment.patient_id != patient_id_for_check:
                 print(f"Warning: Skipping treatment {treatment.id} belonging to different patient during CostaSpine auto-fee update.")
                 continue

            # Apply updates
            if is_costaspine_auto_fee:
                treatment.location = new_value # 'CostaSpine Clinic'
                # Set fee based on whether it's the patient's absolute earliest treatment
                if earliest_treatment_id is not None and treatment.id == earliest_treatment_id:
                    treatment.fee_charged = 80.00
                    print(f"Setting fee to 80 for treatment {treatment.id} (earliest)")
                else:
                    treatment.fee_charged = 70.00
                    print(f"Setting fee to 70 for treatment {treatment.id}")
            else:
                # Standard update for other fields/values (Home Visit, Cash, Card)
                setattr(treatment, field_to_update, new_value)

            updated_count += 1

        # --- Commit and return --- 
        if updated_count > 0: 
            db.session.commit()
            return jsonify({'success': True, 'message': f'Successfully updated {updated_count} treatments.'})
        else:
             # Handle case where all treatments were skipped or list was empty
             return jsonify({'success': False, 'message': 'No valid treatments were updated.'}), 400 # Return 400 Bad Request

    except Exception as e:
        db.session.rollback()
        print(f"Error during bulk treatment update: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred during the update.'}), 500

# --- Financials Page Route --- 
@main.route('/financials')
@login_required
@physio_required # <<< ADD DECORATOR
def financials():
    selected_year = request.args.get('year', str(datetime.now().year))
    try:
        year = int(selected_year)
    except ValueError:
        flash('Invalid year selected.', 'warning')
        year = datetime.now().year
        selected_year = str(year)

    # --- Get available years (existing logic) ---
    available_years = db.session.query(
        func.extract('year', Treatment.created_at)
    ).distinct().order_by(func.extract('year', Treatment.created_at).desc()).all()
    available_years = [int(y[0]) for y in available_years if y[0] is not None]
    if not available_years:
        available_years = [year]
    # Ensure the selected year is in the list if it has data or is the current year
    if int(selected_year) not in available_years:
         # If the selected year isn't in the list (e.g., future year selected with no data),
         # add it to the list to allow selection, or default to the latest available year.
         # For simplicity, let's add it if it's the current year or later.
         if year >= datetime.now().year:
             available_years.insert(0, year)
         elif available_years: # Default to latest year with data if selected year is invalid past
             selected_year = str(available_years[0])
             year = available_years[0]
         else: # Default to current year if no data at all
             selected_year = str(datetime.now().year)
             year = int(selected_year)
             available_years = [year]


    # --- Initialize data structures ---
    # For Quarterly/Annual Table
    quarterly_data = {
        'q1': {'revenue': 0, 'costaspine_revenue': 0, 'costaspine_fee': 0, 'tax': 0, 'fixed_expenses': 0, 'net': 0},
        'q2': {'revenue': 0, 'costaspine_revenue': 0, 'costaspine_fee': 0, 'tax': 0, 'fixed_expenses': 0, 'net': 0},
        'q3': {'revenue': 0, 'costaspine_revenue': 0, 'costaspine_fee': 0, 'tax': 0, 'fixed_expenses': 0, 'net': 0},
        'q4': {'revenue': 0, 'costaspine_revenue': 0, 'costaspine_fee': 0, 'tax': 0, 'fixed_expenses': 0, 'net': 0},
        'annual': {'revenue': 0, 'costaspine_revenue': 0, 'costaspine_fee': 0, 'tax': 0, 'fixed_expenses': 0, 'net': 0}
    }
    # For Monthly Bracket Table
    monthly_data = {} # Key will be month number (1-12)

    tax_rate = 0.19
    costaspine_fee_rate = 0.30
    quarters_map = {1: 'q1', 2: 'q1', 3: 'q1',
                    4: 'q2', 5: 'q2', 6: 'q2',
                    7: 'q3', 8: 'q3', 9: 'q3',
                    10: 'q4', 11: 'q4', 12: 'q4'}

    # --- Loop through months 1-12 to calculate monthly and aggregate quarterly/annual data ---
    for month in range(1, 13):
        # Check if the month is in the future for the selected year
        current_month = datetime.now().month
        current_year = datetime.now().year
        if year == current_year and month > current_month:
            # Initialize future months with zeros and default bracket info
            month_start_date = datetime(year, month, 1)
            monthly_data[month] = {
                'month_name': month_start_date.strftime('%B'),
                'net_revenue': 0,
                'bracket': '-',
                'min_base': '-',
                'monthly_contribution': 0,
                'fixed_expenses': 0,
                'net_revenue_final': 0,
                'diff_to_upper': '-'
            }
            continue # Skip calculation for future months

        month_start_date = datetime(year, month, 1)
        # Get the last day of the month
        month_end_day = monthrange(year, month)[1]
        month_end_date = datetime(year, month, month_end_day, 23, 59, 59)
        q_key = quarters_map[month]

        # Query treatments for the specific month
        monthly_treatments_query = Treatment.query.filter(
            Treatment.created_at >= month_start_date,
            Treatment.created_at <= month_end_date,
            Treatment.status == 'Completed',
            Treatment.fee_charged > 0
        )

        if not current_user.is_admin:
            monthly_treatments_query = monthly_treatments_query.join(Patient).filter(Patient.user_id == current_user.id)
        
        monthly_treatments = monthly_treatments_query.all()

        # Calculate monthly figures
        m_revenue = 0
        m_costaspine_revenue = 0
        m_costaspine_fee = 0
        m_taxable_card_revenue = 0

        for t in monthly_treatments:
            fee = t.fee_charged or 0
            m_revenue += fee

            is_costaspine = t.location == 'CostaSpine Clinic'
            is_card = t.payment_method == 'Card'

            if is_costaspine:
                m_costaspine_revenue += fee
                m_costaspine_fee += fee * costaspine_fee_rate

            if is_card:
                if is_costaspine:
                    m_taxable_card_revenue += fee * (1 - costaspine_fee_rate)
                else:
                    m_taxable_card_revenue += fee

        m_tax = m_taxable_card_revenue * tax_rate
        m_net = m_revenue - m_costaspine_fee - m_tax

        # Find tax bracket for this month's net revenue
        current_bracket = find_bracket(m_net, TAX_BRACKETS_2025)
        bracket_desc = "-" # Default if no treatments/net revenue
        min_base_value = 0 # Store numeric value for calculation
        min_base_display = "-"
        diff_to_upper = "-"
        monthly_contribution = 0 # Default contribution

        if current_bracket:
            bracket_desc = current_bracket['desc']
            min_base_value = current_bracket['base']
            min_base_display = f"€{min_base_value:,.2f}"
            monthly_contribution = min_base_value * 0.314
            
            upper_bound = current_bracket['upper']
            if upper_bound == float('inf'):
                diff_to_upper = "Top Bracket"
            else:
                diff = upper_bound - m_net
                diff_to_upper = f"€{diff:,.2f}"
        elif m_net > 0: 
             bracket_desc = "Error: No bracket found"

        m_net_final = m_net - monthly_contribution

        monthly_data[month] = {
            'month_name': month_start_date.strftime('%B'),
            'net_revenue': m_net, 
            'bracket': bracket_desc,
            'min_base': min_base_display,
            'monthly_contribution': monthly_contribution,
            'fixed_expenses': TOTAL_FIXED_MONTHLY_EXPENSES, 
            'net_revenue_final': m_net_final, 
            'diff_to_upper': diff_to_upper
        }

        quarterly_data[q_key]['revenue'] += m_revenue
        quarterly_data[q_key]['costaspine_revenue'] += m_costaspine_revenue
        quarterly_data[q_key]['costaspine_fee'] += m_costaspine_fee
        quarterly_data[q_key]['tax'] += monthly_contribution 
        quarterly_data[q_key]['fixed_expenses'] += TOTAL_FIXED_MONTHLY_EXPENSES 
        quarterly_data[q_key]['net'] = quarterly_data[q_key]['revenue'] - quarterly_data[q_key]['costaspine_fee'] - quarterly_data[q_key]['tax'] - quarterly_data[q_key]['fixed_expenses']

        quarterly_data['annual']['revenue'] += m_revenue
        quarterly_data['annual']['costaspine_revenue'] += m_costaspine_revenue
        quarterly_data['annual']['costaspine_fee'] += m_costaspine_fee
        quarterly_data['annual']['tax'] += monthly_contribution 
        quarterly_data['annual']['fixed_expenses'] += TOTAL_FIXED_MONTHLY_EXPENSES 
        quarterly_data['annual']['net'] = quarterly_data['annual']['revenue'] - quarterly_data['annual']['costaspine_fee'] - quarterly_data['annual']['tax'] - quarterly_data['annual']['fixed_expenses']

    return render_template(
        'financials.html',
        data=quarterly_data, 
        monthly_breakdown=monthly_data, 
        selected_year=selected_year,
        available_years=sorted(list(set(available_years)), reverse=True), 
        tax_year=2025 
    )

# --- Review Missing Payments Route ---
@main.route('/review-payments')
@login_required
@physio_required # <<< ADD DECORATOR
def review_payments():
    """Displays treatments with fees but missing payment methods."""
    try:
        # --- Add call to update statuses first ---
        marked_count = mark_past_treatments_as_completed() 
        if marked_count > 0:
            print(f"Marked {marked_count} past treatments as completed before loading review page.")
            # Optionally flash a message, but might be noisy if frequent
            # flash(f"{marked_count} past treatment(s) automatically marked as completed.", "info")
        # --- End added call ---

        # Fetch treatments that are Completed and are missing a fee OR payment method
        base_query = Treatment.query.join(Patient).filter(
            Treatment.status == 'Completed', # Must be completed
            or_(
                Treatment.fee_charged.is_(None),
                Treatment.fee_charged == 0,
                Treatment.payment_method.is_(None),
                Treatment.payment_method == ''
            )
        )

        if not current_user.is_admin:
            base_query = base_query.filter(Patient.user_id == current_user.id)

        treatments_to_review = base_query.options(
            db.joinedload(Treatment.patient) # Eager load patient data
        ).order_by(
            Treatment.created_at.asc() # Show oldest first
        ).all()

        return render_template('review_payments.html', treatments=treatments_to_review)

    except Exception as e:
        print(f"Error loading review payments page: {e}")
        flash('Could not load payment review page. Please try again.', 'danger')
        return redirect(url_for('main.index'))

@main.route('/patient/new', methods=['GET', 'POST'])
@login_required
@physio_required # Or your equivalent decorator for physio access
def new_patient():
    current_patients, patient_limit = current_user.patient_usage_details

    if patient_limit is not None and current_patients >= patient_limit:
        flash(f"You have reached your current patient limit of {patient_limit}. Please upgrade your plan to add more patients.", 'warning')
        return redirect(url_for('main.pricing_page'))

    if request.method == 'POST':
        # Re-check just before creating, as a safeguard
        current_patients_post, patient_limit_post = current_user.patient_usage_details
        if patient_limit_post is not None and current_patients_post >= patient_limit_post:
            flash(f"You have reached your current patient limit of {patient_limit_post} while trying to save. Please upgrade your plan.", 'warning')
            # Repopulate form fields for clarity, though redirecting is simpler
            name = request.form['name']
            date_of_birth_str = request.form.get('date_of_birth')
            contact = request.form['contact']
            diagnosis = request.form['diagnosis']
            treatment_plan = request.form.get('treatment_plan')
            notes = request.form.get('notes')
            patient_contact_email_on_patient_record = request.form.get('patient_contact_email_on_patient_record')
            patient_contact_phone_on_patient_record = request.form.get('patient_contact_phone_on_patient_record')
            address_line1 = request.form.get('address_line1')
            address_line2 = request.form.get('address_line2')
            city = request.form.get('city')
            postcode = request.form.get('postcode')
            preferred_location = request.form.get('preferred_location')
            portal_login_email = request.form.get('patient_email', '').strip().lower()

            # It's better to redirect to pricing page for consistency
            return redirect(url_for('main.pricing_page'))

        # --- Basic Patient Info ---
        name = request.form['name']
        date_of_birth_str = request.form.get('date_of_birth')
        contact = request.form['contact']
        diagnosis = request.form['diagnosis']
        treatment_plan = request.form.get('treatment_plan')
        notes = request.form.get('notes')
        patient_contact_email_on_patient_record = request.form.get('patient_contact_email_on_patient_record')
        patient_contact_phone_on_patient_record = request.form.get('patient_contact_phone_on_patient_record')
        address_line1 = request.form.get('address_line1')
        address_line2 = request.form.get('address_line2')
        city = request.form.get('city')
        postcode = request.form.get('postcode')
        preferred_location = request.form.get('preferred_location')
        
        try:
            date_of_birth = datetime.strptime(date_of_birth_str, '%Y-%m-%d').date() if date_of_birth_str else None
        except ValueError:
            flash('Invalid date format for Date of Birth. Please use YYYY-MM-DD.', 'danger')
            return render_template('new_patient.html', name=name, date_of_birth=date_of_birth_str, contact=contact, diagnosis=diagnosis, treatment_plan=treatment_plan, notes=notes, patient_contact_email_on_patient_record=patient_contact_email_on_patient_record, patient_contact_phone_on_patient_record=patient_contact_phone_on_patient_record, address_line1=address_line1, address_line2=address_line2, city=city, postcode=postcode, preferred_location=preferred_location)

        new_patient_obj = Patient(
            name=name,
            date_of_birth=date_of_birth,
            contact=contact,
            diagnosis=diagnosis,
            treatment_plan=treatment_plan,
            notes=notes,
            email=patient_contact_email_on_patient_record,
            phone=patient_contact_phone_on_patient_record,
            address_line1=address_line1,
            address_line2=address_line2,
            city=city,
            postcode=postcode,
            preferred_location=preferred_location,
            user_id=current_user.id, 
            status='Active'
        )
        
        portal_login_email = request.form.get('patient_email', '').strip().lower()
        portal_login_password = request.form.get('patient_password', '')
        newly_created_portal_user = None

        if portal_login_email:
            existing_user_check = User.query.filter_by(email=portal_login_email).first()
            if existing_user_check:
                flash('That portal login email address is already in use. Cannot create patient portal account with this email.', 'danger')
                return render_template('new_patient.html', name=name, date_of_birth=date_of_birth_str, contact=contact, diagnosis=diagnosis, treatment_plan=treatment_plan, notes=notes, patient_contact_email_on_patient_record=patient_contact_email_on_patient_record, patient_contact_phone_on_patient_record=patient_contact_phone_on_patient_record, address_line1=address_line1, address_line2=address_line2, city=city, postcode=postcode, preferred_location=preferred_location, portal_login_email=portal_login_email)
            
            if not portal_login_password:
                flash('Password is required when providing an email for patient portal access.', 'danger')
                return render_template('new_patient.html', name=name, date_of_birth=date_of_birth_str, contact=contact, diagnosis=diagnosis, treatment_plan=treatment_plan, notes=notes, patient_contact_email_on_patient_record=patient_contact_email_on_patient_record, patient_contact_phone_on_patient_record=patient_contact_phone_on_patient_record, address_line1=address_line1, address_line2=address_line2, city=city, postcode=postcode, preferred_location=preferred_location, portal_login_email=portal_login_email)

            newly_created_portal_user = User(
                username=portal_login_email, 
                email=portal_login_email,
                role='patient'
            )
            newly_created_portal_user.set_password(portal_login_password)
        
        try:
            db.session.add(new_patient_obj) 
            
            if newly_created_portal_user:
                db.session.add(newly_created_portal_user) 
            
            db.session.flush() 
            
            if newly_created_portal_user: 
                new_patient_obj.portal_user_id = newly_created_portal_user.id 
                
            db.session.commit()
            flash_message = f'Patient {name} created successfully!'
            if newly_created_portal_user:
                flash_message += ' Portal access enabled.'
            flash(flash_message, 'success')
            return redirect(url_for('main.patient_detail', id=new_patient_obj.id))
        
        except Exception as e: 
            db.session.rollback()
            flash(f'Error creating patient: {str(e)}', 'danger')
            print(f"Error creating patient: {e}") 
            return render_template('new_patient.html',
                                   name=name, date_of_birth=date_of_birth_str, contact=contact, 
                                   diagnosis=diagnosis, treatment_plan=treatment_plan, notes=notes,
                                   patient_contact_email_on_patient_record=patient_contact_email_on_patient_record, 
                                   patient_contact_phone_on_patient_record=patient_contact_phone_on_patient_record,
                                   address_line1=address_line1, address_line2=address_line2, city=city,
                                   postcode=postcode, preferred_location=preferred_location,
                                   portal_login_email=portal_login_email)

    # GET request
    return render_template('new_patient.html')

@main.route('/patient/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_patient(id):
    patient = Patient.query.options(
        joinedload(Patient.portal_user_account)
    ).get_or_404(id)

    # --- Access Control ---
    if not current_user.is_admin:
        if current_user.role == 'physio':
            if patient.user_id != current_user.id:
                flash('You do not have permission to edit this patient\'s details.', 'danger')
                return redirect(url_for('main.patients_list'))
        elif current_user.role == 'patient':
            if not patient.portal_user_account or patient.portal_user_account.id != current_user.id:
                flash('You do not have permission to edit these patient details.', 'danger')
                return redirect(url_for('main.patient_dashboard'))
            # If it IS their record, they are allowed through to edit.
        else: # This 'else' belongs to 'if current_user.role == 'physio':'
            flash('Access Denied.', 'danger')
            return redirect(url_for('main.index'))
    # --- End Access Control ---
    
    if request.method == 'POST':
        print(f"--- edit_patient POST for patient ID: {id} ---")
        print(f"Form data received: {request.form}")

        # --- 1. Update Basic Patient Info ---
        try:
            patient.name = request.form['name']
            dob_str = request.form.get('date_of_birth')
            patient.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
            patient.contact = request.form['contact']
            patient.diagnosis = request.form['diagnosis']
            patient.treatment_plan = request.form['treatment_plan']
            patient.notes = request.form['notes']
            patient.status = request.form['status']
            patient.email = request.form.get('patient_contact_email')
            patient.phone = request.form.get('patient_contact_phone')
            patient.address_line1 = request.form.get('address_line1')
            patient.address_line2 = request.form.get('address_line2')
            patient.city = request.form.get('city')
            patient.postcode = request.form.get('postcode')
            patient.preferred_location = request.form.get('preferred_location')
        except ValueError:
            flash('Invalid date format for Date of Birth. Please use YYYY-MM-DD.', 'danger')
            return render_template('edit_patient.html', patient=patient)
        except Exception as e_basic:
            flash(f'Error parsing basic patient information: {str(e_basic)}', 'danger')
            print(f"Error parsing patient info {id}: {e_basic}")
            return render_template('edit_patient.html', patient=patient)
            
        # --- 2. Handle Portal User Account ---
        portal_login_email = request.form.get('patient_email', '').strip().lower()
        portal_login_password = request.form.get('patient_password', '')
        user_action_message_suffix = ''
        newly_created_portal_user_to_link = None

        if portal_login_email:
            user_to_exclude_id = patient.portal_user_account.id if patient.portal_user_account else -1 # Get ID if portal user exists
            conflicting_user = User.query.filter(User.email == portal_login_email, User.id != user_to_exclude_id).first()

            if conflicting_user:
                flash('That portal login email address is already in use by another account.', 'danger')
                return render_template('edit_patient.html', patient=patient) 
                
            if patient.portal_user_account: 
                portal_user = patient.portal_user_account
                if portal_user.email != portal_login_email:
                    portal_user.email = portal_login_email
                    portal_user.username = portal_login_email # Keep username synced with email
                    user_action_message_suffix = ' Portal access updated.'
                if portal_login_password: # If new password provided, update it
                    print(f"DEBUG: Updating password for user {portal_user.email} with raw password: '{portal_login_password}'") # TEMPORARY
                    portal_user.set_password(portal_login_password)
                    print(f"DEBUG: New password hash for {portal_user.email}: {portal_user.password_hash}") # TEMPORARY
                    user_action_message_suffix = ' Portal access updated.'
            else: # No existing portal user, create a new one
                if not portal_login_password: # Password is required for new portal user
                    flash('A password is required to create a new patient portal login.', 'danger')
                    return render_template('edit_patient.html', patient=patient)
                    
                newly_created_portal_user_to_link = User(
                    username=portal_login_email, # Set username to email
                    email=portal_login_email,
                    role='patient'
                )
                print(f"DEBUG: Creating new portal user {portal_login_email} with raw password: '{portal_login_password}'") # TEMPORARY
                newly_created_portal_user_to_link.set_password(portal_login_password)
                print(f"DEBUG: Password hash for new user {portal_login_email}: {newly_created_portal_user_to_link.password_hash}") # TEMPORARY
                db.session.add(newly_created_portal_user_to_link) # Add to session
                user_action_message_suffix = ' Portal access enabled.'
        
        elif portal_login_password and patient.portal_user_account: # Email not changed, but password provided for existing portal user
            print(f"DEBUG: Updating password (email unchanged) for user {patient.portal_user_account.email} with raw password: '{portal_login_password}'") # TEMPORARY
            patient.portal_user_account.set_password(portal_login_password)
            print(f"DEBUG: New password hash for {patient.portal_user_account.email}: {patient.portal_user_account.password_hash}") # TEMPORARY
            user_action_message_suffix = ' Portal access updated.'
        
        # If only portal_login_email is blanked out, and there was an existing portal user,
        # current logic doesn't remove/disable the portal user. This might be desired or not.
        # For now, we assume blanking email field means no change to portal status if password not also changed.

        # --- 3. Commit all changes ---
        try:
            if newly_created_portal_user_to_link:
                # Need to flush to get the ID of the newly_created_portal_user_to_link
                db.session.flush() 
                patient.portal_user_id = newly_created_portal_user_to_link.id
            
            patient.updated_at = datetime.utcnow() # Ensure patient updated_at is set
            db.session.commit() # Commit all changes (patient, existing user, new user)
            flash('Patient information updated successfully!' + user_action_message_suffix, 'success')
            return redirect(url_for('main.patient_detail', id=patient.id))
            
        except Exception as e_commit:
            db.session.rollback()
            flash(f'An error occurred while saving changes: {str(e_commit)}', 'danger')
            print(f"Error committing changes for patient {id}: {e_commit}")
            return render_template('edit_patient.html', patient=patient)
            
    # --- GET Request ---
    # For GET, ensure patient data (including portal_user_account details if any) is passed
    return render_template('edit_patient.html', patient=patient)

@main.route('/patient/<int:id>/delete', methods=['POST'])
@login_required
@physio_required
def delete_patient(id):
    """Delete a patient and all associated records."""
    patient = Patient.query.get_or_404(id)

    if not current_user.is_admin and patient.user_id != current_user.id:
        flash('You do not have permission to delete this patient.', 'danger')
        return redirect(url_for('main.patients_list'))

    try:
        # Delete treatments and their trigger points
        for treatment in patient.treatments:
            TriggerPoint.query.filter_by(treatment_id=treatment.id).delete()
            db.session.delete(treatment)

        # Delete related reports and recurring appointments
        PatientReport.query.filter_by(patient_id=patient.id).delete()
        RecurringAppointment.query.filter_by(patient_id=patient.id).delete()

        # Unlink any matched Calendly bookings
        UnmatchedCalendlyBooking.query.filter_by(matched_patient_id=patient.id).update({'matched_patient_id': None})

        # Remove portal user account if present
        if patient.portal_user_account:
            db.session.delete(patient.portal_user_account)

        db.session.delete(patient)
        db.session.commit()
        flash('Patient deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting patient: {e}', 'danger')
        print(f"Error deleting patient {id}: {e}")

    return redirect(url_for('main.patients_list'))

# --- Patient Dashboard Route ---
@main.route('/patient/dashboard')
@login_required
def patient_dashboard():
    # Ensure the user is a patient
    if current_user.role != 'patient':
        flash('Access denied. This dashboard is for patient accounts.', 'danger')
        return redirect(url_for('main.index'))

    patient_record = current_user.patient_record 

    if not patient_record:
        flash('No patient data linked to your portal account. Please contact support.', 'danger')
        logout_user() 
        return redirect(url_for('auth.login'))

    print(f"DEBUG: patient_record type: {type(patient_record)}") # TEMPORARY DEBUG
    print(f"DEBUG: patient_record content: {patient_record}") # TEMPORARY DEBUG

    today = datetime.now()
    
    upcoming_appointments = Treatment.query.filter(
        Treatment.patient_id == patient_record.id,
        Treatment.status == 'Scheduled',
        Treatment.created_at >= today 
    ).order_by(Treatment.created_at.asc()).limit(5).all()
    
    latest_homework = PatientReport.query.filter(
        PatientReport.patient_id == patient_record.id,
        PatientReport.report_type == 'Exercise Homework'
    ).order_by(PatientReport.generated_date.desc()).first()

    past_homework_query = PatientReport.query.filter(
        PatientReport.patient_id == patient_record.id,
        PatientReport.report_type == 'Exercise Homework'
    )
    if latest_homework:
        past_homework_query = past_homework_query.filter(PatientReport.id != latest_homework.id)
        
    past_homework_reports = past_homework_query.order_by(PatientReport.generated_date.desc()).limit(5).all()

    return render_template('patient_dashboard.html',
                           upcoming_appointments=upcoming_appointments,
                           latest_homework=latest_homework,
                           past_homework_reports=past_homework_reports,
                           patient=patient_record)

@main.route('/patient/profile')
@login_required
def patient_profile():
    if current_user.role != 'patient':
        flash('Access denied. This profile page is for patient accounts.', 'danger')
        return redirect(url_for('main.index'))
        
    patient_record = current_user.patient_record
    
    if not patient_record:
        flash('No patient data linked to your portal account. Please contact support.', 'danger')
        logout_user()
        return redirect(url_for('auth.login'))
        
    return render_template('patient_profile.html', patient=patient_record)

@main.route('/patient/update-contact', methods=['POST'])
@login_required
def update_patient_contact():
    # Asegurar que el usuario es un paciente
    if current_user.role != 'patient':
        return jsonify({'success': False, 'error': 'Access denied'}), 403
        
    patient_record = current_user.patient_record # Use the new relationship
    if not patient_record:
         return jsonify({'success': False, 'error': 'No patient record linked to your portal account'}), 400
         
    # Now patient_record is the Patient object whose details are being updated
    try:
        # Get data from form - these update the Patient model fields
        patient_record.email = request.form.get('email') # Patient's contact email
        patient_record.phone = request.form.get('phone')
        patient_record.address_line1 = request.form.get('address_line1')
        patient_record.address_line2 = request.form.get('address_line2')
        patient_record.city = request.form.get('city')
        patient_record.postcode = request.form.get('postcode')
        patient_record.preferred_location = request.form.get('preferred_location')
        
        # If the patient's contact email is also their portal login email, update the User model too.
        # This assumes the form field for 'email' is intended for both.
        if patient_record.portal_user_account and patient_record.portal_user_account.email != patient_record.email:
            new_email = patient_record.email
            if new_email:
                conflicting_user = User.query.filter(User.email == new_email, User.id != patient_record.portal_user_account.id).first()
                if conflicting_user:
                    return jsonify({'success': False, 'error': 'That email address is already in use by another portal account.'}), 409 # Conflict
                patient_record.portal_user_account.email = new_email
                patient_record.portal_user_account.username = new_email # Keep username synced
            # else: # If email is cleared, what to do with portal_user_account.email? For now, leave as is or handle explicitly.

        patient_record.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Contact information updated successfully!'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating patient contact for user {current_user.id}, patient record {patient_record.id if patient_record else 'N/A'}: {e}")
        return jsonify({'success': False, 'error': 'An internal error occurred while updating contact information.'}), 500

@main.route('/analytics/generate_new_report', methods=['POST'])
@login_required
@physio_required
def generate_new_analytics_report():
    try:
        user_generating_report = current_user # For clarity
        is_admin_generating = user_generating_report.is_admin

        # --- Comprehensive Data Gathering for AI Report ---
        # Basic Practice Stats
        if is_admin_generating:
            total_patients = Patient.query.count()
            active_patients = Patient.query.filter(Patient.status == 'Active').count()
            # For treatments, we need to sum up all treatments if admin, or user-specific if not
            total_treatments = Treatment.query.count()
        else:
            total_patients = Patient.query.filter_by(user_id=user_generating_report.id).count()
            active_patients = Patient.query.filter_by(user_id=user_generating_report.id, status='Active').count()
            total_treatments = Treatment.query.join(Patient).filter(Patient.user_id == user_generating_report.id).count()
        
        avg_treatments_per_patient = round(total_treatments / total_patients, 1) if total_patients else 0

        # Average Monthly Revenue
        monthly_revenue_base_query = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.sum(Treatment.fee_charged).label('monthly_total')
        ).filter(Treatment.fee_charged.isnot(None))

        if not is_admin_generating:
            monthly_revenue_base_query = monthly_revenue_base_query.join(Patient).filter(Patient.user_id == user_generating_report.id)
        
        monthly_revenue_data = monthly_revenue_base_query.group_by('month').all()
        total_revenue_all_time = sum(m.monthly_total for m in monthly_revenue_data if m.monthly_total)
        num_months_with_revenue = len(monthly_revenue_data)
        avg_monthly_revenue = total_revenue_all_time / num_months_with_revenue if num_months_with_revenue else 0

        # Common Diagnoses (Top 10)
        common_diagnoses_base_query = (db.session.query(
            Patient.diagnosis,
            func.count(Patient.id).label('count')
            ).filter(Patient.diagnosis.isnot(None), Patient.diagnosis != ''))

        if not is_admin_generating:
            common_diagnoses_base_query = common_diagnoses_base_query.filter(Patient.user_id == user_generating_report.id)
        
        common_diagnoses_query_result = (common_diagnoses_base_query
            .group_by(Patient.diagnosis)
            .order_by(func.count(Patient.id).desc())
            .limit(10).all())
        common_diagnoses = [{'diagnosis': d.diagnosis, 'count': d.count} for d in common_diagnoses_query_result]

        # Revenue by Visit Type
        revenue_by_visit_type_base_query = (db.session.query(
            Treatment.treatment_type,
            func.sum(Treatment.fee_charged).label('total_revenue')
            ).filter(Treatment.fee_charged.isnot(None), Treatment.treatment_type.isnot(None)))

        if not is_admin_generating:
            revenue_by_visit_type_base_query = revenue_by_visit_type_base_query.join(Patient).filter(Patient.user_id == user_generating_report.id)

        revenue_by_visit_type_query_result = (revenue_by_visit_type_base_query
            .group_by(Treatment.treatment_type)
            .order_by(func.sum(Treatment.fee_charged).desc()).all())
        revenue_by_visit_type = [{'type': r.treatment_type, 'revenue': float(r.total_revenue)} for r in revenue_by_visit_type_query_result]
        
        # Patient Age Distribution
        patients_for_age_query = Patient.query.filter(Patient.date_of_birth.isnot(None))
        if not is_admin_generating:
            patients_for_age_query = patients_for_age_query.filter(Patient.user_id == user_generating_report.id)
        patients_with_dob = patients_for_age_query.all()
        
        age_distribution = {'0-17': 0, '18-30': 0, '31-45': 0, '46-60': 0, '61+': 0, 'Unknown': 0}
        for p in patients_with_dob:
            age = calculate_age(p.date_of_birth) # Assuming calculate_age is defined elsewhere
            if age is None:
                age_distribution['Unknown'] += 1
            elif age <= 17:
                age_distribution['0-17'] += 1
            elif age <= 30:
                age_distribution['18-30'] += 1
            elif age <= 45:
                age_distribution['31-45'] += 1
            elif age <= 60:
                age_distribution['46-60'] += 1
            else:
                age_distribution['61+'] += 1

        twelve_months_ago = datetime.utcnow() - timedelta(days=365)
        
        # Treatments by Month
        treatments_by_month_base_query = (db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.count(Treatment.id).label('count')
            ).filter(Treatment.created_at >= twelve_months_ago))
        
        if not is_admin_generating:
            treatments_by_month_base_query = treatments_by_month_base_query.join(Patient).filter(Patient.user_id == user_generating_report.id)

        treatments_by_month_query_result = (treatments_by_month_base_query
            .group_by(func.strftime('%Y-%m', Treatment.created_at))
            .order_by(func.strftime('%Y-%m', Treatment.created_at).asc()).all())
        treatments_by_month = [{'month': t.month, 'count': t.count} for t in treatments_by_month_query_result]

        # New Patients by Month
        new_patients_by_month_base_query = (db.session.query(
            func.strftime('%Y-%m', Patient.created_at).label('month'), # Corrected to Patient.created_at
            func.count(Patient.id).label('count')
            ).filter(Patient.created_at >= twelve_months_ago)) # Corrected to Patient.created_at

        if not is_admin_generating:
            new_patients_by_month_base_query = new_patients_by_month_base_query.filter(Patient.user_id == user_generating_report.id)

        new_patients_by_month_query_result = (new_patients_by_month_base_query
            .group_by(func.strftime('%Y-%m', Patient.created_at)) # Corrected to Patient.created_at
            .order_by(func.strftime('%Y-%m', Patient.created_at).asc()).all()) # Corrected to Patient.created_at
        new_patients_by_month = [{'month': p.month, 'count': p.count} for p in new_patients_by_month_query_result]

        analytics_data = {
            'total_patients': total_patients,
            'active_patients': active_patients,
            'total_treatments': total_treatments,
            'avg_treatments': avg_treatments_per_patient,
            'avg_monthly_revenue': avg_monthly_revenue,
            'common_diagnoses': common_diagnoses,
            'revenue_by_visit_type': revenue_by_visit_type,
            'age_distribution': age_distribution,
            'treatments_by_month': treatments_by_month,
            'patients_by_month': new_patients_by_month
        }

        report_content = generate_deepseek_report(analytics_data) # Assuming this function is defined elsewhere

        if "Error:" in report_content or "API key not configured" in report_content:
            flash(f"Failed to generate AI report: {report_content}", "danger")
        else:
            report_user_id = None
            if not is_admin_generating:
                report_user_id = user_generating_report.id
            
            new_report = PracticeReport(
                content=report_content, 
                generated_at=datetime.utcnow(),
                user_id=report_user_id # Set user_id here
            )
            db.session.add(new_report)
            db.session.commit()
            flash("Successfully generated new AI practice insights report!", "success")
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error generating new analytics report for user {current_user.id if current_user else 'Unknown'}: {e}")
        current_app.logger.error(traceback.format_exc())
        flash(f"An unexpected error occurred while generating the report: {str(e)}", "danger")

    return redirect(url_for('main.analytics'))

@main.route('/profile/calendly-settings', methods=['GET', 'POST'])
@login_required
def manage_calendly_settings():
    if current_user.role == 'patient':
        flash('This page is not available for patient accounts.', 'warning')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        token = request.form.get('calendly_api_token', '').strip()
        uri = request.form.get('calendly_user_uri', '').strip()

        # Basic validation: Check if URI looks like a Calendly user URI
        if uri and not uri.startswith('https://api.calendly.com/users/'):
            flash('Invalid Calendly User URI format. It should start with "https://api.calendly.com/users/".', 'danger')
            # Re-render form with submitted values
            # generate_csrf() is called implicitly by Flask-WTF for POST requests if the form has a csrf_token field.
            # However, to be absolutely sure the template has it for re-rendering on error:
            csrf_token_value_on_post_error = generate_csrf()
            return render_template('calendly_settings.html', 
                                   calendly_api_token=token, 
                                   calendly_user_uri=uri,
                                   csrf_token_value=csrf_token_value_on_post_error)

        current_user.calendly_api_token = token if token else None
        current_user.calendly_user_uri = uri if uri else None
        
        try:
            db.session.commit()
            flash('Calendly settings updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating Calendly settings for user {current_user.id}: {e}")
            flash('An error occurred while saving your settings. Please try again.', 'danger')
        
        return redirect(url_for('main.manage_calendly_settings'))

    # GET request
    csrf_token_value = generate_csrf()
    return render_template('calendly_settings.html', 
                           calendly_api_token=current_user.calendly_api_token, 
                           calendly_user_uri=current_user.calendly_user_uri,
                           csrf_token_value=csrf_token_value)

# Route for the pricing page
@main.route('/pricing')
@login_required
def pricing_page():
    all_plans = Plan.query.filter_by(is_active=True).order_by(Plan.display_order).all()
    
    active_plan_id = None
    user_subscription = None # Will hold the UserSubscription object

    if current_user.is_authenticated:
        user_subscription = current_user.current_subscription # Get the full subscription object
        if user_subscription and user_subscription.plan:
            active_plan_id = user_subscription.plan.id
            
    stripe_publishable_key = current_app.config.get('STRIPE_PUBLISHABLE_KEY')
    
    return render_template('pricing.html', 
                           plans=all_plans, 
                           stripe_publishable_key=stripe_publishable_key,
                           active_plan_id=active_plan_id,
                           user_subscription=user_subscription) # Pass the subscription object

@main.route('/subscription-success')
@login_required
def subscription_success():
    session_id = request.args.get('session_id')
    plan_name = None
    error_message = None

    if not session_id:
        error_message = "Checkout session ID is missing. Cannot confirm subscription details."
        flash(error_message, 'warning')
    else:
        try:
            # Retrieve the session from Stripe to get details about the purchase
            checkout_session = stripe.checkout.Session.retrieve(session_id, expand=['line_items'])
            
            if checkout_session and checkout_session.line_items and checkout_session.line_items.data:
                # Assuming the first line item is the plan they subscribed to
                stripe_price_id = checkout_session.line_items.data[0].price.id
                if stripe_price_id:
                    # Find the plan in your database using the Stripe Price ID
                    plan = Plan.query.filter_by(stripe_price_id=stripe_price_id).first()
                    if plan:
                        plan_name = plan.name
                        flash(f'Thank you for subscribing to the {plan_name} plan!', 'success')
                    else:
                        error_message = f"Could not find a plan in our system matching the Stripe Price ID: {stripe_price_id}. Your payment was successful, please contact support."
                        flash(error_message, 'warning')
                else:
                    error_message = "Could not determine the subscribed plan from Stripe session. Your payment was successful, please contact support."
                    flash(error_message, 'warning')
            else:
                error_message = "Could not retrieve line items from Stripe session. Your payment was successful, please contact support."
                flash(error_message, 'warning')

        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe API error retrieving session {session_id} for success page: {str(e)}")
            error_message = "There was an error retrieving your subscription details from Stripe. Your payment was likely successful. Please contact support if you have questions."
            flash(error_message, 'danger')
        except Exception as e:
            current_app.logger.error(f"Unexpected error on subscription success page for session {session_id}: {str(e)}", exc_info=True)
            error_message = "An unexpected error occurred while confirming your subscription details. Please contact support."
            flash(error_message, 'danger')

    if not plan_name and not error_message: # Generic fallback if no specific message was flashed
        flash('Your subscription has been activated successfully!', 'success')

    return render_template('subscription_success.html', plan_name=plan_name, error_message=error_message)

@main.route('/manage-subscription')
@login_required
def manage_subscription():
    # Ensure the user has a Stripe Customer ID
    if not current_user.stripe_customer_id:
        flash('Unable to manage subscription: No Stripe customer ID found.', 'warning')
        return redirect(url_for('main.pricing_page'))

    try:
        # Create a new Stripe Billing Portal session
        # The return_url is where the user will be redirected after they are done in the portal
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=url_for('main.pricing_page', _external=True)
        )
        return redirect(session.url)
    except stripe.error.StripeError as e:
        flash(f'Could not open Stripe billing portal: {str(e)}', 'danger')
        current_app.logger.error(f"Stripe Billing Portal error for user {current_user.id}: {str(e)}")
        return redirect(url_for('main.pricing_page'))
    except Exception as e:
        flash('An unexpected error occurred while trying to access the billing portal.', 'danger')
        current_app.logger.error(f"Unexpected error accessing billing portal for user {current_user.id}: {str(e)}")
        return redirect(url_for('main.pricing_page'))

@main.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    """Handles the request to cancel a user's active subscription at the end of the current billing period."""
    current_sub = current_user.current_subscription
    active_plan_name = current_user.active_plan.name if current_user.active_plan else "your plan"

    if not current_sub or current_sub.status not in ['active', 'trialing']:
        flash('You do not have an active subscription to cancel.', 'warning')
        return redirect(url_for('main.pricing_page'))

    if current_sub.cancel_at_period_end:
        flash(f'Your subscription for {active_plan_name} is already set to cancel at the end of the current period.', 'info')
        return redirect(url_for('main.pricing_page'))

    if not current_sub.stripe_subscription_id:
        flash('Cannot cancel via Stripe: Local subscription record is missing Stripe Subscription ID.', 'danger')
        current_app.logger.error(f"User {current_user.id} tried to cancel subscription {current_sub.id} but no stripe_subscription_id found.")
        # Potentially handle this by manually deactivating locally if it's a non-Stripe plan or an error state.
        # For now, we assume Stripe-managed subscriptions.
        return redirect(url_for('main.pricing_page'))

    try:
        # Update the subscription on Stripe to cancel at period end
        stripe.Subscription.modify(
            current_sub.stripe_subscription_id,
            cancel_at_period_end=True
        )

        # Update the local subscription record
        current_sub.cancel_at_period_end = True
        current_sub.canceled_at = datetime.utcnow() # Record when the cancellation request was made
        # Optionally, change status to 'pending_cancellation' or keep as 'active' 
        # until webhook confirms `invoice.payment_failed` or `customer.subscription.deleted`.
        # For simplicity, keeping status 'active' but `cancel_at_period_end` is True is common.
        # Stripe webhook for `customer.subscription.updated` should reflect `cancel_at_period_end`.
        # And `customer.subscription.deleted` when it's truly gone.
        
        db.session.commit()
        ends_at_readable = current_sub.current_period_ends_at.strftime('%B %d, %Y') if current_sub.current_period_ends_at else "the end of the current billing period"
        flash(f'Your subscription for {active_plan_name} has been set to cancel at {ends_at_readable}. You will retain access until then.', 'success')
        current_app.logger.info(f"User {current_user.id} successfully set subscription {current_sub.stripe_subscription_id} to cancel at period end.")

    except stripe.error.StripeError as e:
        flash(f'Could not update your subscription with Stripe: {str(e)}', 'danger')
        current_app.logger.error(f"Stripe API error while trying to set cancel_at_period_end for user {current_user.id}, sub {current_sub.stripe_subscription_id}: {str(e)}")
    except Exception as e:
        db.session.rollback()
        flash('An unexpected error occurred while canceling your subscription. Please try again or contact support.', 'danger')
        current_app.logger.error(f"Unexpected error canceling subscription for user {current_user.id}, sub {current_sub.stripe_subscription_id}: {str(e)}", exc_info=True)

    return redirect(url_for('main.pricing_page'))

@main.route('/my-account', methods=['GET', 'POST']) # Add POST method
@login_required
def my_account():
    """Renders the My Account page with tabs for subscription, profile, and billing.
    Handles email and password updates from the Profile tab.
    """
    email_form = UpdateEmailForm(prefix='email_form')
    password_form = ChangePasswordForm(prefix='password_form')
    
    user_subscription = current_user.current_subscription
    active_plan = None
    if user_subscription and hasattr(user_subscription, 'plan'):
        active_plan = user_subscription.plan

    if request.method == 'POST':
        if email_form.submit_email.data and email_form.validate():
            # Check if new email is different and not already taken
            if email_form.email.data.lower() != current_user.email.lower():
                existing_user = User.query.filter(func.lower(User.email) == func.lower(email_form.email.data), User.id != current_user.id).first()
                if existing_user:
                    flash('That email address is already in use. Please choose a different one.', 'danger')
                else:
                    current_user.email = email_form.email.data
                    db.session.commit()
                    flash('Your email address has been updated successfully.', 'success')
                    return redirect(url_for('main.my_account', _anchor='profile-tab-pane')) 
            else:
                flash('The new email is the same as your current one.', 'info')
        
        elif password_form.submit_password.data and password_form.validate():
            if current_user.check_password(password_form.current_password.data):
                current_user.set_password(password_form.new_password.data)
                db.session.commit()
                flash('Your password has been updated successfully.', 'success')
                return redirect(url_for('main.my_account', _anchor='profile-tab-pane'))
            else:
                flash('Incorrect current password.', 'danger')
        
        # If we reached here and it was a POST, it means a form was submitted
        # but either not by the specific submit buttons we checked, or it failed validation.
        # WTForms will automatically add errors to the form objects if validate() failed.
        # We just need to fall through to re-render the template with these forms.

    return render_template('my_account.html', 
                           user_subscription=user_subscription, 
                           active_plan=active_plan,
                           email_form=email_form,
                           password_form=password_form)

# Route to handle password change
@main.route('/my-account/change-password', methods=['POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        user = current_user
        if user.check_password(form.current_password.data):
            user.set_password(form.new_password.data)
            db.session.commit()
            flash('Password updated successfully!', 'success')
        else:
            flash('Incorrect current password.', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", 'danger')
    return redirect(url_for('main.my_account'))

@main.route('/calendar')
@login_required
@physio_required # Assuming only physios/admins should access the main calendar view
def calendar_page():
    """Renders the main calendar page."""
    # Fetch ALL patients for the new appointment modal
    if current_user.is_admin:
        patients = Patient.query.order_by(Patient.name).all() # Removed status filter
    else: # Physio role (guaranteed by @physio_required)
        patients = Patient.query.filter_by(user_id=current_user.id).order_by(Patient.name).all() # Removed status filter
    
    return render_template('calendar.html', title="Calendar", patients=patients)

@main.route('/api/calendar-appointments')
@login_required
@physio_required
def get_calendar_appointments():
    """Fetch appointments for FullCalendar, including recurring ones."""
    start_str = request.args.get('start')
    end_str = request.args.get('end')

    events = []
    
    if not start_str or not end_str:
        return jsonify({"error": "Start and end dates are required for fetching calendar events."}), 400

    try:
        start_date_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        end_date_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))

        if start_date_dt.tzinfo is None:
            start_date_dt = UTC.localize(start_date_dt)
        if end_date_dt.tzinfo is None:
            end_date_dt = UTC.localize(end_date_dt)
        
        calendar_view_start_date = start_date_dt.date()
        calendar_view_end_date = end_date_dt.date()

    except ValueError:
        return jsonify({"error": "Invalid date format for start or end parameters"}), 400

    # 1. Fetch standard (non-recurring) treatments
    treatments_query = Treatment.query.join(Patient).filter(
        Patient.user_id == current_user.id,
        Treatment.status == 'Scheduled',
        Treatment.created_at >= start_date_dt,
        Treatment.created_at < end_date_dt
    )
    scheduled_treatments = treatments_query.all()

    for treatment in scheduled_treatments:
        event_start = treatment.created_at.isoformat()
        event_end = (treatment.created_at + timedelta(hours=1)).isoformat()

        title = f"{treatment.patient.name} - {treatment.treatment_type if treatment.treatment_type else 'Appointment'}"
        color = '#007bff' # Default blue
        if treatment.treatment_type:
            if "Initial Assessment" in treatment.treatment_type: color = '#28a745'
            elif "Follow-up" in treatment.treatment_type: color = '#17a2b8'
        
        events.append({
            'id': str(treatment.id), # Ensure ID is string for FullCalendar
            'title': title,
            'start': event_start,
            'end': event_end,
            'allDay': False,
            'color': color,
            'extendedProps': {
                'type': 'treatment',
                'patient_id': treatment.patient_id,
                'patient_name': treatment.patient.name,
                'treatment_type': treatment.treatment_type,
                'status': treatment.status,
                'notes': treatment.notes
            }
        })

    # 2. Fetch and process recurring appointments
    recurring_appointments = RecurringAppointment.query.join(Patient).filter(
        Patient.user_id == current_user.id
    ).options(joinedload(RecurringAppointment.patient)).all()

    # day_mapping removed as RecurringAppointment model uses recurrence_type

    for ra in recurring_appointments:
        if not ra.patient:
            current_app.logger.warn(f"Recurring appointment ID {ra.id} is missing patient data.")
            continue
        
        # Check for recurrence_type
        if not ra.recurrence_type:
            current_app.logger.warn(f"Recurring appointment ID {ra.id} for patient {ra.patient.name} has no recurrence_type set. Skipping.")
            continue

        if ra.time_of_day is None: # Changed from ra.time
            current_app.logger.warn(f"Recurring appointment ID {ra.id} for patient {ra.patient.name} has no time_of_day set. Skipping.")
            continue
        
        if ra.start_date is None:
            current_app.logger.warn(f"Recurring appointment ID {ra.id} for patient {ra.patient.name} has no start_date set. Skipping.")
            continue

        series_start_date = ra.start_date
        # series_end_date will be None if ra.end_date is None, otherwise it's ra.end_date
        # This allows for indefinitely recurring appointments if ra.end_date is null
        series_end_date_from_db = ra.end_date 

        iter_start_date = max(calendar_view_start_date, series_start_date)
        # If series_end_date_from_db is None, iterate up to the calendar_view_end_date
        # Otherwise, iterate up to the earlier of calendar_view_end_date or series_end_date_from_db
        iter_end_date = min(calendar_view_end_date, series_end_date_from_db) if series_end_date_from_db else calendar_view_end_date
        
        # Ensure iter_start_date is not after iter_end_date (can happen if series is entirely outside view window)
        if iter_start_date > iter_end_date:
            continue

        current_iter_date = iter_start_date
        while current_iter_date <= iter_end_date:
            is_occurrence_day = False
            if ra.recurrence_type == 'weekly':
                # For weekly, the day is determined by the weekday of the series start_date
                if ra.start_date.weekday() == current_iter_date.weekday():
                    is_occurrence_day = True
            elif ra.recurrence_type == 'daily-mon-fri':
                if current_iter_date.weekday() < 5: # Monday (0) to Friday (4)
                    is_occurrence_day = True
            # Add other recurrence_type checks here if needed (e.g., 'daily', 'monthly')
            else:
                current_app.logger.warn(f"Recurring appointment ID {ra.id} for patient {ra.patient.name} has unknown recurrence_type: {ra.recurrence_type}. Skipping.")
                # Break from while loop for this ra if recurrence_type is unknown to avoid infinite loop on misconfiguration
                break 

            if is_occurrence_day:
                # Assume ra.time_of_day is entered in the system's local timezone (e.g., Europe/Madrid)
                occurrence_datetime_naive = datetime.combine(current_iter_date, ra.time_of_day)
                # Localize the naive datetime to the application's local timezone
                occurrence_datetime_local = LOCAL_TZ.localize(occurrence_datetime_naive)
                # Convert the local time to UTC for consistent storage/FullCalendar representation
                occurrence_datetime_utc = occurrence_datetime_local.astimezone(UTC)
                
                event_start_iso = occurrence_datetime_utc.isoformat()
                event_end_iso = (occurrence_datetime_utc + timedelta(hours=1)).isoformat() 
                
                title = f"{ra.patient.name} - {ra.treatment_type} (Recurring)"

                events.append({
                    'id': f"recurring_{ra.id}_{current_iter_date.strftime('%Y%m%d')}",
                    'title': title,
                    'start': event_start_iso,
                    'end': event_end_iso,
                    'allDay': False,
                    'color': '#fd7e14',
                    'extendedProps': {
                        'type': 'recurring_instance',
                        'recurring_appointment_id': ra.id,
                        'patient_id': ra.patient_id,
                        'patient_name': ra.patient.name,
                        'treatment_type': ra.treatment_type,
                        'recurrence_type': ra.recurrence_type,
                        'series_start': ra.start_date.isoformat(),
                        # Handle if ra.end_date (series_end_date_from_db) is None for the extendedProps
                        'series_end': series_end_date_from_db.isoformat() if series_end_date_from_db else None 
                    }
                })
            current_iter_date += timedelta(days=1)
    
    return jsonify(events)

# If using Flask-Mail for password resets
# @main.route('/reset_password_request', methods=['GET', 'POST'])

@main.route('/api/patients/bulk-delete', methods=['DELETE'])
@login_required
@physio_required
def bulk_delete_patients():
    data = request.get_json()
    patient_ids = data.get('patient_ids', [])

    if not patient_ids:
        return jsonify({'status': 'error', 'message': 'No patient IDs provided'}), 400

    deleted_count = 0
    errors = []

    for patient_id in patient_ids:
        try:
            patient = Patient.query.filter_by(id=patient_id, user_id=current_user.id).first()
            if patient:
                # Before deleting the patient, ensure related records are handled.
                # Option 1: If cascade delete is set up in models, db.session.delete(patient) is enough.
                # Option 2: Manually delete related records if cascade is not set.
                # Example: Treatment.query.filter_by(patient_id=patient.id).delete()
                #          PatientReport.query.filter_by(patient_id=patient.id).delete()
                # For now, assuming cascade or manual deletion of related records is handled elsewhere or not needed.
                
                db.session.delete(patient)
                deleted_count += 1
            else:
                errors.append(f"Patient with ID {patient_id} not found or not accessible.")
        except Exception as e:
            errors.append(f"Error deleting patient ID {patient_id}: {str(e)}")
            db.session.rollback() # Rollback on error for this specific patient

    if not errors:
        try:
            db.session.commit()
            return jsonify({'status': 'success', 'message': f'{deleted_count} patients deleted successfully.'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': f'Failed to commit deletions: {str(e)}'}), 500
    else:
        # If there were errors, no changes are committed overall unless partial success is desired.
        # For now, let's assume all-or-nothing for the commit of successful deletions if errors occurred for others.
        # If some deletions were successful before an error, and you still want to commit them,
        # you'd need to adjust the logic (e.g., commit after each successful deletion or after the loop if some were successful).
        # However, a rollback was already called for individual errors.
        # This part might need refinement based on desired transactional behavior.
        # For simplicity, if any error occurred, we assume we don't commit the ones that might have been staged.
        # A more robust approach would be to collect all patients to delete, then attempt deletion in one transaction.
        db.session.rollback() # Ensure rollback if there were any errors during the loop
        return jsonify({
            'status': 'error',
            'message': 'Some patients could not be deleted.',
            'deleted_count': deleted_count,
            'errors': errors
        }), 400


@main.route('/welcome')
def landing_page():
    """Public marketing landing page."""
    return render_template('landing.html')

