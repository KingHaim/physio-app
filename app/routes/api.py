from flask import Blueprint, jsonify, current_app, request
import requests
from datetime import datetime, timedelta
from app.models import Treatment, Treatment as Appointment, Patient, UnmatchedCalendlyBooking, PatientReport
from app import db
from sqlalchemy.sql import func, or_
import os
import json

api = Blueprint('api', __name__)

@api.route('/api/sync-calendly-events', methods=['GET'])
def sync_calendly_events():
    # Your Calendly API token (store this securely in environment variables)
    api_token = current_app.config.get('CALENDLY_API_TOKEN')
    
    if not api_token:
        return jsonify({'success': False, 'error': 'Calendly API token not configured'})
    
    try:
        # Get your Calendly user URI
        headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        }
        
        # First, get your user info
        user_response = requests.get('https://api.calendly.com/users/me', headers=headers)
        
        if user_response.status_code != 200:
            return jsonify({'success': False, 'error': f'Failed to get Calendly user: {user_response.text}'})
        
        user_uri = user_response.json()['resource']['uri']
        
        # Get scheduled events (appointments)
        # Set time range (e.g., from 30 days ago to 60 days in the future)
        min_time = (datetime.utcnow() - timedelta(days=30)).isoformat() + 'Z'
        max_time = (datetime.utcnow() + timedelta(days=60)).isoformat() + 'Z'
        
        events_url = 'https://api.calendly.com/scheduled_events'
        params = {
            'user': user_uri,
            'min_start_time': min_time,
            'max_start_time': max_time,
            'status': 'active'
        }
        
        events_response = requests.get(events_url, headers=headers, params=params)
        
        if events_response.status_code != 200:
            return jsonify({'success': False, 'error': f'Failed to get Calendly events: {events_response.text}'})
        
        events = events_response.json()['collection']
        
        # Process each event and get invitee (patient) details
        synced_count = 0
        unmatched_patients = []
        
        for event in events:
            event_uri = event['uri']
            
            # Get invitee details
            event_uuid = event_uri.split('/')[-1]
            invitees_url = f'https://api.calendly.com/scheduled_events/{event_uuid}/invitees'
            invitees_response = requests.get(invitees_url, headers=headers)
            
            if invitees_response.status_code != 200:
                continue
            
            invitees = invitees_response.json()['collection']
            
            for invitee in invitees:
                # Extract appointment details
                name = invitee['name']
                email = invitee['email']
                start_time = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(event['end_time'].replace('Z', '+00:00'))
                event_type = event['name']
                
                # Enhanced patient matching
                patient = find_matching_patient(name, email)
                
                if not patient:
                    # Store unmatched patient for later review
                    unmatched_patients.append({
                        'name': name,
                        'email': email,
                        'event_type': event_type,
                        'start_time': start_time.isoformat(),
                        'calendly_invitee_id': invitee['uri'].split('/')[-1]
                    })
                    
                    # Create temporary patient
                    patient = Patient(
                        name=name,
                        contact=email,
                        date_of_birth=None,
                        diagnosis="To be updated (Calendly booking)",
                        treatment_plan="To be determined",
                        notes=f"Patient booked via Calendly on {datetime.now().strftime('%Y-%m-%d')}. NEEDS REVIEW: Partial information.",
                        status="Pending Review"  # Special status for review
                    )
                    db.session.add(patient)
                    db.session.flush()
                
                # Check if appointment already exists
                existing_appointment = Treatment.query.filter_by(
                    patient_id=patient.id,
                    next_appointment=start_time
                ).first()
                
                if not existing_appointment:
                    # Create new appointment (Treatment)
                    appointment = Treatment(
                        patient_id=patient.id,
                        next_appointment=start_time,
                        description=event_type,
                        status="Scheduled",
                        progress_notes=f"Booked via Calendly. Duration: {int((end_time - start_time).total_seconds() / 60)} minutes.",
                        date=start_time.date()
                    )
                    db.session.add(appointment)
                    synced_count += 1
            
        # Store unmatched patients in session for review
        if unmatched_patients:
            # Store in database for persistence
            for patient_data in unmatched_patients:
                unmatched = UnmatchedCalendlyBooking(
                    name=patient_data['name'],
                    email=patient_data['email'],
                    event_type=patient_data['event_type'],
                    start_time=datetime.fromisoformat(patient_data['start_time']),
                    calendly_invitee_id=patient_data['calendly_invitee_id'],
                    status='Pending'
                )
                db.session.add(unmatched)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'count': synced_count,
            'unmatched': len(unmatched_patients),
            'message': f'Successfully synced {synced_count} appointments from Calendly. {len(unmatched_patients)} patients need review.'
        })
    
    except Exception as e:
        # Log the error
        print(f"Error in sync_calendly_events: {str(e)}")
        # Return a friendly error message
        return jsonify({
            'success': False,
            'error': f"An error occurred: {str(e)}"
        }), 500

