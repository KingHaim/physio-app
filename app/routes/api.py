from flask import Blueprint, jsonify, current_app, request
import requests
from datetime import datetime, timedelta
from app.models import Treatment, Treatment as Appointment, Patient, UnmatchedCalendlyBooking, PatientReport
from app import db
from sqlalchemy.sql import func, or_
import os
import json
from flask_login import login_required, current_user

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
                
                # Check if appointment already exists based on created_at date/time
                existing_appointment = Treatment.query.filter_by(
                    patient_id=patient.id,
                    created_at=start_time
                ).first()
                
                if not existing_appointment:
                    # Create new appointment (Treatment)
                    appointment = Treatment(
                        patient_id=patient.id,
                        created_at=start_time,
                        treatment_type=event_type,
                        status="Scheduled",
                        notes=f"Booked via Calendly. Duration: {int((end_time - start_time).total_seconds() / 60)} minutes.",
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
            created_at=booking.start_time,
            patient_id=patient_id
        ).first()
        
        if not existing_treatment:
            # Create a new treatment record
            # Get the invitee URI from the booking (assuming it's stored)
            # Note: Ensure 'calendly_invitee_id' actually holds the full URI. If not, adjust where it's fetched from.
            invitee_uri = booking.calendly_invitee_id  # <<< Assuming this holds the URI

            treatment = Treatment(
                patient_id=patient_id,
                created_at=booking.start_time,
                treatment_type=booking.event_type,
                status="Scheduled",
                notes=f"Linked to Calendly booking. Matched by admin user.",
                calendly_invitee_uri=invitee_uri # <<< Add the URI here
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

@api.route('/treatments/<int:treatment_id>')
@login_required
def get_treatment(treatment_id):
    treatment = Treatment.query.get_or_404(treatment_id)
    
    # Check if user has permission to view this treatment
    if not current_user.is_admin and treatment.patient.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    treatment_data = {
        'id': treatment.id,
        'patient_id': treatment.patient_id,
        'treatment_type': treatment.treatment_type,
        'assessment': treatment.assessment,
        'notes': treatment.notes,
        'status': treatment.status,
        'provider': treatment.provider,
        'created_at': treatment.created_at.isoformat() if treatment.created_at else None,
        'updated_at': treatment.updated_at.isoformat() if treatment.updated_at else None,
        'body_chart_url': treatment.body_chart_url if hasattr(treatment, 'body_chart_url') else None
    }
    
    return jsonify(treatment_data)

@api.route('/api/appointment/<int:id>/status', methods=['POST'])
def update_appointment_status(id):
    try:
        data = request.json
        status = data.get('status')
        
        if not status:
            return jsonify({'success': False, 'error': 'Status not provided'})
        
        appointment = Treatment.query.get_or_404(id)
        appointment.status = status
        
        # If marking as completed, set the date to today if not already set
        if status == 'Completed' and not appointment.created_at:
            appointment.created_at = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'id': appointment.id,
            'status': appointment.status
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

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
            (Treatment.created_at < today)  # Consider past treatments as completed
        ).order_by(Treatment.created_at).all()
        
        if not treatments:
            print(f"No completed or past treatments found for patient {id}")
            
            # Check if there are any treatments at all
            all_treatments = Treatment.query.filter_by(patient_id=id).order_by(Treatment.created_at).all()
            
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
        
        # Extract initial and latest pain levels if available
        initial_pain = None
        latest_pain = None
        
        for t in treatments:
            if t.pain_level is not None:
                if initial_pain is None:
                    initial_pain = t.pain_level
                latest_pain = t.pain_level
        
        # Calculate treatment duration
        first_date = treatments[0].created_at if treatments else None
        last_date = treatments[-1].created_at if treatments else None
        treatment_duration = None
        
        if first_date and last_date:
            duration_days = (last_date - first_date).days
            if duration_days < 7:
                treatment_duration = f"{duration_days} days"
            elif duration_days < 30:
                treatment_duration = f"{duration_days // 7} weeks, {duration_days % 7} days"
            else:
                treatment_duration = f"{duration_days // 30} months, {(duration_days % 30) // 7} weeks"
        
        # Prepare the prompt for the AI with more structured data
        prompt = f"""
        # PATIENT INFORMATION
        - Diagnosis: {patient.diagnosis}
        - Treatment Plan: {patient.treatment_plan}
        - Total Treatment Sessions: {len(treatments)}
        - Treatment Duration: {treatment_duration or 'N/A'}
        - Initial Pain Level: {initial_pain or 'Not recorded'}
        - Latest Pain Level: {latest_pain or 'Not recorded'}
        
        # DETAILED TREATMENT HISTORY
        """
        
        for idx, t in enumerate(treatments, 1):
            prompt += f"""
        ## Session {idx}: {t.created_at.strftime('%Y-%m-%d')}
        - Treatment Type: {t.treatment_type}
        - Progress Notes: {t.notes or 'None'}
        - Pain Level: {t.pain_level or 'Not recorded'} / 10
        - Movement Restriction: {t.movement_restriction or 'None recorded'}
        - Status: {t.status}
        """
            
            # Include trigger point information if available
            if hasattr(t, 'trigger_points') and t.trigger_points:
                prompt += "\n        - Trigger Points:\n"
                for tp in t.trigger_points:
                    prompt += f"          * {tp.muscle or 'Unspecified muscle'} (Intensity: {tp.intensity or 'N/A'}/10, Type: {tp.type or 'unspecified'})\n"
                    if tp.symptoms:
                        prompt += f"            Symptoms: {tp.symptoms}\n"
        
        prompt += """
        # REPORT GENERATION INSTRUCTIONS
        
        As a professional physiotherapist, please generate a comprehensive physiotherapy treatment progress report based on the above information. The report should include:
        
        1. PATIENT OVERVIEW: Brief introduction to the patient and their presenting condition
        
        2. CLINICAL ASSESSMENT:
           - Initial assessment findings and baseline measurements
           - Key impairments identified
           - Functional limitations observed
        
        3. TREATMENT APPROACH:
           - Overview of physiotherapy interventions provided
           - Specific techniques and modalities used
           - Progression of treatment over time
        
        4. PROGRESS EVALUATION:
           - Changes in pain levels with detailed comparison between initial and current state
           - Improvements in range of motion and functional capacity
           - Response to specific treatment techniques
        
        5. CURRENT STATUS:
           - Present physical condition
           - Remaining impairments and functional limitations
           - Self-management capabilities
        
        6. RECOMMENDATIONS:
           - Required further treatment (if applicable)
           - Home exercise program suggestions
           - Activity modifications and ergonomic advice
           - Preventative strategies to avoid recurrence
        
        7. PROGNOSIS:
           - Expected timeline for full recovery
           - Factors potentially influencing recovery
           - Long-term outlook
        
        Format the report with clear markdown headings, bullet points, and short paragraphs for optimal readability. Use physiotherapy-specific terminology while ensuring the report remains accessible to the patient and other healthcare providers.
        
        End the report with:
        
        ---
        
        **Haim Ganancia, Physiotherapist**  
        ICPFA 7595   
        Report Date: {datetime.now().strftime('%Y-%m-%d')}
        """
        
        # Call the DeepSeek API
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        
        if not api_key:
            print("No DeepSeek API key found in environment variables")
            
            # Try to read from .env file
            try:
                with open('.env', 'r') as file:
                    for line in file:
                        if line.startswith('DEEPSEE_API_KEY='):
                            api_key = line.strip().split('=', 1)[1].strip('"\'')
                            break
            except FileNotFoundError:
                print(".env file not found")
            
            if not api_key:
                print("No DeepSeek API key found in .env file")
                # Generate a fallback report
                report_content = generate_fallback_report(treatments)
                report_type = 'Fallback Report (No API Key)'
        else:
            try:
                print(f"Calling DeepSeek API for patient {id}")
                
                # Get the API endpoint, defaulting to the main endpoint if not specified
                api_endpoint = os.environ.get('DEEPSEEK_API_ENDPOINT', 'https://api.deepseek.com/v1/chat/completions')
                
                # Try to read from working_endpoint.txt if it exists
                try:
                    with open('working_endpoint.txt', 'r') as file:
                        saved_endpoint = file.read().strip()
                        if saved_endpoint:
                            api_endpoint = saved_endpoint
                            print(f"Using saved endpoint from working_endpoint.txt: {api_endpoint}")
                except FileNotFoundError:
                    print("No working_endpoint.txt file found, using default or environment endpoint")
                
                print(f"Using API endpoint: {api_endpoint}")
                print(f"Using API key (first 4 chars): {api_key[:4]}...")
                
                # Increase timeout to 60 seconds
                response = requests.post(
                    api_endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": "You are a professional physiotherapist with expertise in creating detailed, evidence-based treatment progress reports. You use precise physiotherapy terminology while ensuring your reports remain clear and accessible."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,  # Lower temperature for more consistent, factual reports
                        "max_tokens": 4000   # Increased token limit for more detailed reports
                    },
                    timeout=90  # Increased timeout for longer reports
                )
                
                print(f"DeepSeek API response status: {response.status_code}")
                
                if response.status_code != 200:
                    print(f"Error from DeepSeek API: {response.text}")
                    # Add more detailed error logging
                    print(f"Full error details: Status: {response.status_code}, Content: {response.content}")
                    print(f"API Key (first 4 chars): {api_key[:4]}...")
                    
                    # Try alternative endpoints if the main one fails
                    alternative_endpoints = [
                        "https://api.deepseek.ai/v1/chat/completions",
                        "https://api.deepseek.com/v1/completions",
                        "https://api.deepseek.chat/v1/chat/completions"
                    ]
                    
                    # Skip the endpoint we just tried
                    if api_endpoint in alternative_endpoints:
                        alternative_endpoints.remove(api_endpoint)
                    
                    success = False
                    for alt_endpoint in alternative_endpoints:
                        print(f"Trying alternative endpoint: {alt_endpoint}")
                        try:
                            alt_response = requests.post(
                                alt_endpoint,
                                headers={
                                    "Authorization": f"Bearer {api_key}",
                                    "Content-Type": "application/json"
                                },
                                json={
                                    "model": "deepseek-chat",
                                    "messages": [
                                        {"role": "system", "content": "You are a professional physiotherapist."},
                                        {"role": "user", "content": prompt}
                                    ],
                                    "temperature": 0.3,
                                    "max_tokens": 4000
                                },
                                timeout=90
                            )
                            
                            if alt_response.status_code == 200:
                                print(f"Successfully connected to alternative endpoint: {alt_endpoint}")
                                response = alt_response
                                success = True
                                
                                # Save the working endpoint for future use
                                with open('working_endpoint.txt', 'w') as file:
                                    file.write(alt_endpoint)
                                    
                                break
                            else:
                                print(f"Alternative endpoint failed: {alt_response.status_code} - {alt_response.text}")
                        except Exception as alt_e:
                            print(f"Error with alternative endpoint: {str(alt_e)}")
                    
                    if not success:
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
    
    # Extract initial and latest pain levels
    initial_pain = None
    latest_pain = None
    pain_trend = "N/A"
    
    for t in treatments:
        if t.pain_level is not None:
            if initial_pain is None:
                initial_pain = t.pain_level
            latest_pain = t.pain_level
    
    if initial_pain is not None and latest_pain is not None:
        if latest_pain < initial_pain:
            pain_diff = initial_pain - latest_pain
            pain_trend = f"Improved by {pain_diff} points"
        elif latest_pain > initial_pain:
            pain_diff = latest_pain - initial_pain
            pain_trend = f"Worsened by {pain_diff} points"
        else:
            pain_trend = "Remained stable"
    
    # Calculate treatment duration
    first_date = treatments[0].created_at.strftime('%Y-%m-%d') if treatments else "N/A"
    last_date = treatments[-1].created_at.strftime('%Y-%m-%d') if treatments else "N/A"
    
    treatment_duration = "N/A"
    if len(treatments) > 1:
        days = (treatments[-1].created_at - treatments[0].created_at).days
        if days < 7:
            treatment_duration = f"{days} days"
        elif days < 30:
            treatment_duration = f"{days // 7} weeks, {days % 7} days"
        else:
            treatment_duration = f"{days // 30} months, {(days % 30) // 7} weeks"
    
    # Count treatment types
    treatment_types = {}
    for t in treatments:
        t_type = t.treatment_type
        if t_type in treatment_types:
            treatment_types[t_type] += 1
        else:
            treatment_types[t_type] = 1
            
    # Format most used treatment types
    treatment_summary = "\n".join([f"- {t_type}: {count} session(s)" for t_type, count in sorted(treatment_types.items(), key=lambda x: x[1], reverse=True)])
    
    content = f"""# Physiotherapy Treatment Report

## Summary
This automatically generated report summarizes the physiotherapy treatment history. This is a basic report generated when AI report generation is unavailable.

## Patient Treatment Overview
- **Treatment Period**: {first_date} to {last_date}
- **Duration**: {treatment_duration}
- **Total Sessions**: {len(treatments)}
- **Initial Pain Level**: {initial_pain if initial_pain is not None else 'Not recorded'}/10
- **Current Pain Level**: {latest_pain if latest_pain is not None else 'Not recorded'}/10
- **Pain Trend**: {pain_trend}

## Treatment Approaches
{treatment_summary}

## Detailed Treatment History
"""
    
    for idx, t in enumerate(treatments, 1):
        session_date = t.created_at.strftime('%Y-%m-%d')
        content += f"""
### Session {idx}: {session_date}

**Treatment Type:** {t.treatment_type}

**Progress Notes:** {t.notes or 'None recorded'}

**Pain Level:** {t.pain_level if t.pain_level is not None else 'Not recorded'}/10

**Movement Restriction:** {t.movement_restriction or 'None recorded'}

**Status:** {t.status}
"""
        # Add trigger point information if available
        if hasattr(t, 'trigger_points') and t.trigger_points:
            content += "\n**Trigger Points Addressed:**\n"
            for tp in t.trigger_points:
                content += f"- {tp.muscle or 'Unspecified muscle'} (Intensity: {tp.intensity or 'N/A'}/10, Type: {tp.type or 'unspecified'})\n"
    
    content += f"""
## Recommendations
Based on the treatment history, it is recommended to continue with the therapeutic approaches that have shown positive outcomes. Follow-up sessions may be necessary to maintain progress and prevent recurrence of symptoms.

---

**Haim Ganancia, PT**  
CostaSpine Physiotherapy Clinic  
Report Date: {today}
"""
    
    return content

