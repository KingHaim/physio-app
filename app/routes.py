# app/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func, extract, or_
from .models import db, Patient, Treatment, TriggerPoint  # Changed PatientNote to TriggerPoint
import json

main = Blueprint('main', __name__)

@main.route('/')
def index():
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

    total_patients = Patient.query.count()
    active_patients = Patient.query.filter_by(status='Active').count()
    today = datetime.now().date()
    upcoming_appointments = Treatment.query.filter(
        Treatment.next_appointment >= today
    ).order_by(Treatment.next_appointment).limit(5).all()

    return render_template('index.html',
                           patients=patients,
                           total_patients=total_patients,
                           active_patients=active_patients,
                           upcoming_appointments=upcoming_appointments,
                           search=search,
                           status_filter=status_filter)
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
    return render_template('patient.html', patient=patient)

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
def patients_list():
    patients = Patient.query.order_by(Patient.name).all()
    return render_template('patients_list.html', patients=patients)

@main.route('/patient/<int:id>/report')
def patient_report(id):
    patient = Patient.query.get_or_404(id)

    total_treatments = len(patient.treatments)
    completed_treatments = len([t for t in patient.treatments if t.status == 'Completed'])
    completion_rate = (completed_treatments / total_treatments * 100) if total_treatments > 0 else 0

    treatment_dates = [t.date for t in patient.treatments]
    if len(treatment_dates) >= 2:
        date_diffs = [(d2 - d1).days for d1, d2 in zip(treatment_dates[:-1], treatment_dates[1:])]
        avg_frequency = sum(date_diffs) / len(date_diffs)
    else:
        avg_frequency = 0

    progress_timeline = []

    progress_timeline.append({
        'date': patient.created_at,
        'event_type': 'registration',
        'event': 'Initial Registration',
        'details': f"Diagnosis: {patient.diagnosis}"
    })

    for treatment in patient.treatments:
        progress_timeline.append({
            'date': treatment.date,
            'event_type': 'treatment',
            'event': 'Treatment Session',
            'details': treatment.description,
            'notes': treatment.progress_notes
        })

    progress_timeline.sort(key=lambda x: x['date'], reverse=True)

    return render_template('patient_report.html',
                           patient=patient,
                           total_treatments=total_treatments,
                           completion_rate=completion_rate,
                           avg_frequency=avg_frequency,
                           progress_timeline=progress_timeline)
