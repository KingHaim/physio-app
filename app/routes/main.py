# app/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from datetime import datetime, timedelta, date, time
from calendar import monthrange
from sqlalchemy import func, extract, or_, case, cast, Float
from app.models import db, Patient, Treatment, TriggerPoint, UnmatchedCalendlyBooking, PatientReport, RecurringAppointment, User, PracticeReport  # Added PracticeReport
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

@main.route('/')
@login_required
@physio_required # <<< ADD DECORATOR
def index():
    # Automatically mark past treatments as completed
    count_treatments = mark_past_treatments_as_completed()

    # Automatically mark inactive patients
    count_patients = mark_inactive_patients()

    if count_treatments > 0:
        flash(f"{count_treatments} past treatment(s) automatically marked as completed.", "info")

    if count_patients > 0:
        flash(f"{count_patients} patient(s) automatically marked as inactive due to inactivity.", "info")

    # Get key metrics
    total_patients = Patient.query.count()
    active_patients = Patient.query.filter_by(status='Active').count()
    pending_review_count = Patient.query.filter_by(status='Pending Review').count()

    # Calculate date ranges for dashboard
    today = datetime.now().date()
    week_end = today + timedelta(days=7)
    month_end = today + timedelta(days=30)

    # Get today's appointments count
    today_appointments = Treatment.query.filter(
        func.date(Treatment.created_at) == today
    ).count()

    # Get upcoming appointments
    upcoming_appointments = Treatment.query.filter(
        Treatment.created_at >= datetime.combine(today, time.min) # Compare with datetime start of today
    ).order_by(Treatment.created_at).limit(5).all()

    # Get recent treatments
    recent_treatments = Treatment.query.order_by(
        Treatment.created_at.desc()
    ).limit(5).all()

    return render_template('index.html',
                           total_patients=total_patients,
                           active_patients=active_patients,
                           pending_review_count=pending_review_count,
                           today_appointments=today_appointments,
                           upcoming_appointments=upcoming_appointments,
                           recent_treatments=recent_treatments,
                           today=today, # Pass date object for display
                           week_end=week_end,
                           month_end=month_end)

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
# @physio_required # <<< DO NOT ADD YET - Needs granular check
def patient_detail(id):
    patient = Patient.query.get_or_404(id)
    # --- Add Access Control ---
    if current_user.role == 'patient' and current_user.patient_id != id:
        flash('You do not have permission to view this patient\'s details.', 'danger')
        return redirect(url_for('main.patient_dashboard')) # Redirect to their own dashboard
    # --- End Access Control ---

    print(f"Treatments for patient {patient.name}:")
    # Eager load patient relationship when querying treatments
    treatments = Treatment.query.filter_by(patient_id=id).options(joinedload(Treatment.patient)).all()
    for treatment in treatments:
        print(f"Treatment Created At: {treatment.created_at}")

    today = datetime.now()

    # Auto-complete logic (consider moving to a scheduled task or background job for performance)
    # For now, keep it here but be mindful of performance on pages with many patients/treatments
    past_treatments = Treatment.query.filter(
        Treatment.patient_id == id,
        Treatment.created_at < today,
        Treatment.status == 'Scheduled'
    ).all()

    if past_treatments:
        count = 0
        for treatment in past_treatments:
            treatment.status = 'Completed'
            count += 1

        # Fix indentation here and add check before commit/flash
        if count > 0:
            try:
                # --- Fix Indentation --- Removed extra comment line
                db.session.commit()
                flash(f"{count} past treatment(s) automatically marked as completed.", "info")
            except Exception as e: # Added except block
                db.session.rollback()
                print(f"Error auto-completing treatments for patient {id}: {e}")
                flash("Error updating past treatment statuses.", "danger")

    # Determine if this is the patient's first visit (based on existing treatments)
    # Fetch count instead of all treatments for efficiency
    # --- Fix Indentation --- Removed extra comment line
    treatment_count = db.session.query(Treatment.id).filter(Treatment.patient_id == id).count()
    is_first_visit = treatment_count == 0
    print(f"Is first visit for patient {id}? {is_first_visit}")

    # Pass treatments loaded earlier
    return render_template('patient_detail.html',
                          patient=patient,
                          today=today,
                          treatments=treatments, # Pass the pre-loaded treatments
                          is_first_visit=is_first_visit)