@api.route('/api/patient/<int:id>/mark-past-as-completed', methods=['POST'])
def mark_past_as_completed(id):
    try:
        today = datetime.now().date()
        
        # Find all past treatments that aren't already completed
        past_treatments = Treatment.query.filter(
            Treatment.patient_id == id,
            Treatment.created_at < today,
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
    # It's crucial to verify the webhook signature in a production environment!
    # See Calendly docs: https://developer.calendly.com/docs/webhook-signatures
    # For now, we skip signature verification for simplicity.
    
    try:
        data = request.json
        event_type = data.get('event')
        payload = data.get('payload', {})

        print(f"Received Calendly Webhook - Event: {event_type}") # Add logging

        # --- Handle Invitee Creation --- 
        if event_type == 'invitee.created':
            invitee = payload.get('invitee', {})
            event = payload.get('event', {})
            invitee_uri = invitee.get('uri') # Get URI for potential future use
            invitee_uuid = invitee.get('uuid') # Use UUID for checking existing bookings

            if not invitee_uuid:
                print("Webhook Error: invitee.created payload missing invitee.uuid")
                return jsonify({'status': 'error', 'message': 'Missing invitee UUID'}), 400

            # Check if this booking already exists based on UUID
            existing_booking = UnmatchedCalendlyBooking.query.filter_by(
                calendly_invitee_id=invitee_uuid # Assuming this field stores the UUID
            ).first()
            
            if existing_booking:
                print(f"Webhook Info: Booking with UUID {invitee_uuid} already processed.")
                return jsonify({'status': 'ignored', 'reason': 'Booking already processed'})
            
            # Create a new unmatched booking
            start_time_str = invitee.get('start_time')
            end_time_str = invitee.get('end_time')
            
            # Basic validation for required fields
            if not all([invitee.get('name'), invitee.get('email'), event.get('name'), start_time_str, end_time_str]):
                print("Webhook Error: invitee.created payload missing required fields")
                return jsonify({'status': 'error', 'message': 'Missing required booking fields'}), 400
            
            booking = UnmatchedCalendlyBooking(
                calendly_invitee_id=invitee_uuid, # Store UUID here
                name=invitee.get('name'),
                email=invitee.get('email'),
                event_type=event.get('name'),
                start_time=datetime.fromisoformat(start_time_str.replace('Z', '+00:00')),
                # We might not need end_time in the model, but it's in the payload
                # end_time=datetime.fromisoformat(end_time_str.replace('Z', '+00:00')),
                status='Pending',
                # raw_data=json.dumps(data) # Optional: store raw payload for debugging
            )
            
            db.session.add(booking)
            db.session.flush() # Flush to get booking ID if needed, though we might not
            
            # Try to automatically match to an existing patient
            patient = find_matching_patient(booking.name, booking.email)
            
            if patient:
                # Automatically match and create treatment
                booking.status = 'Matched'
                booking.matched_patient_id = patient.id
                
                # Check if treatment already exists (redundancy check)
                existing_treatment = Treatment.query.filter_by(
                    created_at=booking.start_time,
                    patient_id=patient.id
                ).first()

                if not existing_treatment:
                    # Create a treatment record, storing the INVITE URI
                    treatment = Treatment(
                        patient_id=patient.id,
                        created_at=booking.start_time, 
                        treatment_type=booking.event_type, 
                        status="Scheduled",
                        notes=f"Linked to Calendly booking. Auto-matched via webhook.",
                        calendly_invitee_uri=invitee_uri # Store the full Invitee URI here
                    )
                    db.session.add(treatment)
                    print(f"Webhook Info: Created and matched Treatment for patient {patient.id} from invitee {invitee_uri}")
                else:
                     print(f"Webhook Info: Treatment already exists for patient {patient.id} at {booking.start_time}. Skipping creation.")
            else:
                print(f"Webhook Info: Created UnmatchedCalendlyBooking for {invitee_uuid}. Needs manual matching.")
            
            db.session.commit()
            return jsonify({
                'status': 'success', 
                'message': 'Booking created and processed',
                'matched': bool(patient)
            })
        
        # --- Handle Invitee Cancellation --- 
        elif event_type == 'invitee.canceled':
            invitee = payload.get('invitee', {})
            invitee_uri = invitee.get('uri')
            cancellation_reason = invitee.get('cancellation', {}).get('reason', 'N/A')
            canceler_name = invitee.get('cancellation', {}).get('canceled_by', 'Unknown')
            
            if not invitee_uri:
                print("Webhook Error: invitee.canceled payload missing invitee.uri")
                return jsonify({'status': 'error', 'message': 'Missing invitee URI in cancellation payload'}), 400
            
            print(f"Webhook Info: Processing cancellation for invitee URI: {invitee_uri}")
            
            # Find the corresponding treatment using the invitee URI
            treatment_to_cancel = Treatment.query.filter_by(calendly_invitee_uri=invitee_uri).first()
            
            if treatment_to_cancel:
                if treatment_to_cancel.status != 'Cancelled': # Avoid redundant updates
                    old_status = treatment_to_cancel.status
                    treatment_to_cancel.status = 'Cancelled'
                    
                    # Optionally, add a note about the cancellation
                    cancellation_note = f"\n--- CANCELLATION (via Webhook) ---\
Canceled by: {canceler_name}\
Reason: {cancellation_reason}"
                    treatment_to_cancel.notes = (treatment_to_cancel.notes or "") + cancellation_note
                    
                    db.session.commit()
                    print(f"Webhook Success: Updated Treatment ID {treatment_to_cancel.id} status from '{old_status}' to Cancelled for invitee {invitee_uri}.")
                    return jsonify({'status': 'success', 'message': 'Treatment status updated to Cancelled'})
                else:
                    print(f"Webhook Info: Treatment ID {treatment_to_cancel.id} already Cancelled for invitee {invitee_uri}. No action needed.")
                    return jsonify({'status': 'ignored', 'reason': 'Treatment already cancelled'})
            else:
                # Treatment not found - maybe it was never matched or already deleted?
                # Check if an UnmatchedCalendlyBooking exists for this URI (or UUID if URI not stored there)
                # Assuming UnmatchedCalendlyBooking stores UUID in calendly_invitee_id
                invitee_uuid = invitee_uri.split('/')[-1] # Extract UUID from URI
                unmatched_booking = UnmatchedCalendlyBooking.query.filter_by(calendly_invitee_id=invitee_uuid).first()
                
                if unmatched_booking and unmatched_booking.status == 'Pending':
                    # If the booking was pending and now cancelled, we can ignore or delete it
                    unmatched_booking.status = 'Ignored' # Or db.session.delete(unmatched_booking)
                    db.session.commit()
                    print(f"Webhook Info: Marked Pending UnmatchedCalendlyBooking {unmatched_booking.id} (UUID: {invitee_uuid}) as Ignored due to cancellation.")
                    return jsonify({'status': 'success', 'message': 'Pending unmatched booking marked as Ignored'})
                else:
                    print(f"Webhook Warning: No matching Treatment or Pending UnmatchedBooking found for cancelled invitee URI: {invitee_uri}")
                    return jsonify({'status': 'ignored', 'reason': 'No active treatment or pending booking found for this invitee URI'})
        
        # --- Handle Other Event Types (Optional) --- 
        else:
            print(f"Webhook Info: Ignoring event type: {event_type}")
            return jsonify({'status': 'ignored', 'reason': f'Event type {event_type} not handled'})
        
    except Exception as e:
        db.session.rollback()
        # Log the error thoroughly
        import traceback
        print(f"!!! Webhook Error: {str(e)}")
        print(traceback.format_exc())
        # Also log the raw request data if possible (be mindful of sensitive info)
        try:
            print(f"Webhook Raw Data: {request.data}")
        except: # noqa
            print("Webhook Raw Data: Could not read request data.")
            
        return jsonify({'status': 'error', 'message': 'Internal server error processing webhook'}), 500

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
                    created_at=booking.start_time,
                    patient_id=patient.id
                ).first()
                
                if not existing_treatment:
                    # Create a new treatment record
                    # Get the invitee URI from the Calendly event data fetched during the sync process.
                    # Placeholder: Assume 'invitee_uri' is available from the synced event data.
                    # Example: invitee_uri = synced_event_data.get('invitee_uri')

                    treatment = Treatment(
                        patient_id=patient.id,
                        created_at=booking.start_time, # Or use synced_event_data['start_time']
                        treatment_type=booking.event_type, # Or use synced_event_data['event_type']
                        status="Scheduled",
                        notes=f"Linked to Calendly booking via sync.",
                        # calendly_invitee_uri=invitee_uri # Uncomment and assign when invitee_uri is available
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

@api.route('/api/treatments', methods=['POST'])
@login_required
def create_treatment():
    data = request.json
    
    # Get required fields
    patient_id = data.get('patient_id')
    treatment_type = data.get('treatment_type')
    
    # Get optional fields
    pain_level = data.get('pain_level')  # This can be None
    
    # Create treatment
    treatment = Treatment(
        patient_id=patient_id,
        treatment_type=treatment_type,
        pain_level=pain_level,  # This can be None
        # Other fields...
    )
    
    db.session.add(treatment)
    db.session.commit()
    
    return jsonify({'success': True, 'id': treatment.id})

@api.route('/api/report/<int:id>', methods=['DELETE'])
@login_required
def delete_report(id):
    """Delete a patient report by ID"""
    try:
        # Find the report
        report = PatientReport.query.get_or_404(id)
        
        # Get the patient ID for permission checking if needed
        patient_id = report.patient_id
        
        # Delete the report
        db.session.delete(report)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Report {id} successfully deleted',
            'patient_id': patient_id
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting report: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api.route('/api/patient/<int:id>/generate-exercise-prescription', methods=['POST'])
def generate_exercise_prescription(id):
    try:
        patient = Patient.query.get_or_404(id)
        print(f"Starting exercise prescription generation for patient {id}")

        # Get the last 3 completed or past treatments for recent context
        today = datetime.now().date()
        recent_treatments = Treatment.query.filter(
            Treatment.patient_id == id,
            (Treatment.status == 'Completed') | 
            (Treatment.created_at < today)
        ).order_by(Treatment.created_at.desc()).limit(3).all()
        
        # Reverse list to have oldest first for prompt sequence
        recent_treatments.reverse()

        if not recent_treatments:
            print(f"No recent completed/past treatments found for patient {id} to generate prescription.")
            # Optionally check for diagnosis/plan even without treatments
            if patient.diagnosis or patient.treatment_plan:
                 print("Proceeding with diagnosis/plan only.")
            else:
                return jsonify({
                    'success': False,
                    'message': 'No diagnosis, plan, or recent completed treatments found to generate exercise prescription.'
                })

        print(f"Found {len(recent_treatments)} recent treatments for patient {id}")

        # Prepare the prompt for the AI
        prompt = f"""
        # PATIENT CONTEXT
        - Diagnosis: {patient.diagnosis or 'Not specified'}
        - Treatment Plan Goal: {patient.treatment_plan or 'Not specified'}
        
        # RECENT TREATMENT SUMMARY ({len(recent_treatments)} sessions)
        """
        
        for idx, t in enumerate(recent_treatments, 1):
            prompt += f"""
        ## Session {idx} ({t.created_at.strftime('%Y-%m-%d') if t.created_at else 'N/A'}):
        - Treatment Notes: {t.notes or 'None'}
        - Pain Level: {t.pain_level or 'N/A'} / 10
        - Movement Restriction: {t.movement_restriction or 'None recorded'}
        """
        
        prompt += """
        # EXERCISE PRESCRIPTION INSTRUCTIONS
        
        As a professional physiotherapist, generate a concise home exercise program (HEP) suitable for this patient's current stage based on their diagnosis, treatment plan goal, and the recent session summaries provided. 
        
        The HEP should include 3 to 5 exercises.
        
        For each exercise, clearly specify:
        1.  **Exercise Name:** (e.g., Cat-Cow Stretch, Bridging)
        2.  **Sets & Reps:** (e.g., 2 sets of 10 repetitions)
        3.  **Frequency:** (e.g., Daily, 3 times per week)
        4.  **Hold Time:** (if applicable, e.g., Hold 5 seconds)
        5.  **Key Cues:** Provide 1-2 brief, critical instructions for proper form or safety (e.g., 'Engage core', 'Keep back flat', 'Move within pain-free range').
        
        Ensure the exercises are appropriate for the patient's likely condition based *only* on the information provided. Prioritize safety and foundational movements if details are sparse. Format the prescription clearly using Markdown (e.g., use headings for exercise names, bullet points for details).
        
        Start the prescription directly with the first exercise name. Do not include introductory or concluding remarks outside the exercise list.
        """
        
        # Call the AI Service (adapted from report generation)
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        api_endpoint = os.environ.get('DEEPSEEK_API_ENDPOINT', 'https://api.deepseek.com/v1/chat/completions')
        working_endpoint_file = 'working_endpoint.txt'

        if not api_key:
            # Try reading from .env if not in environment
            try:
                with open('.env', 'r') as file:
                    for line in file:
                        if line.startswith('DEEPSEEK_API_KEY='):
                            api_key = line.strip().split('=', 1)[1].strip('"\'')
                            break
            except FileNotFoundError:
                pass # .env not found, api_key remains None

            if not api_key:
                print("ERROR: DeepSeek API key not found.")
                return jsonify({'success': False, 'message': 'AI service API key not configured.'}) 

        # Try reading working endpoint
        try:
            with open(working_endpoint_file, 'r') as file:
                saved_endpoint = file.read().strip()
                if saved_endpoint:
                    api_endpoint = saved_endpoint
                    print(f"Using saved endpoint: {api_endpoint}")
        except FileNotFoundError:
            print(f"No {working_endpoint_file}, using default/env endpoint: {api_endpoint}")

        try:
            print(f"Calling AI for exercise prescription for patient {id} at {api_endpoint}")
            response = requests.post(
                api_endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat", # Or choose another appropriate model
                    "messages": [
                        {"role": "system", "content": "You are a professional physiotherapist creating clear, concise, and safe home exercise programs based on provided patient context. Focus on accuracy and clarity."}, 
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.5, # Slightly higher temp for some variability but still grounded
                    "max_tokens": 1000   # Adjust as needed for prescription length
                },
                timeout=45 # Adjust timeout as needed
            )

            print(f"AI API response status: {response.status_code}")

            if response.status_code != 200:
                print(f"AI API Error: {response.text}")
                # TODO: Implement endpoint fallback logic if needed, similar to report generation
                return jsonify({'success': False, 'message': f'AI service error: {response.status_code}'})
            
            # Extract prescription content
            try:
                prescription_content = response.json()['choices'][0]['message']['content']
                print(f"Successfully generated exercise prescription content of length {len(prescription_content)}")
                
                # Save the prescription as a PatientReport
                try:
                    homework_report = PatientReport(
                        patient_id=id,
                        content=prescription_content,
                        generated_date=datetime.now(),
                        report_type='Exercise Homework' # New report type
                    )
                    db.session.add(homework_report)
                    db.session.commit()
                    print(f"Exercise homework saved to database with ID {homework_report.id}")
                except Exception as db_err:
                    db.session.rollback()
                    print(f"Database error saving exercise homework: {db_err}")
                    # Return success but maybe indicate saving failed?
                    # For now, return success but don't guarantee it saved.
                    # Consider adding a warning message in the response.
                return jsonify({
                    'success': True,
                    'prescription': prescription_content
                })
                
            except (KeyError, IndexError, ValueError) as e:
                print(f"Error parsing AI API response: {str(e)}")
                return jsonify({'success': False, 'message': 'Error parsing AI response.'})

        except requests.exceptions.Timeout:
            print("AI API request timed out for exercise prescription")
            return jsonify({'success': False, 'message': 'AI service request timed out.'})
        except requests.exceptions.RequestException as e:
            print(f"AI API request exception: {str(e)}")
            return jsonify({'success': False, 'message': 'Could not connect to AI service.'})

    except Exception as e:
        db.session.rollback() # Just in case, though unlikely needed here
        print(f"Exception in generate_exercise_prescription: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'An internal error occurred generating the prescription.'
        })

