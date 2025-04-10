# app/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func, extract, or_
from app.models import db, Patient, Treatment, TriggerPoint, UnmatchedCalendlyBooking, PatientReport  # Changed PatientNote to TriggerPoint
import json
from app.utils import mark_past_treatments_as_completed, mark_inactive_patients
from flask_login import login_required

main = Blueprint('main', __name__)

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
        func.date(Treatment.next_appointment) == today
    ).count()
    
    # Get upcoming appointments
    upcoming_appointments = Treatment.query.filter(
        Treatment.next_appointment >= today
    ).order_by(Treatment.next_appointment).limit(5).all()
    
    # Get recent treatments
    recent_treatments = Treatment.query.order_by(
        Treatment.date.desc()
    ).limit(5).all()
    
    # Convert next_appointment to date objects for comparison
    for appointment in upcoming_appointments:
        if appointment.next_appointment:
            # Store the original datetime
            appointment.next_appointment_datetime = appointment.next_appointment
            # Add a date-only attribute for comparison
            appointment.next_appointment_date = appointment.next_appointment.date()

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

    return jsonify({
        'id': treatment.id,
        'date': treatment.date.isoformat(),
        'description': treatment.description,
        'progress_notes': treatment.progress_notes,
        'pain_level': treatment.pain_level,
        'movement_restriction': treatment.movement_restriction,
        'evaluation_data': treatment.evaluation_data,
        'trigger_points': trigger_points,
        'next_appointment': treatment.next_appointment.isoformat() if treatment.next_appointment else None
    })

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
    
    # Make sure today is a datetime object with both date and time
    today = datetime.now()
    
    # Automatically mark past treatments as completed
    past_treatments = Treatment.query.filter(
        Treatment.patient_id == id,
        Treatment.date < today.date(),
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
    
    # Check if treatments exist
    if patient.treatments:
        print(f"Number of treatments: {len(patient.treatments)}")
        for t in patient.treatments:
            print(f"Treatment: {t.id}, Date: {t.date}, Next: {t.next_appointment}")
    
    return render_template('patient_detail.html', patient=patient, today=today)

@main.route('/treatment/new/<int:patient_id>', methods=['POST'])
def new_treatment(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    try:
        # Get next_appointment if it exists, otherwise set to None
        next_appointment = None
        if request.form.get('next_appointment'):
            next_appointment = datetime.strptime(request.form['next_appointment'], '%Y-%m-%d')

        treatment = Treatment(
            patient_id=patient_id,
            description=request.form['description'],
            progress_notes=request.form['progress_notes'],
            next_appointment=next_appointment,  # Now can be None
            pain_level=request.form.get('pain_level', type=int),
            movement_restriction=request.form.get('movement_restriction'),
            evaluation_data={
                'pain_characteristics': request.form.getlist('pain_chars[]'),
                'muscle_symptoms': {k: v for k, v in request.form.items() if k.startswith('muscle_symptoms')}
            }
        )
        
        # Rest of the function remains the same
        db.session.add(treatment)
        db.session.flush()

        trigger_points_data = json.loads(request.form.get('trigger_points', '[]'))
        for point_data in trigger_points_data:
            trigger_point = TriggerPoint(
                treatment_id=treatment.id,
                location_x=point_data['x'],
                location_y=point_data['y'],
                type=point_data['type'],
                muscle=point_data['muscle'],
                intensity=point_data.get('intensity', 5),
                symptoms=point_data.get('symptoms', ''),
                referral_pattern=point_data.get('referral', '')
            )
            db.session.add(trigger_point)

        db.session.commit()
        flash('Treatment recorded successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error recording treatment. Please try again.', 'danger')
        print(f"Error in new_treatment: {e}")

    return redirect(url_for('main.patient_detail', id=patient_id))
@main.route('/appointments')
def appointments():
    start_date = request.args.get('start_date',
                               datetime.now().date().isoformat())
    end_date = request.args.get('end_date',
                             (datetime.now() + timedelta(days=30)).date().isoformat())

    appointments = Treatment.query.filter(
        Treatment.next_appointment.between(start_date, end_date)
    ).order_by(Treatment.next_appointment).all()

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
        Treatment.next_appointment.between(start, end)
    ).all()

    events = [{
        'id': apt.id,
        'title': f"{apt.patient.name} - {apt.description}",
        'start': apt.next_appointment.isoformat(),
        'end': (apt.next_appointment + timedelta(minutes=30)).isoformat(),
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
        treatment.next_appointment = datetime.strptime(
            request.form['appointment_datetime'],
            '%Y-%m-%dT%H:%M'
        )
        treatment.description = request.form['appointment_type']
        treatment.progress_notes = request.form['notes']

    db.session.commit()
    return jsonify({'success': True})

@main.route('/reports')
def reports():
    try:
        total_patients = Patient.query.count()
        active_patients = Patient.query.filter_by(status='Active').count()

        monthly_treatments_query = db.session.query(
            func.strftime('%Y-%m', Treatment.date).label('month'),
            func.count(Treatment.id).label('count')
        ).group_by(func.strftime('%Y-%m', Treatment.date)) \
            .order_by(func.strftime('%Y-%m', Treatment.date).desc()) \
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
            .order_by(Treatment.date.desc())
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
        func.strftime('%Y-%m', Treatment.date).label('month'),
        func.count(Treatment.id).label('count')
    ).group_by(func.strftime('%Y-%m', Treatment.date)) \
        .order_by(func.strftime('%Y-%m', Treatment.date)) \
        .all()

    return jsonify({
        'labels': [t[0] for t in treatments],
        'data': [t[1] for t in treatments]
    })

@main.route('/patient/<int:id>/treatments')
def patient_treatments(id):
    patient = Patient.query.get_or_404(id)
    treatments = Treatment.query.filter_by(patient_id=id).order_by(Treatment.date.desc()).all()
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
        # Get the most recent report
        report = PatientReport.query.filter_by(
            patient_id=id
        ).order_by(PatientReport.generated_date.desc()).first()
    
    if not report:
        flash('No report found for this patient.', 'warning')
        return redirect(url_for('main.patient_detail', id=id))
    
    # Get all reports for the dropdown
    all_reports = PatientReport.query.filter_by(
        patient_id=id
    ).order_by(PatientReport.generated_date.desc()).all()
    
    return render_template('patient_report.html', 
                          patient=patient, 
                          report=report,
                          all_reports=all_reports)

@main.route('/calendly/review')
def review_calendly_bookings():
    unmatched_bookings = UnmatchedCalendlyBooking.query.filter_by(status='Pending').all()
    return render_template('calendly_review.html', unmatched_bookings=unmatched_bookings)

@main.route('/treatment/<int:id>/edit', methods=['GET', 'POST'])
def edit_treatment(id):
    treatment = Treatment.query.get_or_404(id)
    patient = treatment.patient
    
    if request.method == 'POST':
        # Update date field
        if request.form.get('date'):
            treatment.date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        
        treatment.description = request.form['description']
        treatment.progress_notes = request.form['progress_notes']
        treatment.status = request.form['status']
        
        # Handle next_appointment
        if request.form.get('next_appointment'):
            treatment.next_appointment = datetime.strptime(
                request.form['next_appointment'], '%Y-%m-%d'
            )
        else:
            treatment.next_appointment = None
            
        # Handle pain level if provided
        if request.form.get('pain_level'):
            treatment.pain_level = int(request.form['pain_level'])
            
        # Handle movement restriction if provided
        if request.form.get('movement_restriction'):
            treatment.movement_restriction = request.form['movement_restriction']
        
        # Handle trigger points data
        if request.form.get('trigger_points_data'):
            treatment.evaluation_data = json.loads(request.form['trigger_points_data'])
            
            # Update or create trigger points in the database
            # First, remove existing trigger points
            TriggerPoint.query.filter_by(treatment_id=treatment.id).delete()
            
            # Then add the new ones
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
        
        db.session.commit()
        flash(f'Treatment session on {treatment.date.strftime("%Y-%m-%d")} updated successfully!', 'success')
        return redirect(url_for('main.patient_detail', id=patient.id))
    
    return render_template('edit_treatment.html', treatment=treatment, patient=patient)

@main.route('/treatment/<int:id>/view')
def view_treatment(id):
    treatment = Treatment.query.get_or_404(id)
    patient = treatment.patient
    return render_template('view_treatment.html', treatment=treatment, patient=patient)

@main.route('/test/edit-treatment/<int:id>')
def test_edit_treatment(id):
    treatment = Treatment.query.get_or_404(id)
    return f"""
    <html>
    <body>
        <h1>Test Edit Treatment</h1>
        <p>Treatment ID: {treatment.id}</p>
        <p>Date: {treatment.date}</p>
        <p>Description: {treatment.description}</p>
        <p>Patient: {treatment.patient.name}</p>
        <a href="/treatment/{treatment.id}/edit">Go to Edit Page</a>
    </body>
    </html>
    """

@main.route('/patient/<int:id>/edit-treatments')
def patient_edit_treatments(id):
    patient = Patient.query.get_or_404(id)
    treatments = Treatment.query.filter_by(patient_id=id).order_by(Treatment.date.desc()).all()
    return render_template('edit_treatments_list.html', patient=patient, treatments=treatments)

@main.route('/admin/fix-calendly-dates')
def fix_calendly_dates():
    # Get all treatments with "Booked via Calendly" in the notes
    calendly_treatments = Treatment.query.filter(
        Treatment.progress_notes.like('%Booked via Calendly%')
    ).all()
    
    updated_count = 0
    for treatment in calendly_treatments:
        if treatment.next_appointment:
            # Update the date to match the next_appointment date
            treatment.date = treatment.next_appointment.date()
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
        func.strftime('%Y-%m', Treatment.date).label('month'),
        func.count(Treatment.id).label('count')
    ).filter(Treatment.date >= one_year_ago) \
        .group_by(func.strftime('%Y-%m', Treatment.date)) \
        .order_by(func.strftime('%Y-%m', Treatment.date)) \
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
    
    # Get average treatments per patient
    avg_treatments = db.session.query(
        func.avg(
            db.session.query(func.count(Treatment.id))
            .filter(Treatment.patient_id == Patient.id)
            .scalar_subquery()
        )
    ).scalar() or 0
    
    return render_template('analytics.html',
                          total_patients=total_patients,
                          active_patients=active_patients,
                          inactive_patients=inactive_patients,
                          total_treatments=total_treatments,
                          treatments_by_month=treatments_by_month,
                          patients_by_month=patients_by_month,
                          common_diagnoses=common_diagnoses,
                          avg_treatments=round(avg_treatments, 1))