@main.route('/patient/<int:patient_id>/treatment', methods=['POST'])
@login_required
@physio_required # <<< ADD DECORATOR
def add_treatment(patient_id):
    # Get form data
    treatment_type = request.form.get('treatment_type')
    assessment = request.form.get('assessment')
    notes = request.form.get('notes')
    status = request.form.get('status')
    provider = request.form.get('provider')
    
    # --- Location Logic ---
    location = request.form.get('location')
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
    pain_level = request.form.get('pain_level')
    if pain_level:  # Only convert to int if a value was provided
        pain_level = int(pain_level)
    else:
        pain_level = None  # Set to None if not provided
    
    movement_restriction = request.form.get('movement_restriction')
    body_chart_url = request.form.get('body_chart_url')
    
    # Get new financial fields (these might be set by the location logic or form)
    visit_type = request.form.get('visit_type') 
    fee_str = request.form.get('fee_charged')
    fee_charged = float(fee_str) if fee_str else None
    payment_method = request.form.get('payment_method')
    
    # Get trigger points / evaluation data
    evaluation_data = None
    trigger_data_str = request.form.get('trigger_points_data') or request.form.get('evaluation_data')
    if trigger_data_str:
        try:
            evaluation_data = json.loads(trigger_data_str)
        except json.JSONDecodeError:
            flash('Error decoding trigger points data.', 'danger')
            # Decide how to handle this - maybe redirect back with error?
            # For now, just log and continue without trigger points
            print(f"ERROR: Invalid JSON for trigger points data for patient {patient_id}")
            evaluation_data = None # Ensure it's reset
    
    # Get date field if provided
    date_str = request.form.get('date')
    created_at = None
    if date_str:
        try:
            # Try parsing Date first, then DateTime
            try:
                 created_at = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                 # --- Fix Indentation --- Removed extra comment line
                 created_at = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            # If date parsing fails, use current datetime
            flash('Invalid date format provided. Using current date/time.', 'warning')
            created_at = datetime.now()
    else:
        created_at = datetime.now()
    
    # Create new treatment
    treatment = Treatment(
        patient_id=patient_id,
        treatment_type=treatment_type,
        assessment=assessment,
        notes=notes,
        status=status,
        provider=provider,
        pain_level=pain_level,  # This can be None
        movement_restriction=movement_restriction,
        body_chart_url=body_chart_url,
        created_at=created_at,
        evaluation_data=evaluation_data,  # Add the evaluation_data
        location=location,                # Add determined location
        visit_type=visit_type,            # Add visit type
        fee_charged=fee_charged,          # Add fee
        payment_method=payment_method     # Add payment method
    )
    
    db.session.add(treatment)
    # Commit here to get treatment.id for trigger points
    try:
        # --- Fix Indentation --- Removed extra comment line
        db.session.commit()
    except Exception as e: # Added except block
        db.session.rollback()
        flash(f'Error adding treatment: {e}', 'danger')
        return redirect(url_for('main.patient_detail', id=patient_id)) # Redirect back on error
    
    # If we have trigger points data, create those records too
    if evaluation_data and isinstance(evaluation_data, list): # Ensure it's a list
        try:
            # --- Fix Indentation Start --- Removed extra comment line
            for point_data in evaluation_data:
                if isinstance(point_data, dict): # Check if item is a dictionary
                    trigger_point = TriggerPoint(
                        treatment_id=treatment.id,
                        location_x=float(point_data.get('x', 0)), # Use .get with default
                        location_y=float(point_data.get('y', 0)), # Use .get with default
                        type=point_data.get('type', 'unknown'),   # Use .get with default
                        muscle=point_data.get('muscle', ''),
                        intensity=int(point_data['intensity']) if point_data.get('intensity') else None,
                        symptoms=point_data.get('symptoms', ''),
                        referral_pattern=point_data.get('referral', '')
                    )
                    db.session.add(trigger_point)
            db.session.commit() # Commit trigger points
            # --- Fix Indentation End --- Removed extra comment line
        except Exception as e: # Added except block
            db.session.rollback() # Rollback trigger points if error
            # Optionally delete the treatment itself or leave it without points?
            # Let's leave the treatment but flash an error about points
            flash(f'Treatment added, but failed to save trigger points: {e}', 'warning')
            print(f"ERROR: Failed adding trigger points for treatment {treatment.id}: {e}")
    
    flash('Treatment added successfully', 'success')
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
    patient = rule.patient
    
    if request.method == 'POST':
        try:
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            time_str = request.form.get('time_of_day')
            
            rule.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else rule.start_date
            rule.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
            rule.time_of_day = datetime.strptime(time_str, '%H:%M').time() if time_str else rule.time_of_day
            
            rule.recurrence_type = request.form.get('recurrence_type', rule.recurrence_type)
            rule.treatment_type = request.form.get('treatment_type', rule.treatment_type)
            rule.notes = request.form.get('notes')
            rule.location = request.form.get('location') # Update to read from hidden input later if needed
            rule.provider = request.form.get('provider')
            fee_str = request.form.get('fee_charged')
            rule.fee_charged = float(fee_str) if fee_str else None
            rule.payment_method = request.form.get('payment_method')
            rule.is_active = request.form.get('is_active') == 'on'

            # Basic validation
            if not all([rule.start_date, rule.time_of_day, rule.recurrence_type, rule.treatment_type]):
                flash('Start Date, Time, Recurrence Type, and Treatment Type are required.', 'danger')
            else:
                db.session.commit()
                flash('Recurring appointment rule updated successfully!', 'success')
                return redirect(url_for('main.patient_detail', id=patient.id))

        except ValueError:
             flash('Invalid date or time format. Please use YYYY-MM-DD and HH:MM.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating recurring rule: {e}', 'danger')
            print(f"Error updating recurring rule {id}: {e}")
            
    # GET request - Pass the existing rule to the template
    return render_template('edit_recurring_appointment.html', rule=rule, patient=patient)

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

    appointments = Treatment.query.filter(
        Treatment.created_at.between(start_date, end_date)
    ).order_by(Treatment.created_at).all()

    patients = Patient.query.filter_by(status='Active').all()

    return render_template('appointments.html',
                           appointments=appointments,
                           patients=patients,
                           start_date=start_date,
                           end_date=end_date)

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
# @physio_required # <<< DO NOT ADD YET - Needs granular check
def patient_treatments(id):
    patient = Patient.query.get_or_404(id)
    # --- Add Access Control --- 
    if current_user.role == 'patient' and current_user.patient_id != id:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.patient_dashboard'))
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

    query = Patient.query

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
                           status_filter=status_filter)

@main.route('/patient/<int:id>/report')
@login_required
# @physio_required # <<< DO NOT ADD YET - Needs granular check
def patient_report(id):
    patient = Patient.query.get_or_404(id)
    # --- Add Access Control --- 
    if current_user.role == 'patient' and current_user.patient_id != id:
        flash('You do not have permission to view this report.', 'danger')
        return redirect(url_for('main.patient_dashboard'))
    # --- End Access Control ---
    
    # Check if a specific report ID was requested
    report_id = request.args.get('report_id')
    
    if report_id:
        report = PatientReport.query.get_or_404(report_id)
        if report.patient_id != patient.id:
            flash('Report does not belong to this patient.', 'danger')
            return redirect(url_for('main.patient_detail', id=id))
    else:
        # Get the most recent *non-homework* report if no ID specified
        report = PatientReport.query.filter(
            PatientReport.patient_id == id,
            PatientReport.report_type != 'Exercise Homework' # Exclude homework from default view
        ).order_by(PatientReport.generated_date.desc()).first()
    
    # If still no main report found (maybe only homework exists?), get the absolute latest one
    if not report:
        report = PatientReport.query.filter_by(
            patient_id=id
        ).order_by(PatientReport.generated_date.desc()).first()
    
    # If *still* no report, redirect
    if not report:
        flash('No reports found for this patient.', 'warning')
        return redirect(url_for('main.patient_detail', id=id))
    
    # Get all reports for the dropdown (including homework)
    all_reports = PatientReport.query.filter_by(
        patient_id=id
    ).order_by(PatientReport.generated_date.desc()).all()
    
    # Get specifically the Exercise Homework reports
    exercise_homework_reports = PatientReport.query.filter_by(
        patient_id=id,
        report_type='Exercise Homework'
    ).order_by(PatientReport.generated_date.desc()).all()
    
    return render_template('patient_report.html', 
                          patient=patient, 
                          report=report, # The currently viewed report
                          all_reports=all_reports, # For dropdown
                          exercise_homework_reports=exercise_homework_reports) # For bottom section