# --- API Endpoint to Set Payment Method ---
@api.route('/api/treatment/<int:id>/set-payment', methods=['POST'])
@login_required # Ensure user is logged in
def set_treatment_payment_method(id):
    """Sets the payment method for a specific treatment."""
    try:
        data = request.get_json()
        payment_method = data.get('payment_method')

        if not payment_method or payment_method not in ['Cash', 'Card']:
            return jsonify({'success': False, 'message': 'Invalid or missing payment_method.'}), 400

        treatment = Treatment.query.get_or_404(id)

        # Optionally, check if the payment method is already set?
        # if treatment.payment_method:
        #     return jsonify({'success': False, 'message': 'Payment method already set.'}), 409 # 409 Conflict

        treatment.payment_method = payment_method
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Payment method for treatment {id} set to {payment_method}.'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error setting payment method for treatment {id}: {e}")
        return jsonify({'success': False, 'message': 'An internal server error occurred.'}), 500

@api.route('/api/treatment/<int:id>/set-fee', methods=['POST'])
@login_required
def set_treatment_fee(id):
    """Sets the fee for a specific treatment."""
    print(f"--- set_treatment_fee START for ID: {id} ---") # Log start
    treatment = Treatment.query.get_or_404(id)
    data = None # Initialize data
    try:
        # Log raw data if possible (might be empty if not JSON)
        raw_data = request.get_data(as_text=True)
        print(f"Raw request data: {raw_data}")
        # Try getting JSON
        data = request.get_json()
        print(f"Parsed JSON data: {data}")
    except Exception as json_err:
        print(f"!!! Error parsing JSON: {json_err} !!!")
        # Return a specific error if JSON parsing fails
        return jsonify({'success': False, 'message': f'Invalid request format: {json_err}'}), 400

    if not data or 'fee' not in data:
        print("Missing 'fee' key in JSON data.")
        return jsonify({'success': False, 'message': 'Missing fee amount in request.'}), 400
        
    fee_input = data['fee']
    print(f"Fee value received: {fee_input} (Type: {type(fee_input)})")

    try:
        fee_value = float(fee_input)
        print(f"Fee value successfully converted to float: {fee_value}")
        if fee_value < 0:
             print("Fee value is negative.")
             return jsonify({'success': False, 'message': 'Fee cannot be negative.'}), 400
             
        treatment.fee_charged = fee_value
        db.session.commit()
        print(f"Fee successfully updated in DB for treatment {id}")
        return jsonify({'success': True, 'message': 'Fee updated successfully.', 'new_fee': fee_value})
    except ValueError:
         print(f"ValueError converting fee '{fee_input}' to float.")
         return jsonify({'success': False, 'message': 'Invalid fee amount provided.'}), 400
    except Exception as e:
        db.session.rollback()
        print(f"!!! UNEXPECTED Error setting fee for treatment {id}: {e} !!!")
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