def find_matching_patient(name, email):
    """Try to find a matching patient using name and email."""
    # First try exact email match
    patient = Patient.query.filter_by(contact=email).first()
    if patient:
        return patient
    
    # Try name matching (first name only)
    first_name = name.split()[0].lower()
    potential_matches = Patient.query.filter(
        func.lower(Patient.name).like(f"{first_name}%")
    ).all()
    
    if len(potential_matches) == 1:
        # If only one match, return it
        return potential_matches[0]
    
    # No confident match found
    return None

@api.route('/api/patients/search')
def search_patients():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    patients = Patient.query.filter(
        or_(
            Patient.name.ilike(f'%{query}%'),
            Patient.contact.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'contact': p.contact
    } for p in patients])

@api.route('/api/calendly/match-booking', methods=['POST'])
def match_calendly_booking():
    try:
        data = request.json
        booking_id = data.get('booking_id')
        patient_id = data.get('patient_id')
        
        if not booking_id or not patient_id:
            return jsonify({'success': False, 'error': 'Missing booking_id or patient_id'})
        
        # Get the booking
        booking = UnmatchedCalendlyBooking.query.get(booking_id)
        if not booking:
            return jsonify({'success': False, 'error': 'Booking not found'})
        
        # Get the patient
        patient = Patient.query.get(patient_id)
        if not patient:
            return jsonify({'success': False, 'error': 'Patient not found'})
        
        # Update the booking status and link to patient
        booking.status = 'Matched'
        booking.matched_patient_id = patient_id
        
        # Check if there's already a treatment for this appointment
        existing_treatment = Treatment.query.filter_by(
            next_appointment=booking.start_time,
            patient_id=patient_id
        ).first()
        
        if not existing_treatment:
            # Create a new treatment record
            treatment = Treatment(
                patient_id=patient_id,
                date=datetime.now(),
                description=f"Calendly booking: {booking.event_type}",
                next_appointment=booking.start_time,
                status="Scheduled",
                progress_notes=f"Booked via Calendly. Email: {booking.email}"
            )
            db.session.add(treatment)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Booking matched to patient successfully',
            'patient_id': patient_id
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in match_calendly_booking: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@api.route('/api/calendly/create-patient-from-booking', methods=['POST'])
def create_patient_from_booking():
    data = request.json
    booking_id = data.get('booking_id')
    
    if not booking_id:
        return jsonify({'success': False, 'error': 'Missing booking_id'})
    
    try:
        booking = UnmatchedCalendlyBooking.query.get_or_404(booking_id)
        
        # Check if a temporary patient was already created
        temp_patient = Patient.query.filter_by(
            contact=booking.email,
            status='Pending Review'
        ).first()
        
        if temp_patient:
            # Update the temporary patient
            temp_patient.status = 'Active'
            patient_id = temp_patient.id
        else:
            # Create a new patient
            patient = Patient(
                name=booking.name,
                contact=booking.email,
                date_of_birth=None,
                diagnosis="Created from Calendly booking",
                treatment_plan="To be determined",
                notes=f"Patient created from Calendly booking on {datetime.now().strftime('%Y-%m-%d')}",
                status="Active"
            )
            db.session.add(patient)
            db.session.flush()
            patient_id = patient.id
        
        # Update booking status
        booking.status = 'Matched'
        booking.matched_patient_id = patient_id
        
        db.session.commit()
        
        return jsonify({'success': True, 'patient_id': patient_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@api.route('/api/treatment/<int:id>', methods=['GET'])
def get_treatment(id):
    treatment = Treatment.query.get_or_404(id)
    return jsonify({
        'id': treatment.id,
        'date': treatment.date.strftime('%Y-%m-%d'),
        'description': treatment.description,
        'progress_notes': treatment.progress_notes,
        'status': treatment.status,
        'next_appointment': treatment.next_appointment.strftime('%Y-%m-%d') if treatment.next_appointment else None,
        'pain_level': treatment.pain_level,
        'movement_restriction': treatment.movement_restriction
    })

@api.route('/api/appointment/<int:id>/status', methods=['POST'])
def update_appointment_status(id):
    data = request.json
    status = data.get('status')
    
    if not status:
        return jsonify({'success': False, 'message': 'Status is required'})
    
    try:
        appointment = Treatment.query.get_or_404(id)
        appointment.status = status
        
        # If marking as completed, set the date to today if not already set
        if status == 'Completed' and not appointment.date:
            appointment.date = datetime.now().date()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Appointment status updated to {status}'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@api.route('/api/patient/<int:id>/generate-report', methods=['POST'])
def generate_patient_report(id):
    try:
        patient = Patient.query.get_or_404(id)
        
        # Log the start of report generation
        print(f"Starting report generation for patient {id}")
        
        # Get all completed treatments AND past treatments
        today = datetime.now().date()
        treatments = Treatment.query.filter(
            Treatment.patient_id == id,
            (Treatment.status == 'Completed') | 
            (Treatment.date < today)  # Consider past treatments as completed
        ).order_by(Treatment.date).all()
        
        if not treatments:
            print(f"No completed or past treatments found for patient {id}")
            
            # Check if there are any treatments at all
            all_treatments = Treatment.query.filter_by(patient_id=id).order_by(Treatment.date).all()
            
            if all_treatments:
                print(f"Using fallback report with {len(all_treatments)} treatments")
                # Generate a fallback report
                report_content = generate_fallback_report(all_treatments)
                
                # Save the report to the database
                report = PatientReport(
                    patient_id=id,
                    content=report_content,
                    generated_date=datetime.now(),
                    report_type='Fallback Report'
                )
                db.session.add(report)
                db.session.commit()
                
                print(f"Fallback report saved to database with ID {report.id}")
                
                return jsonify({
                    'success': True,
                    'message': 'Basic report generated successfully',
                    'report_id': report.id
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'No treatments found for this patient.'
                })
        
        print(f"Found {len(treatments)} completed/past treatments for patient {id}")
        
        # Prepare the prompt for the AI
        prompt = f"""
        Patient Name: {patient.name}
        Diagnosis: {patient.diagnosis}
        Treatment Plan: {patient.treatment_plan}
        
        Treatment History:
        """
        
        for t in treatments:
            prompt += f"""
            Date: {t.date.strftime('%Y-%m-%d')}
            Description: {t.description}
            Progress Notes: {t.progress_notes or 'None'}
            Pain Level: {t.pain_level or 'Not recorded'}
            Movement Restriction: {t.movement_restriction or 'None'}
            Status: {t.status}
            
            """
        
        prompt += """
        Based on the above information, please generate a comprehensive physiotherapy treatment progress report. 
        Include:
        1. A summary of the patient's condition and progress
        2. Key observations from the treatment sessions
        3. Assessment of improvement in pain levels and movement
        4. Recommendations for continued treatment
        
        Format the report with markdown headings and bullet points for readability.
        
        End the report with a signature section that includes:
        
        ---
        
        **Haim Ganancia**
        CostaSpine Physiotherapy Clinic
        Date: [Current Date]
        """
        
        # Call the DeepSeek API
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        
        if not api_key:
            print("No DeepSeek API key found")
            # Generate a fallback report
            report_content = generate_fallback_report(treatments)
            report_type = 'Fallback Report (No API Key)'
        else:
            try:
                print(f"Calling DeepSeek API for patient {id}")
                
                # Increase timeout to 60 seconds
                response = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": "You are a professional physiotherapist creating a treatment progress report."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 2000
                    },
                    timeout=60  # Increased from 30 to 60 seconds
                )
                
                print(f"DeepSeek API response status: {response.status_code}")
                
                if response.status_code != 200:
                    print(f"Error from DeepSeek API: {response.text}")
                    # Generate a fallback report
                    report_content = generate_fallback_report(treatments)
                    report_type = 'Fallback Report (API Error)'
                else:
                    # Extract the report content
                    try:
                        report_content = response.json()['choices'][0]['message']['content']
                        report_type = 'AI Generated'
                        print(f"Successfully generated report content of length {len(report_content)}")
                    except (KeyError, IndexError, ValueError) as e:
                        print(f"Error parsing API response: {str(e)}")
                        # Generate a fallback report
                        report_content = generate_fallback_report(treatments)
                        report_type = 'Fallback Report (Parse Error)'
                    
            except requests.exceptions.Timeout:
                print("DeepSeek API request timed out")
                # Generate a fallback report
                report_content = generate_fallback_report(treatments)
                report_type = 'Fallback Report (Timeout)'
            except requests.exceptions.RequestException as e:
                print(f"Request exception: {str(e)}")
                # Generate a fallback report
                report_content = generate_fallback_report(treatments)
                report_type = 'Fallback Report (Request Error)'
        
        # Save the report to the database
        report = PatientReport(
            patient_id=id,
            content=report_content,
            generated_date=datetime.now(),
            report_type=report_type
        )
        db.session.add(report)
        db.session.commit()
        
        print(f"Report saved to database with ID {report.id}")
        
        return jsonify({
            'success': True,
            'message': 'Report generated successfully',
            'report_id': report.id
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Exception in generate_patient_report: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        })