@main.route('/calendly/review')
@login_required
@physio_required # <<< ADD DECORATOR
def review_calendly_bookings():
    unmatched_bookings = UnmatchedCalendlyBooking.query.filter_by(status='Pending').all()
    return render_template('calendly_review.html', unmatched_bookings=unmatched_bookings)

@main.route('/treatment/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@physio_required # <<< ADD DECORATOR
def edit_treatment(id):
    treatment = Treatment.query.get_or_404(id)
    patient = treatment.patient
    
    print(f"DEBUG: Raw treatment.evaluation_data for ID {id}: {treatment.evaluation_data!r}") 
    
    if request.method == 'POST':
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
        
        # Handle created_at
        if request.form.get('created_at'):
            treatment.created_at = datetime.strptime(
                request.form['created_at'], '%Y-%m-%d'
            )
        else:
            # Don't set to None if not provided, keep existing value
            pass
            
        # Handle pain level if provided
        if request.form.get('pain_level'):
            treatment.pain_level = int(request.form['pain_level'])
            
        # Handle movement restriction if provided
        if request.form.get('movement_restriction'):
            treatment.movement_restriction = request.form['movement_restriction']
        
        # Handle new financial fields
        treatment.location = request.form.get('location')
        treatment.visit_type = request.form.get('visit_type')
        fee_str = request.form.get('fee_charged')
        treatment.fee_charged = float(fee_str) if fee_str else None
        treatment.payment_method = request.form.get('payment_method')
        
        # Handle trigger points data
        if request.form.get('trigger_points_data'):
            trigger_data_string = request.form.get('trigger_points_data')
            print(f"DEBUG: Received trigger_points_data: {trigger_data_string}") # Keep for server log
            try:
                treatment.evaluation_data = json.loads(trigger_data_string)
                
                # Update or create trigger points in the database
                TriggerPoint.query.filter_by(treatment_id=treatment.id).delete()
                for point_data in treatment.evaluation_data:
                    trigger_point = TriggerPoint(
                        treatment_id=treatment.id,
                        location_x=float(point_data['x']),
                        location_y=float(point_data['y']),
                        type=point_data['type'],
                        muscle=point_data.get('muscle', ''),
                        intensity=int(point_data['intensity']) if point_data.get('intensity') else None,
                        symptoms=point_data.get('symptoms', ''),
                        referral_pattern=point_data.get('referral', '')
                    )
                    db.session.add(trigger_point)
                # Note: Trigger points are committed in the final try block below
            except json.JSONDecodeError as e:
                # Log the error and the problematic string to the error log
                print(f"ERROR: JSONDecodeError processing trigger points for treatment {id}")
                print(f"ERROR_STRING: {trigger_data_string}")
                print(f"ERROR_DETAILS: {e}")
                flash('Error processing trigger point data. Please check the format or report this issue.', 'danger')
                db.session.rollback()
                original_treatment_data = Treatment.query.get(id) # Get original data again after rollback
                return render_template('edit_treatment.html',
                                      treatment={ # Rebuild the context for the template
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
                                          'evaluation_data': original_treatment_data.evaluation_data if original_treatment_data else [], # Use original data
                                          'trigger_points': treatment.trigger_points,
                                          'body_chart_url': treatment.body_chart_url
                                      },
                                      patient=patient)
            except Exception as e: # Catch other potential errors during trigger point processing
                print(f"ERROR: Unexpected error processing trigger points for treatment {id}: {e}")
                flash('An unexpected error occurred while processing trigger points.', 'danger')
                db.session.rollback()
                original_treatment_data = Treatment.query.get(id)
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
                                          'evaluation_data': original_treatment_data.evaluation_data if original_treatment_data else [],
                                          'trigger_points': treatment.trigger_points,
                                          'body_chart_url': treatment.body_chart_url
                                      },
                                      patient=patient)
        
        # Final commit for all changes (basic info + trigger points if processed)
        try:
            db.session.commit()
            flash(f'Treatment session on {treatment.created_at.strftime("%Y-%m-%d")} updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error saving treatment changes. Please try again.', 'danger')
            print(f"Error committing changes for treatment {id}: {e}")
            # Re-render the edit form if commit fails
            return render_template('edit_treatment.html',
                                  treatment={ # Rebuild context
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
                                      'evaluation_data': treatment.evaluation_data,
                                      'trigger_points': treatment.trigger_points,
                                      'body_chart_url': treatment.body_chart_url
                                  },
                                  patient=patient)

        return redirect(url_for('main.patient_detail', id=patient.id))
    
    # --- GET Request Logic ---
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

    return render_template('edit_treatment.html', 
                          treatment=template_context, 
                          patient=patient,
                          has_past_treatments=has_past_treatments) # Pass the flag