# --- API Endpoint to Set Location (and potentially auto-set fee) ---
@api.route('/api/treatment/<int:id>/set-location', methods=['POST'])
@login_required
def set_treatment_location(id):
    """Sets the location for a specific treatment. 
       If location is 'CostaSpine Clinic', automatically sets the fee based on patient history.
    """
    print(f"--- set_treatment_location START for ID: {id} ---")
    treatment = Treatment.query.options(db.joinedload(Treatment.patient)).get_or_404(id)
    patient_id = treatment.patient_id
    data = None
    auto_set_fee = None # To return the fee if auto-set

    try:
        data = request.get_json()
        print(f"Parsed JSON data: {data}")
        location_value = data.get('location')

        if not location_value or location_value not in ['CostaSpine Clinic', 'Home Visit']:
            print("Invalid or missing location value.")
            return jsonify({'success': False, 'message': 'Invalid or missing location.'}), 400

        # Set the location
        treatment.location = location_value
        print(f"Location set to: {location_value}")

        # --- Auto-Fee Logic for CostaSpine Clinic ---
        if location_value == 'CostaSpine Clinic':
            # Find the earliest treatment for this specific patient
            earliest_patient_treatment = Treatment.query.filter_by(patient_id=patient_id).order_by(Treatment.created_at.asc(), Treatment.id.asc()).first()
            earliest_treatment_id = earliest_patient_treatment.id if earliest_patient_treatment else None

            # Set fee based on whether it's the patient's absolute earliest treatment
            if earliest_treatment_id is not None and treatment.id == earliest_treatment_id:
                treatment.fee_charged = 80.00
                auto_set_fee = 80.00
                print(f"Auto-setting fee to 80 for treatment {treatment.id} (earliest)")
            else:
                treatment.fee_charged = 70.00
                auto_set_fee = 70.00
                print(f"Auto-setting fee to 70 for treatment {treatment.id}")
        # --- End Auto-Fee Logic ---

        db.session.commit()
        print(f"Location and potentially fee updated in DB for treatment {id}")
        
        response_data = {
            'success': True, 
            'message': 'Location updated successfully.',
            'location': treatment.location # Return the set location
        }
        # Include the auto-set fee in the response if it was set
        if auto_set_fee is not None:
            response_data['auto_set_fee'] = auto_set_fee
            response_data['message'] += f' Fee automatically set to £{auto_set_fee:.2f}.'
        
        return jsonify(response_data)

    except Exception as e:
        db.session.rollback()
        print(f"!!! UNEXPECTED Error setting location for treatment {id}: {e} !!!")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

