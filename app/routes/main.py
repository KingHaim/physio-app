# app/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from datetime import datetime, timedelta
from calendar import monthrange
from sqlalchemy import func, extract, or_, case, cast, Float
from app.models import db, Patient, Treatment, TriggerPoint, UnmatchedCalendlyBooking, PatientReport  # Changed PatientNote to TriggerPoint
import json
from app.utils import mark_past_treatments_as_completed, mark_inactive_patients
from flask_login import login_required
from io import BytesIO
from xhtml2pdf import pisa
import markdown
import os

main = Blueprint('main', __name__)

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
        Treatment.created_at >= today
    ).order_by(Treatment.created_at).limit(5).all()
    
    # Get recent treatments
    recent_treatments = Treatment.query.order_by(
        Treatment.created_at.desc()  # O el nombre correcto de la columna

    ).limit(5).all()
    

    return render_template('index.html',
                           total_patients=total_patients,
                           active_patients=active_patients,
                           pending_review_count=pending_review_count,
                           today_appointments=today_appointments,
                           upcoming_appointments=upcoming_appointments,
                           recent_treatments=recent_treatments,
                           today=today,
                           week_end=week_end,
                           month_end=month_end)
@main.route('/api/treatment/<int:id>')
def get_treatment_details(id):
    try:
        treatment = Treatment.query.get_or_404(id)
        
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
        # Include both original field names and mapped field names for backward compatibility
        return jsonify({
            'id': treatment.id,
            'date': treatment.created_at.isoformat() if treatment.created_at else None,
            'description': treatment.treatment_type,  # For backward compatibility
            'progress_notes': treatment.notes,        # For backward compatibility
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
    except Exception as e:
        print(f"Error getting treatment details: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve treatment details',
            'message': str(e)
        }), 500

# In your routes.py file
from flask import jsonify
from sqlalchemy import exc

@main.route('/api/treatment/<int:id>', methods=['DELETE'])
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
@main.route('/patient/<int:id>/edit', methods=['GET', 'POST'])
def edit_patient(id):
    patient = Patient.query.get_or_404(id)
    if request.method == 'POST':
        try:
            patient.name = request.form['name']
            patient.date_of_birth = datetime.strptime(request.form['date_of_birth'], '%Y-%m-%d')
            patient.contact = request.form['contact']
            patient.diagnosis = request.form['diagnosis']
            patient.treatment_plan = request.form['treatment_plan']
            patient.notes = request.form['notes']
            patient.status = request.form['status']
            
            db.session.commit()
            flash('Patient information updated successfully!', 'success')
            return redirect(url_for('main.patient_detail', id=patient.id))
        except Exception as e:
            db.session.rollback()
            flash('Error updating patient information. Please try again.', 'danger')
            print(e)  # For debugging
    return render_template('edit_patient.html', patient=patient)

@main.route('/patient/new', methods=['GET', 'POST'])
def new_patient():
    if request.method == 'POST':
        try:
            patient = Patient(
                name=request.form['name'],
                date_of_birth=datetime.strptime(request.form['date_of_birth'], '%Y-%m-%d'),
                contact=request.form['contact'],
                diagnosis=request.form['diagnosis'],
                treatment_plan=request.form['treatment_plan'],
                notes=request.form['notes'],
                status='Active'
            )
            db.session.add(patient)
            db.session.commit()
            flash('Patient added successfully!', 'success')
            return redirect(url_for('main.patient_detail', id=patient.id))
        except Exception as e:
            db.session.rollback()
            flash('Error adding patient. Please try again.', 'danger')
            print(e)  # For debugging
    return render_template('new_patient.html')

@main.route('/patient/<int:id>')
def patient_detail(id):
    patient = Patient.query.get_or_404(id)
    print(f"Treatments for patient {patient.name}:")
    for treatment in patient.treatments:
        print(f"Treatment Created At: {treatment.created_at}")
    
    # Make sure today is a datetime object with both date and time
    today = datetime.now()
    
    # Automatically mark past treatments as completed
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
        
        db.session.commit()
        flash(f"{count} past treatment(s) automatically marked as completed.", "info")
    
    # Debug information
    print(f"Patient: {patient.name}, ID: {patient.id}")
    print(f"Today: {today}")
    
    # Check if treatments exist and directly query them to bypass any caching issues
    direct_treatments = Treatment.query.filter_by(patient_id=id).all()
    print(f"Direct query found {len(direct_treatments)} treatments for patient {patient.id}")
    
    for t in direct_treatments:
        print(f"Direct treatment: ID={t.id}, Type={t.treatment_type}, Date={t.created_at}, Status={t.status}")
    
    # Determine if this is the patient's first visit (based on existing treatments)
    is_first_visit = len(direct_treatments) == 0
    print(f"Is first visit for patient {patient.id}? {is_first_visit}") # Debugging

    # Use direct queried treatments in the template
    # This bypasses any possible issues with the relationship loading
    return render_template('patient_detail.html', 
                          patient=patient, 
                          today=today, 
                          treatments=direct_treatments,
                          is_first_visit=is_first_visit) # Pass the flag to the template


@main.route('/patient/<int:patient_id>/treatment', methods=['POST'])
@login_required
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
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding treatment: {e}', 'danger')
        return redirect(url_for('main.patient_detail', id=patient_id)) # Redirect back on error
        
    # If we have trigger points data, create those records too
    if evaluation_data and isinstance(evaluation_data, list): # Ensure it's a list
        try:
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
        except Exception as e:
            db.session.rollback() # Rollback trigger points if error
            # Optionally delete the treatment itself or leave it without points?
            # Let's leave the treatment but flash an error about points
            flash(f'Treatment added, but failed to save trigger points: {e}', 'warning') 
            print(f"ERROR: Failed adding trigger points for treatment {treatment.id}: {e}")

    flash('Treatment added successfully', 'success')
    return redirect(url_for('main.patient_detail', id=patient_id))

@main.route('/appointments')
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
def get_appointments():
    start = request.args.get('start', datetime.now().date().isoformat())
    end = request.args.get('end', (datetime.now() + timedelta(days=30)).date().isoformat())

    appointments = Treatment.query.filter(
        Treatment.created_at.between(start, end)
    ).all()

    events = [{
        'id': apt.id,
        'title': f"{apt.patient.name} - {apt.treatment_type}",
        'start': apt.created_at.isoformat(),
        'end': (apt.created_at + timedelta(minutes=30)).isoformat(),
        'color': '#3498db' if apt.status == 'Scheduled' else '#2ecc71'
    } for apt in appointments]

    return jsonify(events)

@main.route('/appointments/update/<int:id>', methods=['POST'])
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
def patient_treatments(id):
    patient = Patient.query.get_or_404(id)
    treatments = Treatment.query.filter_by(patient_id=id).order_by(Treatment.created_at.desc()).all()
    return render_template('treatments.html', patient=patient, treatments=treatments)

@main.route('/search')
def search():
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
def patient_report(id):
    patient = Patient.query.get_or_404(id)
    
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
def review_calendly_bookings():
    unmatched_bookings = UnmatchedCalendlyBooking.query.filter_by(status='Pending').all()
    return render_template('calendly_review.html', unmatched_bookings=unmatched_bookings)

@main.route('/treatment/<int:id>/edit', methods=['GET', 'POST'])
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

            except json.JSONDecodeError as e:
                # Log the error and the problematic string to the error log
                print(f"ERROR: JSONDecodeError processing trigger points for treatment {id}")
                print(f"ERROR_STRING: {trigger_data_string}")
                print(f"ERROR_DETAILS: {e}")
                flash('Error processing trigger point data. Please check the format or report this issue.', 'danger')
                db.session.rollback()
                original_treatment_data = Treatment.query.get(id)
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

        # If try block succeeded or no trigger_points_data was present, commit other changes
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
def view_treatment(id):
    treatment = Treatment.query.get_or_404(id)
    patient = treatment.patient
    
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
def patient_edit_treatments(id):
    patient = Patient.query.get_or_404(id)
    treatments = Treatment.query.filter_by(patient_id=id).order_by(Treatment.created_at.desc()).all()
    return render_template('edit_treatments_list.html', patient=patient, treatments=treatments)

@main.route('/patient/<int:patient_id>/new_treatment_page', methods=['GET'])
@login_required
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

@main.route('/analytics')
def analytics():
    # Get total counts
    total_patients = Patient.query.count()
    active_patients = Patient.query.filter_by(status='Active').count()
    inactive_patients = Patient.query.filter_by(status='Inactive').count()
    total_treatments = Treatment.query.count()
    
    # Get treatments by month for the past year
    today = datetime.now().date()
    one_year_ago = today - timedelta(days=365)
    
    treatments_by_month = db.session.query(
        func.strftime('%Y-%m', Treatment.created_at).label('month'),
        func.count(Treatment.id).label('count')
    ).filter(Treatment.created_at >= one_year_ago) \
        .group_by(func.strftime('%Y-%m', Treatment.created_at)) \
        .order_by(func.strftime('%Y-%m', Treatment.created_at)) \
        .all()
    
    # Get patient acquisition by month
    patients_by_month = db.session.query(
        func.strftime('%Y-%m', Patient.created_at).label('month'),
        func.count(Patient.id).label('count')
    ).filter(Patient.created_at >= one_year_ago) \
        .group_by(func.strftime('%Y-%m', Patient.created_at)) \
        .order_by(func.strftime('%Y-%m', Patient.created_at)) \
        .all()
    
    # Get most common diagnoses
    common_diagnoses = db.session.query(
        Patient.diagnosis,
        func.count(Patient.id).label('count')
    ).filter(Patient.diagnosis != None, Patient.diagnosis != '') \
        .group_by(Patient.diagnosis) \
        .order_by(func.count(Patient.id).desc()) \
        .limit(10) \
        .all()
    
    # Get average treatments per patient - Corrected query
    # Subquery to count treatments per patient
    treatment_counts_subquery = db.session.query(
        Treatment.patient_id,
        func.count(Treatment.id).label('treatment_count')
    ).group_by(Treatment.patient_id).subquery()
    
    # Query to calculate the average of the counts from the subquery
    avg_treatments = db.session.query(
        func.avg(treatment_counts_subquery.c.treatment_count)
    ).scalar() or 0
    
    # --- New Financial Analytics ---
    
    # Calculate Average Monthly Revenue (from past treatments with a fee)
    monthly_revenue_subquery = db.session.query(
        func.strftime('%Y-%m', Treatment.created_at).label('month'),
        func.sum(Treatment.fee_charged).label('monthly_total')
    ).filter(
        Treatment.created_at < today, 
        Treatment.fee_charged.isnot(None)
    ).group_by('month').subquery()
    
    avg_monthly_revenue = db.session.query(
        func.avg(monthly_revenue_subquery.c.monthly_total)
    ).scalar() or 0
    
    # Revenue by Visit Type (for past treatments with a fee)
    revenue_by_visit_type = db.session.query(
        Treatment.visit_type,
        func.sum(Treatment.fee_charged).label('total_fee')
    ).filter(Treatment.fee_charged.isnot(None), Treatment.visit_type.isnot(None)) \
     .group_by(Treatment.visit_type) \
     .order_by(func.sum(Treatment.fee_charged).desc()) \
     .all()

    # Revenue by Location (for ALL treatments with a fee)
    revenue_by_location = db.session.query(
        Treatment.location,
        func.sum(Treatment.fee_charged).label('total_fee')
    ).filter(Treatment.fee_charged.isnot(None), Treatment.location.isnot(None), Treatment.location != '') \
     .group_by(Treatment.location) \
     .order_by(func.sum(Treatment.fee_charged).desc()) \
     .limit(10) \
     .all()

    # Payment Method Distribution (Keeping status filter for this one, assuming it makes sense)
    payment_method_distribution = db.session.query(
        Treatment.payment_method,
        func.count(Treatment.id).label('count')
    ).filter(Treatment.status == 'Completed', Treatment.payment_method.isnot(None), Treatment.payment_method != '') \
     .group_by(Treatment.payment_method) \
     .order_by(func.count(Treatment.id).desc()) \
     .all()
     
    # Calculate CostaSpine Revenue and Service Fee
    costaspine_revenue_query = db.session.query(
        func.sum(Treatment.fee_charged)
    ).filter(
        Treatment.location == 'CostaSpine Clinic', 
        Treatment.fee_charged.isnot(None)
    ).scalar() or 0
    
    costaspine_revenue = float(costaspine_revenue_query)
    costaspine_service_fee = costaspine_revenue * 0.30
    
    # --- Calculate Estimated Tax (19%) on Card Payments --- 
    tax_calculation_query = db.session.query(
        func.sum(
            case(
                (Treatment.location == 'CostaSpine Clinic', Treatment.fee_charged * 0.70 * 0.19),
                else_= Treatment.fee_charged * 0.19
            )
        )
    ).filter(
        Treatment.payment_method == 'Card',
        Treatment.fee_charged.isnot(None)
    ).scalar() or 0
    
    total_estimated_tax = float(tax_calculation_query)

    # --- End New Financial Analytics ---
    
    return render_template('analytics.html',
                          total_patients=total_patients,
                          active_patients=active_patients,
                          inactive_patients=inactive_patients,
                          total_treatments=total_treatments,
                          treatments_by_month=treatments_by_month,
                          patients_by_month=patients_by_month,
                          common_diagnoses=common_diagnoses,
                          avg_treatments=round(avg_treatments, 1),
                          avg_monthly_revenue=avg_monthly_revenue,
                          revenue_by_visit_type=revenue_by_visit_type,
                          revenue_by_location=revenue_by_location,
                          payment_method_distribution=payment_method_distribution,
                          costaspine_revenue=costaspine_revenue,
                          costaspine_service_fee=costaspine_service_fee,
                          total_estimated_tax=total_estimated_tax) # Pass new tax data

@main.route('/api/analytics/costaspine-fee-data')
@login_required
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
def download_report_pdf(report_id):
    """Generates and serves a PDF version of a specific report."""
    report = PatientReport.query.get_or_404(report_id)
    patient = report.patient # Assuming relationship is set up

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
def review_payments():
    """Displays treatments with fees but missing payment methods."""
    try:
        treatments_to_review = Treatment.query.join(Patient).filter(
            Treatment.fee_charged.isnot(None),
            Treatment.fee_charged > 0,
            or_(Treatment.payment_method.is_(None), Treatment.payment_method == ''),
            Treatment.status == 'Completed' # Focus on completed treatments
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