def generate_fallback_report(treatments):
    """Generate a simple report if the API fails"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    content = """# Treatment Progress Report

## Summary
This is an automatically generated summary of the treatment history.

## Treatment History
"""
    
    for t in treatments:
        content += f"""
### Session on {t.date.strftime('%Y-%m-%d')}

**Description:** {t.description}

**Progress Notes:** {t.progress_notes or 'None recorded'}

**Pain Level:** {t.pain_level or 'Not recorded'}

**Movement Restriction:** {t.movement_restriction or 'None recorded'}

---
"""
    
    content += """
## Recommendations

Please consult with your physiotherapist for personalized recommendations based on your treatment progress.

---

**Haim Ganancia**  
CostaSpine Physiotherapy Clinic  
Date: """ + today
    
    return content

@api.route('/api/patient/<int:id>/mark-past-as-completed', methods=['POST'])
def mark_past_as_completed(id):
    try:
        today = datetime.now().date()
        
        # Find all past treatments that aren't already completed
        past_treatments = Treatment.query.filter(
            Treatment.patient_id == id,
            Treatment.date < today,
            Treatment.status != 'Completed'
        ).all()
        
        # Update their status
        count = 0
        for treatment in past_treatments:
            treatment.status = 'Completed'
            count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'count': count,
            'message': f'{count} past treatments marked as Completed.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        })

@api.route('/api/calendly/webhook', methods=['POST'])
def calendly_webhook():
    try:
        data = request.json
        
        # Verify this is a booking.created event
        if data.get('event') != 'invitee.created':
            return jsonify({'status': 'ignored', 'reason': 'Not a booking creation event'})
        
        # Extract booking details
        payload = data.get('payload', {})
        invitee = payload.get('invitee', {})
        event = payload.get('event', {})
        
        # Check if this booking already exists
        existing_booking = UnmatchedCalendlyBooking.query.filter_by(
            calendly_uuid=invitee.get('uuid')
        ).first()
        
        if existing_booking:
            return jsonify({'status': 'ignored', 'reason': 'Booking already processed'})
        
        # Create a new unmatched booking
        booking = UnmatchedCalendlyBooking(
            calendly_uuid=invitee.get('uuid'),
            name=invitee.get('name', ''),
            email=invitee.get('email', ''),
            event_type=event.get('name', ''),
            start_time=datetime.fromisoformat(invitee.get('start_time').replace('Z', '+00:00')),
            end_time=datetime.fromisoformat(invitee.get('end_time').replace('Z', '+00:00')),
            status='Pending',
            raw_data=json.dumps(data)
        )
        
        db.session.add(booking)
        db.session.commit()
        
        # Try to automatically match to an existing patient
        patient = find_matching_patient(booking.name, booking.email)
        
        if patient:
            # Automatically match and create treatment
            booking.status = 'Matched'
            booking.matched_patient_id = patient.id
            
            # Create a treatment record
            treatment = Treatment(
                patient_id=patient.id,
                date=datetime.now(),
                description=f"Calendly booking: {booking.event_type}",
                next_appointment=booking.start_time,
                status="Scheduled",
                progress_notes=f"Automatically matched from Calendly. Email: {booking.email}"
            )
            
            db.session.add(treatment)
            db.session.commit()
            
            return jsonify({
                'status': 'success', 
                'message': 'Booking created and automatically matched to patient',
                'patient_id': patient.id
            })
        
        return jsonify({'status': 'success', 'message': 'Unmatched booking created'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in calendly_webhook: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api.route('/api/calendly/sync', methods=['POST'])
def sync_calendly_appointments():
    try:
        # This would typically call the Calendly API to get recent appointments
        # For now, we'll just check for any unmatched bookings and try to match them
        
        unmatched_bookings = UnmatchedCalendlyBooking.query.filter_by(status='Pending').all()
        matched_count = 0
        
        for booking in unmatched_bookings:
            # Try to find a matching patient
            patient = find_matching_patient(booking.name, booking.email)
            
            if patient:
                # Match the booking and create a treatment
                booking.status = 'Matched'
                booking.matched_patient_id = patient.id
                
                # Check if there's already a treatment for this appointment
                existing_treatment = Treatment.query.filter_by(
                    next_appointment=booking.start_time,
                    patient_id=patient.id
                ).first()
                
                if not existing_treatment:
                    # Create a new treatment record
                    treatment = Treatment(
                        patient_id=patient.id,
                        date=datetime.now(),
                        description=f"Calendly booking: {booking.event_type}",
                        next_appointment=booking.start_time,
                        status="Scheduled",
                        progress_notes=f"Automatically matched from Calendly. Email: {booking.email}"
                    )
                    
                    db.session.add(treatment)
                    matched_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Sync complete. Matched {matched_count} appointments.'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in sync_calendly_appointments: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@api.route('/api/patients/<int:patient_id>/status', methods=['POST'])
def update_patient_status(patient_id):
    try:
        data = request.json
        status = data.get('status')
        
        if not status or status not in ['Active', 'Inactive', 'Completed', 'Pending Review']:
            return jsonify({'success': False, 'error': 'Invalid status'})
        
        patient = Patient.query.get_or_404(patient_id)
        patient.status = status
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Patient status updated to {status}'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        })

@api.route('/api/patients/bulk-update-status', methods=['POST'])
def bulk_update_patient_status():
    try:
        data = request.json
        patient_ids = data.get('patient_ids', [])
        status = data.get('status')
        
        if not status or status not in ['Active', 'Inactive', 'Completed', 'Pending Review']:
            return jsonify({'success': False, 'error': 'Invalid status'})
        
        if not patient_ids:
            return jsonify({'success': False, 'error': 'No patients selected'})
        
        updated_count = 0
        for patient_id in patient_ids:
            patient = Patient.query.get(patient_id)
            if patient:
                patient.status = status
                updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Updated {updated_count} patients to {status}'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        })