# --- Analytics API Endpoints ---

# Helper to get start of month
def start_of_month(dt):
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

@api.route('/api/analytics/treatments-by-month')
@login_required
def treatments_by_month():
    try:
        # Get counts grouped by month
        data = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.count(Treatment.id).label('count')
        ).group_by('month').order_by('month').all()
        
        # Convert to list of dicts
        result = [{'month': item.month, 'count': item.count} for item in data]
        return jsonify(result)
    except Exception as e:
        print(f"Error fetching treatments-by-month: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/patients-by-month')
@login_required
def patients_by_month():
    try:
        # Get counts grouped by month
        data = db.session.query(
            func.strftime('%Y-%m', Patient.created_at).label('month'),
            func.count(Patient.id).label('count')
        ).group_by('month').order_by('month').all()
        
        result = [{'month': item.month, 'count': item.count} for item in data]
        return jsonify(result)
    except Exception as e:
        print(f"Error fetching patients-by-month: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/revenue-by-visit-type')
@login_required
def revenue_by_visit_type():
    try:
        data = db.session.query(
            Treatment.visit_type.label('treatment_type'), # Use visit_type
            func.sum(Treatment.fee_charged).label('total_fee')
        ).filter(Treatment.fee_charged.isnot(None))\
         .group_by(Treatment.visit_type)\
         .order_by(func.sum(Treatment.fee_charged).desc())\
         .all()
        
        result = [{'treatment_type': item.treatment_type or 'Uncategorized', 'total_fee': float(item.total_fee or 0)} for item in data]
        return jsonify(result)
    except Exception as e:
        print(f"Error fetching revenue-by-visit-type: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/revenue-by-location')
@login_required
def revenue_by_location():
    try:
        data = db.session.query(
            Treatment.location.label('location'),
            func.sum(Treatment.fee_charged).label('total_fee')
        ).filter(Treatment.fee_charged.isnot(None))\
        .group_by(Treatment.location)\
        .order_by(func.sum(Treatment.fee_charged).desc())\
        .limit(10)\
        .all()
        
        result = [{'location': item.location or 'Unknown', 'total_fee': float(item.total_fee or 0)} for item in data]
        return jsonify(result)
    except Exception as e:
        print(f"Error fetching revenue-by-location: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/common-diagnoses')
@login_required
def common_diagnoses():
    try:
        data = db.session.query(
            Patient.diagnosis.label('diagnosis'),
            func.count(Patient.id).label('count')
        ).filter(Patient.diagnosis.isnot(None), Patient.diagnosis != '')\
        .group_by(Patient.diagnosis)\
        .order_by(func.count(Patient.id).desc())\
        .limit(7)\
        .all()
        
        result = [{'diagnosis': item.diagnosis, 'count': item.count} for item in data]
        return jsonify(result)
    except Exception as e:
        print(f"Error fetching common-diagnoses: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/patient-status')
@login_required
def patient_status_distribution():
    try:
        active_count = Patient.query.filter_by(status='Active').count()
        inactive_count = Patient.query.filter_by(status='Inactive').count()
        # Add other statuses if needed
        
        return jsonify({'active': active_count, 'inactive': inactive_count})
    except Exception as e:
        print(f"Error fetching patient-status: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/payment-methods')
@login_required
def payment_method_distribution():
    try:
        data = db.session.query(
            Treatment.payment_method.label('payment_method'),
            func.count(Treatment.id).label('count')
        ).filter(Treatment.payment_method.isnot(None), Treatment.payment_method != '')\
         .group_by(Treatment.payment_method)\
         .order_by(func.count(Treatment.id).desc())\
         .all()
         
        result = [{'payment_method': item.payment_method, 'count': item.count} for item in data]
        return jsonify(result)
    except Exception as e:
        print(f"Error fetching payment-methods: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/costaspine-fee-data')
@login_required
def get_costaspine_fee_data():
    """Returns the total fee charged per month for CostaSpine Clinic treatments."""
    try:
        # Group fees by month for CostaSpine Clinic
        monthly_fee_data = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.sum(Treatment.fee_charged).label('total_fee')
        ).filter(
            Treatment.location == 'CostaSpine Clinic',
            Treatment.fee_charged.isnot(None)
        ).group_by(func.strftime('%Y-%m', Treatment.created_at))\
         .order_by(func.strftime('%Y-%m', Treatment.created_at)).all()
        
        # Convert to a list of dictionaries
        results = [
            {'month': record.month, 'total_fee': float(record.total_fee)}
            for record in monthly_fee_data
        ]
        
        return jsonify(results)
    except Exception as e:
        print(f"Error fetching CostaSpine monthly fee data: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/recently-inactive-patients')
@login_required
def recently_inactive_patients():
    """Returns the count and list of patients made inactive in the last 7 days."""
    try:
        # Calculate the date 7 days ago
        one_week_ago = datetime.utcnow() - timedelta(days=7)

        # Query for patients who became inactive recently
        inactive_patients = Patient.query.filter(
            Patient.status == 'Inactive',
            Patient.updated_at >= one_week_ago
        ).order_by(Patient.updated_at.desc()).all()

        count = len(inactive_patients)
        patient_list = [
            {'id': p.id, 'name': p.name, 'inactive_since': p.updated_at.isoformat()} 
            for p in inactive_patients
        ]

        return jsonify({
            'count': count,
            'patients': patient_list
        })

    except Exception as e:
        print(f"Error fetching recently inactive patients: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/top-patients-by-revenue')
@login_required
def top_patients_by_revenue():
    """Returns the top N patients ranked by total revenue generated."""
    try:
        top_n = 10 # Define how many top patients to show

        patient_revenue = db.session.query(
            Patient.name.label('patient_name'),
            func.sum(Treatment.fee_charged).label('total_revenue')
        ).join(Treatment, Patient.id == Treatment.patient_id)\
         .filter(Treatment.fee_charged.isnot(None), Treatment.fee_charged > 0)\
         .group_by(Patient.id, Patient.name)\
         .order_by(func.sum(Treatment.fee_charged).desc())\
         .limit(top_n)\
         .all()

        result = [
            {'patient_name': item.patient_name, 'total_revenue': float(item.total_revenue)}
            for item in patient_revenue
        ]

        return jsonify(result)

    except Exception as e:
        print(f"Error fetching top patients by revenue: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500