@main.route('/treatment/<int:id>/view')
@login_required
# @physio_required # <<< DO NOT ADD YET - Needs granular check
def view_treatment(id):
    treatment = Treatment.query.get_or_404(id)
    patient = treatment.patient
    # --- Add Access Control --- 
    if current_user.role == 'patient' and current_user.patient_id != patient.id:
        flash('You do not have permission to view this treatment.', 'danger')
        return redirect(url_for('main.patient_dashboard'))
    # --- End Access Control ---
    
    # Add a debug statement to check what treatment data is available
    print(f"Viewing treatment {id}: Type={treatment.treatment_type}, Notes={treatment.notes}, Status={treatment.status}")
    
    # Create a mapped treatment object that includes both original and mapped fields
    # This ensures backward compatibility with templates that might use either naming convention
    mapped_treatment = {
        'id': treatment.id,
        'created_at': treatment.created_at,
        'description': treatment.treatment_type,  # Map treatment_type to description
        'progress_notes': treatment.notes,        # Map notes to progress_notes
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
    
    # Pass patient, now, and the flag to the template
    return render_template('new_treatment_page.html', 
                          patient=patient, 
                          now=now,
                          has_past_treatments=has_past_treatments)

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
    latest_report = PracticeReport.query.order_by(PracticeReport.generated_at.desc()).first()
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

    # --- Data JUST for Summary Cards ---
    total_patients = Patient.query.count()
    active_patients = Patient.query.filter(Patient.status == 'Active').count()
    inactive_patients = total_patients - active_patients
    total_treatments = Treatment.query.count()
    avg_treatments = round(total_treatments / total_patients, 1) if total_patients else 0
    
    # Monthly Revenue Calc...
    monthly_revenue = db.session.query(
        func.strftime('%Y-%m', Treatment.created_at).label('month'),
        func.sum(Treatment.fee_charged).label('monthly_total')
    ).filter(Treatment.fee_charged.isnot(None)).group_by('month').all()
    total_revenue = sum(m.monthly_total for m in monthly_revenue if m.monthly_total)
    num_months = len(monthly_revenue)
    avg_monthly_revenue = total_revenue / num_months if num_months else 0
    
    # CostaSpine Calcs...
    costaspine_revenue_query = db.session.query(
        func.sum(Treatment.fee_charged).label('total_costaspine_revenue')
    ).filter(
        Treatment.location == 'CostaSpine Clinic',
        Treatment.fee_charged.isnot(None)
    ).scalar()
    costaspine_revenue_data = costaspine_revenue_query or 0
    costaspine_service_fee = costaspine_revenue_data * 0.30

    # Autonomo Calcs...
    total_autonomo_contribution = 0
    monthly_data_autonomo = db.session.query(
        # ... autonomo query ...
        func.strftime('%Y-%m', Treatment.created_at).label('month'),
        func.strftime('%Y', Treatment.created_at).label('year'),
        func.sum(Treatment.fee_charged).label('monthly_total_revenue'),
        func.sum(
            case((Treatment.location == 'CostaSpine Clinic', Treatment.fee_charged), else_=0)
        ).label('monthly_costaspine_revenue')
    ).filter(
        Treatment.fee_charged.isnot(None),
        Treatment.created_at.isnot(None)
    ).group_by('year', 'month').order_by('year', 'month').all()

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
                          costaspine_revenue=costaspine_revenue_data,
                          costaspine_service_fee=costaspine_service_fee,
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
@login_required # Ensure user is logged in
# @physio_required # <<< DO NOT ADD YET - Needs granular check
def download_report_pdf(report_id):
    """Generates and serves a PDF version of a specific report."""
    report = PatientReport.query.get_or_404(report_id)
    patient = report.patient # Assuming relationship is set up
    # --- Add Access Control --- 
    if current_user.role == 'patient' and current_user.patient_id != patient.id:
        flash('You do not have permission to download this report.', 'danger')
        return redirect(url_for('main.patient_dashboard'))
    # --- End Access Control ---

    # Convert report content from Markdown to HTML
    try:
        report_html = markdown.markdown(report.content)
    except Exception as e:
        print(f"Error converting markdown for report {report_id}: {e}")
        flash('Error generating PDF: Could not parse report content.', 'danger')
        return redirect(url_for('main.patient_report', id=patient.id, report_id=report.id))

    # Read the CSS content
    css_content = ""
    try:
        # Construct the absolute path to the CSS file
        css_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'report.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
    except FileNotFoundError:
        print("Warning: report.css not found. PDF will have basic styling.")
    except Exception as e:
        print(f"Error reading report.css: {e}")

    # Basic HTML structure for the PDF
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Report: {patient.name}</title>
        <style>
            {css_content} /* Inject the CSS content here */
        </style>
    </head>
    <body>
        <div class="report-content">
            {report_html}
        </div>
    </body>
    </html>
    """

    # Generate PDF
    pdf_file = BytesIO()
    try:
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_file)
        if pisa_status.err:
            raise Exception(f"pisa error: {pisa_status.err}")
    except Exception as e:
        print(f"Error creating PDF for report {report_id}: {e}")
        flash('Error generating PDF. Please check report content or server logs.', 'danger')
        return redirect(url_for('main.patient_report', id=patient.id, report_id=report.id))

    pdf_file.seek(0)

    # Create response
    response = make_response(pdf_file.read())
    response.headers['Content-Type'] = 'application/pdf'
    # Suggest filename for download
    filename = f"Report_{patient.name.replace(' ', '_')}_{report.generated_date.strftime('%Y%m%d')}.pdf"
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response

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
        monthly_treatments = Treatment.query.filter(
            Treatment.created_at >= month_start_date,
            Treatment.created_at <= month_end_date,
            Treatment.status == 'Completed',
            Treatment.fee_charged > 0
        ).all()

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
            # Format min_base for display
            min_base_display = f"€{min_base_value:,.2f}"
            # Calculate the estimated monthly contribution (31.4%)
            monthly_contribution = min_base_value * 0.314
            
            upper_bound = current_bracket['upper']
            if upper_bound == float('inf'):
                diff_to_upper = "Top Bracket"
            else:
                diff = upper_bound - m_net
                # Format diff_to_upper as currency
                diff_to_upper = f"€{diff:,.2f}"
        elif m_net > 0: # Handle case where net is positive but doesn't match a bracket
             bracket_desc = "Error: No bracket found"

        # Final Net Revenue for the month (After all expenses and contributions)
        m_net_final = m_net - monthly_contribution

        # Store monthly breakdown (Updated)
        monthly_data[month] = {
            'month_name': month_start_date.strftime('%B'),
            'net_revenue': m_net, # Revenue used for bracket calc
            'bracket': bracket_desc,
            'min_base': min_base_display,
            'monthly_contribution': monthly_contribution,
            'fixed_expenses': TOTAL_FIXED_MONTHLY_EXPENSES, # Store monthly fixed expenses
            'net_revenue_final': m_net_final, # Store the final net after contribution
            'diff_to_upper': diff_to_upper
        }

        # --- Aggregate into quarterly and annual data (Updated) ---
        quarterly_data[q_key]['revenue'] += m_revenue
        quarterly_data[q_key]['costaspine_revenue'] += m_costaspine_revenue
        quarterly_data[q_key]['costaspine_fee'] += m_costaspine_fee
        quarterly_data[q_key]['tax'] += monthly_contribution # Sum autonomo contributions
        quarterly_data[q_key]['fixed_expenses'] += TOTAL_FIXED_MONTHLY_EXPENSES # Sum fixed expenses
        # Recalculate Net for the quarter
        quarterly_data[q_key]['net'] = quarterly_data[q_key]['revenue'] - quarterly_data[q_key]['costaspine_fee'] - quarterly_data[q_key]['tax'] - quarterly_data[q_key]['fixed_expenses']

        quarterly_data['annual']['revenue'] += m_revenue
        quarterly_data['annual']['costaspine_revenue'] += m_costaspine_revenue
        quarterly_data['annual']['costaspine_fee'] += m_costaspine_fee
        quarterly_data['annual']['tax'] += monthly_contribution # Sum autonomo contributions
        quarterly_data['annual']['fixed_expenses'] += TOTAL_FIXED_MONTHLY_EXPENSES # Sum fixed expenses
        # Recalculate Net for the year
        quarterly_data['annual']['net'] = quarterly_data['annual']['revenue'] - quarterly_data['annual']['costaspine_fee'] - quarterly_data['annual']['tax'] - quarterly_data['annual']['fixed_expenses']

    return render_template(
        'financials.html',
        data=quarterly_data, # Pass quarterly/annual data
        monthly_breakdown=monthly_data, # Pass new monthly data
        selected_year=selected_year,
        available_years=sorted(list(set(available_years)), reverse=True), # Ensure unique and sorted
        tax_year=2025 # Pass the year the brackets apply to
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
        treatments_to_review = Treatment.query.join(Patient).filter(
            Treatment.status == 'Completed', # Must be completed
            or_(
                Treatment.fee_charged.is_(None),
                Treatment.fee_charged == 0,
                Treatment.payment_method.is_(None),
                Treatment.payment_method == ''
            )
        ).options(
            db.joinedload(Treatment.patient) # Eager load patient data
        ).order_by(
            Treatment.created_at.asc() # Show oldest first
        ).all()

        return render_template('review_payments.html', treatments=treatments_to_review)

    except Exception as e:
        print(f"Error loading review payments page: {e}")
        flash('Could not load payment review page. Please try again.', 'danger')
        return redirect(url_for('main.index'))

@main.route('/patient/<int:id>/edit', methods=['GET', 'POST'])
@login_required # Asegurar que solo usuarios logueados puedan editar
# @physio_required # <<< DO NOT ADD YET - Needs granular check
def edit_patient(id):
    # Cargar paciente y su usuario asociado (si existe) para evitar queries extra
    patient = Patient.query.options(joinedload(Patient.user)).get_or_404(id) 
    # --- Add Access Control --- 
    if current_user.role == 'patient' and current_user.patient_id != id:
        flash('You do not have permission to edit this patient\'s details.', 'danger')
        return redirect(url_for('main.patient_dashboard'))
    # --- End Access Control ---
    
    if request.method == 'POST':
        # --- Actualizar Información Básica del Paciente --- 
        try:
            patient.name = request.form['name']
            dob_str = request.form.get('date_of_birth')
            # Manejar fecha de nacimiento vacía o inválida
            patient.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
            patient.contact = request.form['contact']
            patient.diagnosis = request.form['diagnosis']
            patient.treatment_plan = request.form['treatment_plan']
            patient.notes = request.form['notes']
            patient.status = request.form['status']
        except ValueError:
             db.session.rollback()
             flash('Invalid date format for Date of Birth. Please use YYYY-MM-DD.', 'danger')
             return render_template('edit_patient.html', patient=patient)
        except Exception as e:
            db.session.rollback()
            flash(f'Error parsing basic patient information: {e}', 'danger')
            print(f"Error parsing patient info {id}: {e}") # Log para debug
            return render_template('edit_patient.html', patient=patient)
            
        # --- Actualizar Acceso al Portal del Paciente --- 
        patient_email = request.form.get('patient_email', '').strip().lower()
        patient_password = request.form.get('patient_password', '') # Obtener contraseña (puede estar vacía)
        
        user_changed = False # Flag para saber si mostrar mensaje de portal actualizado
        try:
            if patient_email: # Si se proporciona un email
                # Comprobar si el email está siendo cambiado a uno que ya existe para *otro* usuario
                existing_user_check = User.query.filter(
                    User.email == patient_email, 
                    User.id != (patient.user.id if patient.user else -1) # Excluir al usuario actual del paciente (si existe)
                ).first()
                
                if existing_user_check:
                    flash('That email address is already in use by another user.', 'danger')
                    # No hacer rollback aquí, los cambios básicos del paciente pueden ser válidos
                    return render_template('edit_patient.html', patient=patient) 
                
                if patient.user: 
                    # El paciente YA tiene una cuenta de usuario
                    # Actualizar email si ha cambiado
                    if patient.user.email != patient_email:
                        patient.user.email = patient_email
                        patient.user.username = patient_email # Mantener username sincronizado con email
                        user_changed = True
                    # Actualizar contraseña si se proporcionó una nueva
                    if patient_password:
                        patient.user.set_password(patient_password)
                        user_changed = True
                        
                else: 
                    # El paciente NO tiene cuenta de usuario, hay que crearla
                    # Se requiere contraseña para crear una nueva cuenta
                    if not patient_password:
                        flash('A password is required to create a new patient login.', 'danger')
                        # No hacer rollback, cambios básicos pueden ser válidos
                        return render_template('edit_patient.html', patient=patient)
                    
                    # Crear nuevo usuario
                    new_user = User(
                        username=patient_email, # Usar email como username
                        email=patient_email,
                        role='patient', # Asignar rol paciente
                        patient_id=patient.id # Vincular al paciente
                    )
                    new_user.set_password(patient_password)
                    db.session.add(new_user)
                    user_changed = True # Indicar que se creó/modificó usuario
                    # No es necesario asignar patient.user = new_user aquí, 
                    # SQLAlchemy maneja la relación al hacer commit si patient_id está puesto
                    
            elif patient.user and patient_password: 
                # Si el campo email está vacío, pero el paciente tiene usuario y se proporcionó contraseña nueva
                # Actualizar solo la contraseña del usuario existente
                patient.user.set_password(patient_password)
                user_changed = True
                
            # elif not patient_email and patient.user:
                # Opcional: Lógica si se borra el email. Podríamos desactivar/borrar el usuario.
                # Por ahora, no hacemos nada, mantenemos la cuenta existente aunque se borre el email del form.
                # pass 

            # --- Hacer Commit de Todos los Cambios (Paciente y/o Usuario) --- 
            db.session.commit() 
            flash('Patient information updated successfully!' + (' Portal access updated.' if user_changed else ''), 'success')
            return redirect(url_for('main.patient_detail', id=patient.id))
            
        except Exception as e:
            db.session.rollback() # Hacer rollback si hay error al manejar el usuario
            flash(f'Error updating patient portal access: {str(e)}', 'danger')
            print(f"Error updating user access for patient {id}: {e}") # Log para debug
            return render_template('edit_patient.html', patient=patient) # Re-renderizar en caso de error
            
    # --- Petición GET --- 
    # Renderizar la plantilla pasando el objeto paciente (que ya tiene el usuario cargado si existe)
    return render_template('edit_patient.html', patient=patient)

@main.route('/patient/new', methods=['GET', 'POST'])
@login_required
@physio_required # <<< ADD DECORATOR
def new_patient():
    if request.method == 'POST':
        # --- Basic Patient Info ---
        name = request.form['name']
        date_of_birth_str = request.form.get('date_of_birth')
        contact = request.form['contact']
        diagnosis = request.form['diagnosis']
        treatment_plan = request.form.get('treatment_plan')
        notes = request.form.get('notes')
        
        try:
            date_of_birth = datetime.strptime(date_of_birth_str, '%Y-%m-%d').date() if date_of_birth_str else None
        except ValueError:
            flash('Invalid date format for Date of Birth. Please use YYYY-MM-DD.', 'danger')
            return render_template('new_patient.html')

        new_patient_obj = Patient(
            name=name,
            date_of_birth=date_of_birth,
            contact=contact,
            diagnosis=diagnosis,
            treatment_plan=treatment_plan,
            notes=notes,
            status='Active' # Default status for new patients
        )
        
        # --- Optional Patient Portal User ---
        patient_email = request.form.get('patient_email', '').strip().lower()
        patient_password = request.form.get('patient_password', '')

        new_user = None
        if patient_email:
            # Check if email already exists
            existing_user = User.query.filter_by(email=patient_email).first()
            if existing_user:
                flash('Email address already in use. Cannot create patient portal account with this email.', 'danger')
                # Don't proceed with saving patient if user creation failed due to email clash
                return render_template('new_patient.html', 
                                       # Pass back form data to avoid re-entry (optional but good UX)
                                       name=name, date_of_birth=date_of_birth_str, contact=contact, 
                                       diagnosis=diagnosis, treatment_plan=treatment_plan, notes=notes,
                                       patient_email=patient_email) 
            
            if not patient_password:
                flash('Password is required when providing an email for patient portal access.', 'danger')
                # Don't proceed if password missing for user creation
                return render_template('new_patient.html', 
                                       name=name, date_of_birth=date_of_birth_str, contact=contact, 
                                       diagnosis=diagnosis, treatment_plan=treatment_plan, notes=notes,
                                       patient_email=patient_email)

            new_user = User(
                username=patient_email, # Use email as username for simplicity
                email=patient_email,
                role='patient'
            )
            new_user.set_password(patient_password)
        
        # --- Save Patient (and User if created) ---
        try:
            db.session.add(new_patient_obj)
            # Flush to get the new_patient_obj.id before adding user (if needed)
            # Not strictly necessary if using backref, but good practice
            db.session.flush() 
            
            if new_user:
                new_user.patient_id = new_patient_obj.id # Link user to the patient
                db.session.add(new_user)
                
            db.session.commit()
            flash(f'Patient {name} created successfully!' + (' Portal access enabled.' if new_user else ''), 'success')
            return redirect(url_for('main.patient_detail', id=new_patient_obj.id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating patient: {str(e)}', 'danger')
            print(f"Error creating patient: {e}") # Log for debugging
            return render_template('new_patient.html',
                                   name=name, date_of_birth=date_of_birth_str, contact=contact, 
                                   diagnosis=diagnosis, treatment_plan=treatment_plan, notes=notes,
                                   patient_email=patient_email) 

    # GET request
    return render_template('new_patient.html')

# --- Patient Dashboard Route ---
@main.route('/patient/dashboard')
@login_required
def patient_dashboard():
    if current_user.role != 'patient':
        # Redirect non-patients away from the patient dashboard
        flash('Access denied. Redirecting to main dashboard.', 'warning')
        return redirect(url_for('main.index'))
        
    # Ensure the patient user is linked to a patient record
    if not current_user.patient_id or not current_user.patient:
        flash('Error: Your user account is not linked to a patient record.', 'danger')
        # Log them out or redirect to an error page?
        logout_user()
        return redirect(url_for('auth.login'))
        
    # Get the linked patient
    patient = current_user.patient
    
    # Find the most recent 'Exercise Homework' report for this patient
    latest_homework = PatientReport.query.filter_by(
        patient_id=patient.id,
        report_type='Exercise Homework'
    ).order_by(PatientReport.generated_date.desc()).first()
    
    # --- Fetch Upcoming Appointments ---
    today_start = datetime.combine(date.today(), time.min)
    upcoming_appointments = Treatment.query.filter(
        Treatment.patient_id == patient.id,
        Treatment.created_at >= today_start, # From start of today onwards
        Treatment.status == 'Scheduled'      # Only show scheduled
    ).order_by(Treatment.created_at.asc()).limit(5).all() # Limit for display
    # --- End Fetch ---
    
    # --- Fetch Past Homework (excluding the latest) ---
    past_homework_query = PatientReport.query.filter(
        PatientReport.patient_id == patient.id,
        PatientReport.report_type == 'Exercise Homework'
    )
    if latest_homework:
        past_homework_query = past_homework_query.filter(PatientReport.id != latest_homework.id)
        
    past_homework_reports = past_homework_query.order_by(PatientReport.generated_date.desc()).all()
    # --- End Fetch ---

    return render_template('patient_dashboard.html', 
                           latest_homework=latest_homework,
                           upcoming_appointments=upcoming_appointments,
                           past_homework_reports=past_homework_reports) # Pass past homework
# --- End Patient Dashboard ---

# --- View Homework Route (Patient Only) ---
@main.route('/patient/homework/<int:report_id>')
@login_required
def view_homework(report_id):
    # 1. Ensure user is a patient
    if current_user.role != 'patient':
        flash('Access Denied.', 'danger')
        return redirect(url_for('main.index')) # Or appropriate redirect for non-patients
        
    # 2. Fetch the report
    report = PatientReport.query.get_or_404(report_id)
    
    # 3. Security Checks:
    #    - Does the report belong to the logged-in patient?
    #    - Is the report type actually 'Exercise Homework'?
    if report.patient_id != current_user.patient_id or report.report_type != 'Exercise Homework':
        flash('You do not have permission to view this report.', 'danger')
        return redirect(url_for('main.patient_dashboard'))
        
    # 4. Render the dedicated homework template
    return render_template('view_homework.html', report=report)
# --- End View Homework ---

# --- NEW Route to Generate Report --- 
@main.route('/analytics/generate', methods=['POST']) # Use POST for action
@login_required
@physio_required
def generate_new_analytics_report():
    print("Generating new analytics report...") # Log start
    try:
        # --- Gather Data (Replicate the data gathering needed for the AI function) ---
        total_patients = Patient.query.count()
        active_patients = Patient.query.filter(Patient.status == 'Active').count()
        total_treatments = Treatment.query.count()
        avg_treatments = round(total_treatments / total_patients, 1) if total_patients else 0
        
        monthly_revenue_query = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.sum(Treatment.fee_charged).label('monthly_total')
        ).filter(Treatment.fee_charged.isnot(None)).group_by('month').all()
        total_revenue = sum(m.monthly_total for m in monthly_revenue_query if m.monthly_total)
        num_months = len(monthly_revenue_query)
        avg_monthly_revenue = total_revenue / num_months if num_months else 0
        
        common_diagnoses_query = db.session.query(
            Patient.diagnosis, 
            func.count(Patient.id).label('count')
        ).filter(Patient.diagnosis.isnot(None), Patient.diagnosis != '').group_by(Patient.diagnosis).order_by(func.count(Patient.id).desc()).limit(10).all()
        common_diagnoses = [{'diagnosis': d.diagnosis, 'count': d.count} for d in common_diagnoses_query]
        
        revenue_by_visit_type_query = db.session.query(
            Treatment.treatment_type,
            func.sum(Treatment.fee_charged).label('total_fee')
        ).filter(Treatment.fee_charged.isnot(None)).group_by(Treatment.treatment_type).order_by(func.sum(Treatment.fee_charged).desc()).all()
        revenue_by_visit_type = [{'type': r.treatment_type, 'revenue': r.total_fee} for r in revenue_by_visit_type_query]
        
        treatments_by_month_query = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.count(Treatment.id).label('count')
        ).group_by('month').order_by('month').all()
        treatments_by_month = [{'month': t.month, 'count': t.count} for t in treatments_by_month_query]
        
        patients_by_month_query = db.session.query(
            func.strftime('%Y-%m', Patient.created_at).label('month'),
            func.count(Patient.id).label('count')
        ).group_by('month').order_by('month').all()
        patients_by_month = [{'month': p.month, 'count': p.count} for p in patients_by_month_query]
        
        patients_with_dob = Patient.query.filter(Patient.date_of_birth.isnot(None)).all()
        age_brackets = {
            "0-17": 0,
            "18-30": 0,
            "31-45": 0,
            "46-60": 0,
            "61+": 0,
            "Unknown": 0
        }
        for p in patients_with_dob:
            age = calculate_age(p.date_of_birth)
            if age is None:
                age_brackets["Unknown"] += 1
            elif age <= 17:
                age_brackets["0-17"] += 1
            elif age <= 30:
                age_brackets["18-30"] += 1
            elif age <= 45:
                age_brackets["31-45"] += 1
            elif age <= 60:
                age_brackets["46-60"] += 1
            else:
                age_brackets["61+"] += 1
        unknown_dob_count = Patient.query.filter(Patient.date_of_birth.is_(None)).count()
        age_brackets["Unknown"] += unknown_dob_count
        age_distribution_data = age_brackets
        
        ai_analytics_data = {
            'total_patients': total_patients,
            'active_patients': active_patients,
            'total_treatments': total_treatments,
            'avg_treatments': avg_treatments,
            'avg_monthly_revenue': avg_monthly_revenue,
            'common_diagnoses': common_diagnoses, 
            'revenue_by_visit_type': revenue_by_visit_type, 
            'treatments_by_month': treatments_by_month, 
            'patients_by_month': patients_by_month, 
            'age_distribution': age_distribution_data, 
        }

        # --- Generate the report using the existing helper ---
        report_content = generate_deepseek_report(ai_analytics_data)
        
        # --- Save the new report to the database ---
        if not report_content.startswith("Error:"):
            new_report = PracticeReport(content=report_content, generated_at=datetime.utcnow())
            db.session.add(new_report)
            db.session.commit()
            flash('New AI practice insights generated successfully!', 'success')
            print("New report saved successfully.")
        else:
            # Don't save if there was an error generating
            flash(f'Failed to generate new insights: {report_content}', 'danger')
            print(f"Failed to generate/save report: {report_content}")

    except Exception as e:
        db.session.rollback()
        flash(f'An unexpected error occurred while generating the report: {str(e)}', 'danger')
        print(f"Error in /analytics/generate: {e}") # Log the exception
        
    return redirect(url_for('main.analytics')) # Redirect back to analytics page

# --- NEW: API Endpoints for Chart Data ---

@main.route('/api/analytics/treatments-by-month')
@login_required
@physio_required
def api_treatments_by_month():
    try:
        data = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.count(Treatment.id).label('count')
        ).group_by('month').order_by('month').all()
        # Convert Row objects to list of dicts for JSON
        result = [{'month': row.month, 'count': row.count} for row in data]
        return jsonify(result)
    except Exception as e:
        print(f"Error in /api/analytics/treatments-by-month: {e}")
        return jsonify({"error": "Failed to fetch treatments by month data"}), 500

@main.route('/api/analytics/patients-by-month')
@login_required
@physio_required
def api_patients_by_month():
    try:
        data = db.session.query(
            func.strftime('%Y-%m', Patient.created_at).label('month'),
            func.count(Patient.id).label('count')
        ).group_by('month').order_by('month').all()
        result = [{'month': row.month, 'count': row.count} for row in data]
        return jsonify(result)
    except Exception as e:
        print(f"Error in /api/analytics/patients-by-month: {e}")
        return jsonify({"error": "Failed to fetch patients by month data"}), 500

@main.route('/api/analytics/revenue-by-visit-type')
@login_required
@physio_required
def api_revenue_by_visit_type():
    try:
        data = db.session.query(
            Treatment.treatment_type,
            func.sum(Treatment.fee_charged).label('total_fee')
        ).filter(Treatment.fee_charged.isnot(None)).group_by(Treatment.treatment_type).order_by(func.sum(Treatment.fee_charged).desc()).all()
        # Handle potential None values during conversion
        result = [{'treatment_type': row.treatment_type if row.treatment_type else 'Unspecified', 
                   'total_fee': float(row.total_fee) if row.total_fee else 0} 
                  for row in data]
        return jsonify(result)
    except Exception as e:
        print(f"Error in /api/analytics/revenue-by-visit-type: {e}")
        return jsonify({"error": "Failed to fetch revenue by visit type data"}), 500

@main.route('/api/analytics/revenue-by-location')
@login_required
@physio_required
def api_revenue_by_location():
    try:
        data = db.session.query(
            Treatment.location,
            func.sum(Treatment.fee_charged).label('total_fee')
        ).filter(Treatment.fee_charged.isnot(None)).group_by(Treatment.location).order_by(func.sum(Treatment.fee_charged).desc()).limit(10).all()
        result = [{'location': row.location if row.location else 'Unspecified', 
                   'total_fee': float(row.total_fee) if row.total_fee else 0} 
                  for row in data]
        return jsonify(result)
    except Exception as e:
        print(f"Error in /api/analytics/revenue-by-location: {e}")
        return jsonify({"error": "Failed to fetch revenue by location data"}), 500

@main.route('/api/analytics/common-diagnoses')
@login_required
@physio_required
def api_common_diagnoses():
    try:
        data = db.session.query(
            Patient.diagnosis, 
            func.count(Patient.id).label('count')
        ).filter(Patient.diagnosis.isnot(None), Patient.diagnosis != '').group_by(Patient.diagnosis).order_by(func.count(Patient.id).desc()).limit(10).all()
        result = [{'diagnosis': row.diagnosis if row.diagnosis else 'Unspecified', 
                   'count': row.count} 
                  for row in data]
        return jsonify(result)
    except Exception as e:
        print(f"Error in /api/analytics/common-diagnoses: {e}")
        return jsonify({"error": "Failed to fetch common diagnoses data"}), 500

@main.route('/api/analytics/patient-status')
@login_required
@physio_required
def api_patient_status():
    try:
        total_patients = Patient.query.count()
        active_patients = Patient.query.filter(Patient.status == 'Active').count()
        inactive_patients = total_patients - active_patients
        result = {'active': active_patients, 'inactive': inactive_patients} # Simpler structure for this chart
        return jsonify(result)
    except Exception as e:
        print(f"Error in /api/analytics/patient-status: {e}")
        return jsonify({"error": "Failed to fetch patient status data"}), 500

@main.route('/api/analytics/payment-methods')
@login_required
@physio_required
def api_payment_methods():
    try:
        data = db.session.query(
            Treatment.payment_method,
            func.count(Treatment.id).label('count')
        ).filter(Treatment.payment_method.isnot(None)).group_by(Treatment.payment_method).all()
        result = [{'payment_method': row.payment_method if row.payment_method else 'Unspecified', 
                   'count': row.count} 
                  for row in data]
        return jsonify(result)
    except Exception as e:
        print(f"Error in /api/analytics/payment-methods: {e}")
        return jsonify({"error": "Failed to fetch payment method data"}), 500

# --- End API Endpoints for Chart Data ---
