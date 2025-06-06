from flask import Blueprint, jsonify, current_app, request
import requests
from datetime import datetime, timedelta
from app.models import Treatment, Treatment as Appointment, Patient, UnmatchedCalendlyBooking, PatientReport, Plan, User, UserSubscription
from app import db
from sqlalchemy.sql import func, or_
import os
import json
from flask_login import login_required, current_user
import traceback
import stripe
from flask import url_for

api = Blueprint('api', __name__)

@api.route('/api/sync-calendly-events', methods=['GET'])
@login_required
def sync_calendly_events():
    # Use the current user's Calendly API token and URI
    api_token = current_user.calendly_api_token
    user_calendly_uri_for_events = current_user.calendly_user_uri

    if not api_token:
        return jsonify({'success': False, 'error': 'Your Calendly API token is not configured. Please set it in your profile settings.'}), 400
    if not user_calendly_uri_for_events:
        return jsonify({'success': False, 'error': 'Your Calendly User URI is not configured. This is needed to fetch your specific events. Please set it in your profile settings.'}), 400
    
    try:
        headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36'
        }
        
        # Get scheduled events for the current_user
        min_time = (datetime.utcnow() - timedelta(days=30)).isoformat() + 'Z'
        max_time = (datetime.utcnow() + timedelta(days=60)).isoformat() + 'Z'
        
        events_url = 'https://api.calendly.com/scheduled_events'
        params = {
            'user': user_calendly_uri_for_events, # Use the user's specific URI
            'min_start_time': min_time,
            'max_start_time': max_time,
            'status': 'active',
            'sort': 'start_time:asc' # Good practice to sort
        }
        
        events_response = requests.get(events_url, headers=headers, params=params)
        
        if events_response.status_code != 200:
            error_message = f'Failed to get Calendly events for your account: {events_response.text}'
            try:
                error_details = events_response.json()
                if 'message' in error_details: error_message = f"Calendly API Error: {error_details['message']}"
                if 'details' in error_details and isinstance(error_details['details'], list) and error_details['details']:
                     error_message += f" Details: {error_details['details'][0].get('message', '')}"
                elif 'details' in error_details: error_message += f" Details: {error_details['details']}"

            except ValueError: pass # Keep original text if not JSON
            current_app.logger.error(f"Calendly event fetch error for user {current_user.id}: {error_message}")
            return jsonify({'success': False, 'error': error_message}), events_response.status_code
        
        events = events_response.json()['collection']
        
        synced_treatments_count = 0
        newly_created_unmatched_bookings_count = 0
        
        for event in events:
            event_uri = event['uri']
            event_uuid = event_uri.split('/')[-1] # Calendly event UUID
            
            invitees_url = f'https://api.calendly.com/scheduled_events/{event_uuid}/invitees'
            invitees_response = requests.get(invitees_url, headers=headers)
            
            if invitees_response.status_code != 200:
                current_app.logger.warning(f"Failed to get invitees for event {event_uuid} for user {current_user.id}: {invitees_response.text}")
                continue # Skip this event
            
            invitees = invitees_response.json()['collection']
            
            for invitee in invitees:
                invitee_uri = invitee['uri'] # Calendly invitee URI
                
                # --- MODIFICATION START ---
                # Reliably get invitee_uuid from the invitee_uri
                try:
                    invitee_uuid_for_booking = invitee_uri.split('/')[-1]
                    if not invitee_uuid_for_booking: # Should not happen if URI is valid
                        raise ValueError("Extracted invitee_uuid is empty")
                except (IndexError, ValueError) as e:
                    current_app.logger.error(f"Could not extract invitee_uuid from URI '{invitee_uri}': {e}. Skipping invitee: {invitee}")
                    continue 
                # --- MODIFICATION END ---

                name = invitee['name']
                email = invitee['email']
                start_time = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(event['end_time'].replace('Z', '+00:00'))
                event_type_name = event['name']
                
                # Check if an UnmatchedCalendlyBooking already exists for this invitee_uuid and user
                existing_unmatched_booking = UnmatchedCalendlyBooking.query.filter_by(
                    calendly_invitee_id=invitee_uuid_for_booking, # Storing invitee UUID here
                    user_id=current_user.id
                ).first()

                if existing_unmatched_booking and existing_unmatched_booking.status != 'Pending':
                    current_app.logger.info(f"Skipping already processed (status: {existing_unmatched_booking.status}) unmatched booking for invitee {invitee_uuid_for_booking}, user {current_user.id}")
                    continue

                # Try to find a matching patient (globally for now, or refine later)
                # If your patients are strictly per-physio, this matching needs to be user-scoped.
                patient = find_matching_patient(name, email) 
                
                created_new_treatment = False
                if patient:
                    # Patient exists, check if treatment already exists for this patient and start_time
                    existing_treatment = Treatment.query.filter_by(
                        patient_id=patient.id,
                        created_at=start_time
                        # Consider adding calendly_invitee_uri if it was reliably unique before
                    ).first()
                    
                    if not existing_treatment:
                        new_treatment = Treatment(
                            patient_id=patient.id,
                            created_at=start_time,
                            treatment_type=event_type_name,
                            status="Scheduled",
                            notes=f"Booked via Calendly. Synced by {current_user.username}. Duration: {int((end_time - start_time).total_seconds() / 60)} min.",
                            calendly_invitee_uri=invitee_uri # Store the invitee URI
                        )
                        db.session.add(new_treatment)
                        synced_treatments_count += 1
                        created_new_treatment = True
                        current_app.logger.info(f"Created new Treatment for existing patient {patient.id} by user {current_user.id} from Calendly event {event_uuid}, invitee {invitee_uri}")
                        if existing_unmatched_booking: # If it was pending and now we created a treatment
                            existing_unmatched_booking.status = 'Matched'
                            existing_unmatched_booking.matched_patient_id = patient.id
                    else:
                        current_app.logger.info(f"Treatment already exists for patient {patient.id} at {start_time}. User {current_user.id}, Calendly event {event_uuid}")
                        # If treatment exists, ensure any PENDING unmatched booking is marked Matched
                        if existing_unmatched_booking and existing_unmatched_booking.status == 'Pending':
                             existing_unmatched_booking.status = 'Matched'
                             existing_unmatched_booking.matched_patient_id = patient.id

                else: # No matching patient found, create/update UnmatchedCalendlyBooking
                    if not existing_unmatched_booking:
                        unmatched_booking_record = UnmatchedCalendlyBooking(
                            user_id=current_user.id, # Associate with the current physio
                            name=name,
                            email=email,
                            event_type=event_type_name,
                            start_time=start_time,
                            calendly_invitee_id=invitee_uuid_for_booking, # Store invitee UUID
                            status='Pending'
                        )
                        db.session.add(unmatched_booking_record)
                        newly_created_unmatched_bookings_count += 1
                        current_app.logger.info(f"Created new UnmatchedCalendlyBooking for user {current_user.id}, Calendly invitee {invitee_uuid_for_booking}")
                    # If existing_unmatched_booking is PENDING, we just leave it as is.
            
        db.session.commit()
        
        message = f'Successfully synced Calendly for your account. Created {synced_treatments_count} new treatments/appointments. '
        if newly_created_unmatched_bookings_count > 0:
            message += f'Created {newly_created_unmatched_bookings_count} new items for review.'
        elif synced_treatments_count == 0 and newly_created_unmatched_bookings_count == 0:
             message = 'Your Calendly appointments appear to be up to date. No new items created.'
        
        return jsonify({
            'success': True,
            'message': message,
            'new_treatments': synced_treatments_count,
            'new_unmatched_bookings': newly_created_unmatched_bookings_count
        })
    
    except Exception as e:
        db.session.rollback()
        error_message_for_log = f"Error details: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        current_app.logger.error(f"Error in sync_calendly_events for user {current_user.id if current_user.is_authenticated else 'anonymous'}. {error_message_for_log}")
        return jsonify({
            'success': False,
            'error': f"An unexpected error occurred during Calendly sync: {str(e)}"
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
                patient_id=patient.id,
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
        current_app.logger.info(f"Error in match_calendly_booking: {str(e)}")
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
        current_app.logger.info(f"Starting report generation for patient {id}")

        # Get all completed treatments AND past treatments
        today = datetime.now().date()
        treatments = Treatment.query.filter(
            Treatment.patient_id == id,
            (Treatment.status == 'Completed') | 
            (Treatment.created_at < today)  # Consider past treatments as completed
        ).order_by(Treatment.created_at).all()
        
        if not treatments:
            current_app.logger.info(f"No completed or past treatments found for patient {id}")
            
            # Check if there are any treatments at all
            all_treatments = Treatment.query.filter_by(patient_id=id).order_by(Treatment.created_at).all()
            
            if all_treatments:
                current_app.logger.info(f"Using fallback report with {len(all_treatments)} treatments")
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
                
                current_app.logger.info(f"Fallback report saved to database with ID {report.id}")
                
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
        
        current_app.logger.info(f"Found {len(treatments)} completed/past treatments for patient {id}")
        
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
            current_app.logger.info("No DeepSeek API key found in environment variables")
            
            # Try to read from .env file
            try:
                with open('.env', 'r') as file:
                    for line in file:
                        if line.startswith('DEEPSEE_API_KEY='):
                            api_key = line.strip().split('=', 1)[1].strip('"\'')
                            break
            except FileNotFoundError:
                current_app.logger.info(".env file not found")
            
            if not api_key:
                current_app.logger.info("No DeepSeek API key found in .env file")
                # Generate a fallback report
                report_content = generate_fallback_report(treatments)
                report_type = 'Fallback Report (No API Key)'
        else:
            try:
                current_app.logger.info(f"Calling DeepSeek API for patient {id}")
                
                # Get the API endpoint, defaulting to the main endpoint if not specified
                api_endpoint = os.environ.get('DEEPSEEK_API_ENDPOINT', 'https://api.deepseek.com/v1/chat/completions')
                
                # Try to read from working_endpoint.txt if it exists
                try:
                    with open('working_endpoint.txt', 'r') as file:
                        saved_endpoint = file.read().strip()
                        if saved_endpoint:
                            api_endpoint = saved_endpoint
                            current_app.logger.info(f"Using saved endpoint from working_endpoint.txt: {api_endpoint}")
                except FileNotFoundError:
                    current_app.logger.info("No working_endpoint.txt file found, using default or environment endpoint")
                
                current_app.logger.info(f"Using API endpoint: {api_endpoint}")
                current_app.logger.info(f"Using API key (first 4 chars): {api_key[:4]}...")
                
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
                
                current_app.logger.info(f"DeepSeek API response status: {response.status_code}")
                
                if response.status_code != 200:
                    current_app.logger.info(f"Error from DeepSeek API: {response.text}")
                    # Add more detailed error logging
                    current_app.logger.info(f"Full error details: Status: {response.status_code}, Content: {response.content}")
                    current_app.logger.info(f"API Key (first 4 chars): {api_key[:4]}...")
                    
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
                        current_app.logger.info(f"Trying alternative endpoint: {alt_endpoint}")
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
                                current_app.logger.info(f"Successfully connected to alternative endpoint: {alt_endpoint}")
                                response = alt_response
                                success = True
                                
                                # Save the working endpoint for future use
                                with open('working_endpoint.txt', 'w') as file:
                                    file.write(alt_endpoint)
                                    
                                break
                            else:
                                current_app.logger.info(f"Alternative endpoint failed: {alt_response.status_code} - {alt_response.text}")
                        except Exception as alt_e:
                            current_app.logger.info(f"Error with alternative endpoint: {str(alt_e)}")
                    
                    if not success:
                        # Generate a fallback report
                        report_content = generate_fallback_report(treatments)
                        report_type = 'Fallback Report (API Error)'
                else:
                    # Extract the report content
                    try:
                        report_content = response.json()['choices'][0]['message']['content']
                        report_type = 'AI Generated'
                        current_app.logger.info(f"Successfully generated report content of length {len(report_content)}")
                    except (KeyError, IndexError, ValueError) as e:
                        current_app.logger.info(f"Error parsing API response: {str(e)}")
                        # Generate a fallback report
                        report_content = generate_fallback_report(treatments)
                        report_type = 'Fallback Report (Parse Error)'
                    
            except requests.exceptions.Timeout:
                current_app.logger.info("DeepSeek API request timed out")
                # Generate a fallback report
                report_content = generate_fallback_report(treatments)
                report_type = 'Fallback Report (Timeout)'
            except requests.exceptions.RequestException as e:
                current_app.logger.info(f"Request exception: {str(e)}")
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
        
        current_app.logger.info(f"Report saved to database with ID {report.id}")
        
        return jsonify({
            'success': True,
            'message': 'Report generated successfully',
            'report_id': report.id
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.info(f"Exception in generate_patient_report: {str(e)}")
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

        current_app.logger.info(f"Received Calendly Webhook - Event: {event_type}") # Add logging

        # --- Handle Invitee Creation --- 
        if event_type == 'invitee.created':
            invitee = payload.get('invitee', {})
            event = payload.get('event', {})
            invitee_uri = invitee.get('uri') # Get URI for potential future use
            invitee_uuid = invitee.get('uuid') # Use UUID for checking existing bookings

            if not invitee_uuid:
                current_app.logger.info("Webhook Error: invitee.created payload missing invitee.uuid")
                return jsonify({'status': 'error', 'message': 'Missing invitee UUID'}), 400

            # Check if this booking already exists based on UUID
            existing_booking = UnmatchedCalendlyBooking.query.filter_by(
                calendly_invitee_id=invitee_uuid # Assuming this field stores the UUID
            ).first()
            
            if existing_booking:
                current_app.logger.info(f"Webhook Info: Booking with UUID {invitee_uuid} already processed.")
                return jsonify({'status': 'ignored', 'reason': 'Booking already processed'})
            
            # Create a new unmatched booking
            start_time_str = invitee.get('start_time')
            end_time_str = invitee.get('end_time')
            
            # Basic validation for required fields
            if not all([invitee.get('name'), invitee.get('email'), event.get('name'), start_time_str, end_time_str]):
                current_app.logger.info("Webhook Error: invitee.created payload missing required fields")
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
                    current_app.logger.info(f"Webhook Info: Created and matched Treatment for patient {patient.id} from invitee {invitee_uri}")
                else:
                     current_app.logger.info(f"Webhook Info: Treatment already exists for patient {patient.id} at {booking.start_time}. Skipping creation.")
            else:
                current_app.logger.info(f"Webhook Info: Created UnmatchedCalendlyBooking for {invitee_uuid}. Needs manual matching.")
            
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
                current_app.logger.info("Webhook Error: invitee.canceled payload missing invitee.uri")
                return jsonify({'status': 'error', 'message': 'Missing invitee URI in cancellation payload'}), 400
            
            current_app.logger.info(f"Webhook Info: Processing cancellation for invitee URI: {invitee_uri}")
            
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
                    current_app.logger.info(f"Webhook Success: Updated Treatment ID {treatment_to_cancel.id} status from '{old_status}' to Cancelled for invitee {invitee_uri}.")
                    return jsonify({'status': 'success', 'message': 'Treatment status updated to Cancelled'})
                else:
                    current_app.logger.info(f"Webhook Info: Treatment ID {treatment_to_cancel.id} already Cancelled for invitee {invitee_uri}. No action needed.")
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
                    current_app.logger.info(f"Webhook Info: Marked Pending UnmatchedCalendlyBooking {unmatched_booking.id} (UUID: {invitee_uuid}) as Ignored due to cancellation.")
                    return jsonify({'status': 'success', 'message': 'Pending unmatched booking marked as Ignored'})
                else:
                    current_app.logger.info(f"Webhook Warning: No matching Treatment or Pending UnmatchedBooking found for cancelled invitee URI: {invitee_uri}")
                    return jsonify({'status': 'ignored', 'reason': 'No active treatment or pending booking found for this invitee URI'})
        
        # --- Handle Other Event Types (Optional) --- 
        else:
            current_app.logger.info(f"Webhook Info: Ignoring event type: {event_type}")
            return jsonify({'status': 'ignored', 'reason': f'Event type {event_type} not handled'})
        
    except Exception as e:
        db.session.rollback()
        # Log the error thoroughly
        current_app.logger.info(f"!!! Webhook Error: {str(e)}")
        current_app.logger.info(traceback.format_exc())
        # Also log the raw request data if possible (be mindful of sensitive info)
        try:
            current_app.logger.info(f"Webhook Raw Data: {request.data}")
        except: # noqa
            current_app.logger.info("Webhook Raw Data: Could not read request data.")
            
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
        current_app.logger.info(f"Error in sync_calendly_appointments: {str(e)}")
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
        current_app.logger.info(f"Error deleting report: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api.route('/api/patient/<int:id>/generate-exercise-prescription', methods=['POST'])
def generate_exercise_prescription(id):
    try:
        patient = Patient.query.get_or_404(id)
        current_app.logger.info(f"Starting exercise prescription generation for patient {id}")

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
            current_app.logger.info(f"No recent completed/past treatments found for patient {id} to generate prescription.")
            # Optionally check for diagnosis/plan even without treatments
            if patient.diagnosis or patient.treatment_plan:
                 current_app.logger.info("Proceeding with diagnosis/plan only.")
            else:
                return jsonify({
                    'success': False,
                    'message': 'No diagnosis, plan, or recent completed treatments found to generate exercise prescription.'
                })

        current_app.logger.info(f"Found {len(recent_treatments)} recent treatments for patient {id}")

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
                current_app.logger.info("ERROR: DeepSeek API key not found.")
                return jsonify({'success': False, 'message': 'AI service API key not configured.'}) 

        # Try reading working endpoint
        try:
            with open(working_endpoint_file, 'r') as file:
                saved_endpoint = file.read().strip()
                if saved_endpoint:
                    api_endpoint = saved_endpoint
                    current_app.logger.info(f"Using saved endpoint: {api_endpoint}")
        except FileNotFoundError:
            current_app.logger.info(f"No {working_endpoint_file}, using default/env endpoint: {api_endpoint}")

        try:
            current_app.logger.info(f"Calling AI for exercise prescription for patient {id} at {api_endpoint}")
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

            current_app.logger.info(f"AI API response status: {response.status_code}")

            if response.status_code != 200:
                current_app.logger.info(f"AI API Error: {response.text}")
                # TODO: Implement endpoint fallback logic if needed, similar to report generation
                return jsonify({'success': False, 'message': f'AI service error: {response.status_code}'})
            
            # Extract prescription content
            try:
                prescription_content = response.json()['choices'][0]['message']['content']
                current_app.logger.info(f"Successfully generated exercise prescription content of length {len(prescription_content)}")
                
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
                    current_app.logger.info(f"Exercise homework saved to database with ID {homework_report.id}")
                except Exception as db_err:
                    db.session.rollback()
                    current_app.logger.info(f"Database error saving exercise homework: {db_err}")
                    # Return success but maybe indicate saving failed?
                    # For now, return success but don't guarantee it saved.
                    # Consider adding a warning message in the response.
                return jsonify({
                    'success': True,
                    'prescription': prescription_content
                })
                
            except (KeyError, IndexError, ValueError) as e:
                current_app.logger.info(f"Error parsing AI API response: {str(e)}")
                return jsonify({'success': False, 'message': 'Error parsing AI response.'})

        except requests.exceptions.Timeout:
            current_app.logger.info("AI API request timed out for exercise prescription")
            return jsonify({'success': False, 'message': 'AI service request timed out.'})
        except requests.exceptions.RequestException as e:
            current_app.logger.info(f"AI API request exception: {str(e)}")
            return jsonify({'success': False, 'message': 'Could not connect to AI service.'})

    except Exception as e:
        db.session.rollback() # Just in case, though unlikely needed here
        current_app.logger.info(f"Exception in generate_exercise_prescription: {str(e)}")
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
        current_app.logger.info(f"Error setting payment method for treatment {id}: {e}")
        return jsonify({'success': False, 'message': 'An internal server error occurred.'}), 500

@api.route('/api/treatment/<int:id>/set-fee', methods=['POST'])
@login_required
def set_treatment_fee(id):
    """Sets the fee for a specific treatment."""
    current_app.logger.info(f"--- set_treatment_fee START for ID: {id} ---") # Log start
    treatment = Treatment.query.get_or_404(id)
    data = None # Initialize data
    try:
        # Log raw data if possible (might be empty if not JSON)
        raw_data = request.get_data(as_text=True)
        current_app.logger.info(f"Raw request data: {raw_data}")
        # Try getting JSON
        data = request.get_json()
        current_app.logger.info(f"Parsed JSON data: {data}")
    except Exception as json_err:
        current_app.logger.info(f"!!! Error parsing JSON: {json_err} !!!")
        # Return a specific error if JSON parsing fails
        return jsonify({'success': False, 'message': f'Invalid request format: {json_err}'}), 400

    if not data or 'fee' not in data:
        current_app.logger.info("Missing 'fee' key in JSON data.")
        return jsonify({'success': False, 'message': 'Missing fee amount in request.'}), 400
        
    fee_input = data['fee']
    current_app.logger.info(f"Fee value received: {fee_input} (Type: {type(fee_input)})")

    try:
        fee_value = float(fee_input)
        current_app.logger.info(f"Fee value successfully converted to float: {fee_value}")
        if fee_value < 0:
             current_app.logger.info("Fee value is negative.")
             return jsonify({'success': False, 'message': 'Fee cannot be negative.'}), 400
             
        treatment.fee_charged = fee_value
        db.session.commit()
        current_app.logger.info(f"Fee successfully updated in DB for treatment {id}")
        return jsonify({'success': True, 'message': 'Fee updated successfully.', 'new_fee': fee_value})
    except ValueError:
         current_app.logger.info(f"ValueError converting fee '{fee_input}' to float.")
         return jsonify({'success': False, 'message': 'Invalid fee amount provided.'}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.info(f"!!! UNEXPECTED Error setting fee for treatment {id}: {e} !!!")
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

# --- API Endpoint to Set Location (and potentially auto-set fee) ---
@api.route('/api/treatment/<int:id>/set-location', methods=['POST'])
@login_required
def set_treatment_location(id):
    """Sets the location for a specific treatment. 
       If location is 'CostaSpine Clinic', automatically sets the fee based on patient history.
    """
    current_app.logger.info(f"--- set_treatment_location START for ID: {id} ---")
    treatment = Treatment.query.options(db.joinedload(Treatment.patient)).get_or_404(id)
    patient_id = treatment.patient_id
    data = None
    auto_set_fee = None # To return the fee if auto-set

    try:
        data = request.get_json()
        current_app.logger.info(f"Parsed JSON data: {data}")
        location_value = data.get('location')

        if not location_value or location_value not in ['CostaSpine Clinic', 'Home Visit']:
            current_app.logger.info("Invalid or missing location value.")
            return jsonify({'success': False, 'message': 'Invalid or missing location.'}), 400

        # Set the location
        treatment.location = location_value
        current_app.logger.info(f"Location set to: {location_value}")

        # --- Auto-Fee Logic for CostaSpine Clinic ---
        if location_value == 'CostaSpine Clinic':
            # Find the earliest treatment for this specific patient
            earliest_patient_treatment = Treatment.query.filter_by(patient_id=patient_id).order_by(Treatment.created_at.asc(), Treatment.id.asc()).first()
            earliest_treatment_id = earliest_patient_treatment.id if earliest_patient_treatment else None

            # Set fee based on whether it's the patient's absolute earliest treatment
            if earliest_treatment_id is not None and treatment.id == earliest_treatment_id:
                treatment.fee_charged = 80.00
                auto_set_fee = 80.00
                current_app.logger.info(f"Auto-setting fee to 80 for treatment {treatment.id} (earliest)")
            else:
                treatment.fee_charged = 70.00
                auto_set_fee = 70.00
                current_app.logger.info(f"Auto-setting fee to 70 for treatment {treatment.id}")
        # --- End Auto-Fee Logic ---

        db.session.commit()
        current_app.logger.info(f"Location and potentially fee updated in DB for treatment {id}")
        
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
        current_app.logger.info(f"!!! UNEXPECTED Error setting location for treatment {id}: {e} !!!")
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
        query = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.count(Treatment.id).label('count')
        )
        
        if not current_user.is_admin:
            query = query.join(Patient, Patient.id == Treatment.patient_id).filter(Patient.user_id == current_user.id)
            
        data = query.group_by(func.strftime('%Y-%m', Treatment.created_at)).order_by(func.strftime('%Y-%m', Treatment.created_at)).all() # Ensure group_by and order_by are on the correct column expression
        
        result = [{'month': item.month, 'count': item.count} for item in data]
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching treatments-by-month for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/patients-by-month')
@login_required
def patients_by_month():
    twelve_months_ago = datetime.utcnow() - timedelta(days=365)
    
    query = db.session.query(
        func.strftime('%Y-%m', Patient.created_at).label('month'), # Corrected to Patient.created_at
        func.count(Patient.id).label('count')
    ).filter(Patient.created_at >= twelve_months_ago) # Corrected to Patient.created_at

    # If the user is not an admin, filter by their user_id
    if not current_user.is_admin:
        query = query.filter(Patient.user_id == current_user.id)
    
    result = query.group_by(func.strftime('%Y-%m', Patient.created_at)).order_by(func.strftime('%Y-%m', Patient.created_at).asc()).all() # Corrected to Patient.created_at
    
    # Convert the result to the desired format
    data = [{'month': r.month, 'count': r.count} for r in result]
    
    return jsonify(data)

@api.route('/api/analytics/revenue-by-visit-type')
@login_required
def revenue_by_visit_type():
    try:
        query = db.session.query(
            Treatment.visit_type.label('treatment_type'),
            func.sum(Treatment.fee_charged).label('total_fee')
        ).filter(Treatment.fee_charged.isnot(None))

        if not current_user.is_admin:
            query = query.join(Patient, Patient.id == Treatment.patient_id).filter(Patient.user_id == current_user.id)

        data = query.group_by(Treatment.visit_type)\
            .order_by(func.sum(Treatment.fee_charged).desc())\
            .all()
        
        result = [{'treatment_type': item.treatment_type or 'Uncategorized', 'total_fee': float(item.total_fee or 0)} for item in data]
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching revenue-by-visit-type for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/revenue-by-location')
@login_required
def revenue_by_location():
    try:
        query = db.session.query(
            Treatment.location.label('location'),
            func.sum(Treatment.fee_charged).label('total_fee')
        ).filter(Treatment.fee_charged.isnot(None))

        if not current_user.is_admin:
            query = query.join(Patient, Patient.id == Treatment.patient_id).filter(Patient.user_id == current_user.id)

        data = query.group_by(Treatment.location)\
            .order_by(func.sum(Treatment.fee_charged).desc())\
            .limit(10)\
            .all()
        
        result = [{'location': item.location or 'Unknown', 'total_fee': float(item.total_fee or 0)} for item in data]
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching revenue-by-location for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/common-diagnoses')
@login_required
def common_diagnoses():
    try:
        query = db.session.query(
            Patient.diagnosis.label('diagnosis'),
            func.count(Patient.id).label('count')
        ).filter(Patient.diagnosis.isnot(None), Patient.diagnosis != '')

        if not current_user.is_admin:
            query = query.filter(Patient.user_id == current_user.id)

        data = query.group_by(Patient.diagnosis)\
            .order_by(func.count(Patient.id).desc())\
            .limit(7)\
            .all()
        
        result = [{'diagnosis': item.diagnosis, 'count': item.count} for item in data]
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching common-diagnoses for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/patient-status')
@login_required
def patient_status_distribution():
    try:
        active_query = Patient.query.filter_by(status='Active')
        inactive_query = Patient.query.filter_by(status='Inactive')

        if not current_user.is_admin:
            active_query = active_query.filter_by(user_id=current_user.id)
            inactive_query = inactive_query.filter_by(user_id=current_user.id)
        
        active_count = active_query.count()
        inactive_count = inactive_query.count()
        # Add other statuses if needed, applying the same filtering logic
        
        return jsonify({'active': active_count, 'inactive': inactive_count})
    except Exception as e:
        current_app.logger.error(f"Error fetching patient-status for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/payment-methods')
@login_required
def payment_method_distribution():
    try:
        query = db.session.query(
            Treatment.payment_method.label('payment_method'),
            func.count(Treatment.id).label('count')
        ).filter(Treatment.payment_method.isnot(None), Treatment.payment_method != '')

        if not current_user.is_admin:
            query = query.join(Patient, Patient.id == Treatment.patient_id).filter(Patient.user_id == current_user.id)

        data = query.group_by(Treatment.payment_method)\
            .order_by(func.count(Treatment.id).desc())\
            .all()
         
        result = [{'payment_method': item.payment_method, 'count': item.count} for item in data]
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching payment-methods for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/costaspine-fee-data')
@login_required
def get_costaspine_fee_data():
    """Returns the total fee charged per month for CostaSpine Clinic treatments."""
    try:
        query = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.sum(Treatment.fee_charged).label('total_fee')
        ).filter(
            Treatment.location == 'CostaSpine Clinic',
            Treatment.fee_charged.isnot(None)
        )

        if not current_user.is_admin:
            query = query.join(Patient, Patient.id == Treatment.patient_id).filter(Patient.user_id == current_user.id)

        monthly_fee_data = query.group_by(func.strftime('%Y-%m', Treatment.created_at))\
            .order_by(func.strftime('%Y-%m', Treatment.created_at)).all()
        
        results = [
            {'month': record.month, 'total_fee': float(record.total_fee)}
            for record in monthly_fee_data
        ]
        
        return jsonify(results)
    except Exception as e:
        current_app.logger.error(f"Error fetching CostaSpine monthly fee data for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/recently-inactive-patients')
@login_required
def recently_inactive_patients():
    """Returns a list of patients who became inactive in the last 7 days and their count."""
    try:
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        
        inactive_patients_query = Patient.query.filter(
            Patient.status == 'Inactive',
            Patient.updated_at >= one_week_ago 
        )

        if not current_user.is_admin:
            inactive_patients_query = inactive_patients_query.filter(Patient.user_id == current_user.id)
        
        # This is a placeholder if you don't have a specific 'became_inactive_at' field.
        # A more robust solution might involve an audit log for status changes.

        inactive_patients_list = inactive_patients_query.order_by(Patient.updated_at.desc()).all()
        count = inactive_patients_query.count() # Re-evaluate count on the potentially filtered query

        patients_data = [{
            'id': p.id,
            'name': p.name,
            'last_updated': p.updated_at.strftime('%Y-%m-%d') if p.updated_at else 'N/A' 
        } for p in inactive_patients_list]

        return jsonify({'count': count, 'patients': patients_data})

    except Exception as e:
        current_app.logger.error(f"Error fetching recently_inactive_patients for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/api/analytics/top-patients-by-revenue')
@login_required
def top_patients_by_revenue():
    """Returns the top N patients ranked by total revenue generated."""
    try:
        top_n = 10 # Define how many top patients to show

        query = db.session.query(
            Patient.name.label('patient_name'),
            func.sum(Treatment.fee_charged).label('total_revenue')
        ).join(Treatment, Patient.id == Treatment.patient_id)\
         .filter(Treatment.fee_charged.isnot(None), Treatment.fee_charged > 0)

        if not current_user.is_admin:
            query = query.filter(Patient.user_id == current_user.id)

        patient_revenue = query.group_by(Patient.id, Patient.name)\
            .order_by(func.sum(Treatment.fee_charged).desc())\
            .limit(top_n)\
            .all()

        result = [
            {'patient_name': item.patient_name, 'total_revenue': float(item.total_revenue)}
            for item in patient_revenue
        ]

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Error fetching top patients by revenue for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

# Route to create a Stripe Checkout Session
@api.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    try:
        data = request.get_json()
        plan_id = data.get('plan_id')
        billing_cycle = data.get('billing_cycle') # e.g., 'monthly', 'annual'

        if not plan_id or not billing_cycle:
            return jsonify({'error': 'Missing plan_id or billing_cycle'}), 400

        # Find the plan. 
        # This logic assumes plan_id from frontend + billing_cycle helps identify the specific Stripe Price ID.
        # Your Plan model has 'slug' like 'pro-monthly', 'basic-monthly'.
        # And Plan.stripe_price_id is the one to use.
        # We need to ensure we get the correct Plan object that corresponds to the selected cycle.
        
        # First, get the base plan by ID to get its general slug structure
        base_plan_for_slug = Plan.query.get(plan_id)
        if not base_plan_for_slug:
            return jsonify({'error': f'Plan with ID {plan_id} not found to determine slug structure.'}), 404

        # Construct the expected slug based on the base plan's slug (e.g., 'pro') and the cycle
        # This is a bit heuristic; ideally, the frontend sends a plan_slug or a more direct identifier if plan_id isn't unique enough per cycle.
        # Example: if base_plan_for_slug.slug is 'pro', and billing_cycle is 'monthly', target_slug is 'pro-monthly'
        # For now, let's assume the plan_id from pricing.html *is* specific enough for the chosen plan AND cycle.
        # So, we look up the plan by the given plan_id, and then use its stripe_price_id.
        # The `billing_cycle` from the client helps confirm intent but might not be strictly needed if plan_id is already cycle-specific.

        plan = Plan.query.get(plan_id) # Get the specific plan (e.g. "Pro Monthly" if plan_id was for that)

        if not plan:
            return jsonify({'error': f'Plan with id {plan_id} not found.'}), 404
        
        if not plan.stripe_price_id:
            return jsonify({'error': f'Plan \'{plan.name}\' does not have a Stripe Price ID configured.'}), 400

        stripe_price_id = plan.stripe_price_id

        # Define success and cancel URLs
        success_url = url_for('main.subscription_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}'
        cancel_url = url_for('main.index', _external=True) # Or a specific cancellation page/pricing page

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price': stripe_price_id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(current_user.id),  # Crucial for webhook to identify user
            # To prefill email, if you have a Stripe customer object you can pass it, 
            # or pass customer_email. If not, Stripe collects it.
            # customer_email=current_user.email, # Example
        )
        return jsonify({'sessionId': checkout_session.id})

    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe API error in create_checkout_session: {str(e)}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Error in create_checkout_session: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred.'}), 500

@api.route('/stripe-webhooks', methods=['POST'])
def stripe_webhooks():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')

    if not endpoint_secret:
        current_app.logger.error("Stripe webhook secret not configured.")
        return jsonify(error="Webhook secret not configured"), 500

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        current_app.logger.error(f"Stripe webhook ValueError: {e}")
        return jsonify(error=str(e)), 400
    except stripe.error.SignatureVerificationError as e:
        current_app.logger.error(f"Stripe webhook SignatureVerificationError: {e}")
        return jsonify(error=str(e)), 400
    except Exception as e:
        current_app.logger.error(f"Stripe webhook generic error constructing event: {e}")
        return jsonify(error=str(e)), 500

    # Handle the event
    current_app.logger.info(f'Received Stripe event: {event.type} (ID: {event.id})')

    if event.type == 'customer.subscription.created':
        subscription = event.data.object
        current_app.logger.info(f"Webhook processing: customer.subscription.created for Stripe sub ID {subscription.id}")
        user = User.query.filter_by(stripe_customer_id=subscription.customer).first()
        if user:
            plan = Plan.query.filter_by(stripe_price_id=subscription.items.data[0].price.id).first()
            if plan:
                existing_sub = UserSubscription.query.filter_by(stripe_subscription_id=subscription.id).first()
                if existing_sub:
                    current_app.logger.info(f"Subscription {subscription.id} already exists locally with ID {existing_sub.id}. Updating it.")
                    # Potentially update status or dates if it was created manually before webhook
                    existing_sub.status = subscription.status
                    existing_sub.plan_id = plan.id # Ensure plan is correct
                else:
                    current_app.logger.info(f"Creating new local subscription for Stripe sub ID {subscription.id} for user {user.id}")
                    existing_sub = UserSubscription(user_id=user.id, plan_id=plan.id, stripe_subscription_id=subscription.id)
                
                existing_sub.status = subscription.status
                if subscription.current_period_start: # Check if not None
                    existing_sub.current_period_starts_at = datetime.fromtimestamp(subscription.current_period_start)
                if subscription.current_period_end: # Check if not None
                    existing_sub.current_period_ends_at = datetime.fromtimestamp(subscription.current_period_end)
                if hasattr(subscription, 'trial_start') and subscription.trial_start: # Check if attribute exists and not None
                    existing_sub.trial_starts_at = datetime.fromtimestamp(subscription.trial_start)
                if hasattr(subscription, 'trial_end') and subscription.trial_end:
                    existing_sub.trial_ends_at = datetime.fromtimestamp(subscription.trial_end)
                existing_sub.cancel_at_period_end = subscription.cancel_at_period_end
                existing_sub.canceled_at = datetime.fromtimestamp(subscription.canceled_at) if subscription.canceled_at else None
                existing_sub.ended_at = datetime.fromtimestamp(subscription.ended_at) if subscription.ended_at else None
                db.session.add(existing_sub)
                try:
                    db.session.commit()
                    current_app.logger.info(f"Successfully created/updated local subscription {existing_sub.id} for Stripe sub {subscription.id}")
                except Exception as e_commit:
                    db.session.rollback()
                    current_app.logger.error(f"Error committing subscription {subscription.id} for user {user.id}: {e_commit}")
            else:
                current_app.logger.error(f"No plan found with Stripe Price ID: {subscription.items.data[0].price.id} for subscription {subscription.id}")
        else:
            current_app.logger.error(f"No user found with Stripe Customer ID: {subscription.customer} for subscription {subscription.id}")

    elif event.type == 'customer.subscription.updated':
        subscription = event.data.object
        current_app.logger.info(f"Webhook processing: customer.subscription.updated for Stripe sub ID {subscription.id}")
        existing_sub = UserSubscription.query.filter_by(stripe_subscription_id=subscription.id).first()
        if existing_sub:
            new_stripe_price_id = subscription.items.data[0].price.id
            if existing_sub.plan.stripe_price_id != new_stripe_price_id:
                new_plan = Plan.query.filter_by(stripe_price_id=new_stripe_price_id).first()
                if new_plan:
                    current_app.logger.info(f"Plan changed for sub {subscription.id} from {existing_sub.plan.name} to {new_plan.name}")
                    existing_sub.plan_id = new_plan.id
                else:
                    current_app.logger.error(f"Could not find new plan with Stripe Price ID {new_stripe_price_id} for sub {subscription.id}")
            
            existing_sub.status = subscription.status
            if subscription.current_period_start:
                existing_sub.current_period_starts_at = datetime.fromtimestamp(subscription.current_period_start)
            if subscription.current_period_end:
                existing_sub.current_period_ends_at = datetime.fromtimestamp(subscription.current_period_end)
            existing_sub.cancel_at_period_end = subscription.cancel_at_period_end
            existing_sub.canceled_at = datetime.fromtimestamp(subscription.canceled_at) if subscription.canceled_at else None
            existing_sub.ended_at = datetime.fromtimestamp(subscription.ended_at) if subscription.ended_at else None
            try:
                db.session.commit()
                current_app.logger.info(f"Successfully updated local subscription {existing_sub.id} for Stripe sub {subscription.id}")
            except Exception as e_commit:
                db.session.rollback()
                current_app.logger.error(f"Error committing update for subscription {subscription.id}: {e_commit}")
        else:
            current_app.logger.warning(f"Received update for unknown Stripe subscription ID: {subscription.id}. Might need to handle as a new subscription if created directly in Stripe.")
            # Optionally, call the creation logic here if it should be treated as new

    elif event.type == 'customer.subscription.deleted':
        subscription = event.data.object
        current_app.logger.info(f"Webhook processing: customer.subscription.deleted for Stripe sub ID {subscription.id}")
        existing_sub = UserSubscription.query.filter_by(stripe_subscription_id=subscription.id).first()
        if existing_sub:
            existing_sub.status = 'canceled' # Or 'ended' based on your preference
            existing_sub.ended_at = datetime.fromtimestamp(subscription.ended_at) if subscription.ended_at else datetime.utcnow()
            existing_sub.cancel_at_period_end = True # Typically true for deleted subs
            try:
                db.session.commit()
                current_app.logger.info(f"Successfully marked local subscription {existing_sub.id} as deleted for Stripe sub {subscription.id}")
            except Exception as e_commit:
                db.session.rollback()
                current_app.logger.error(f"Error committing deletion for subscription {subscription.id}: {e_commit}")
        else:
            current_app.logger.warning(f"Received delete for unknown Stripe subscription ID: {subscription.id}")

    elif event.type == 'invoice.paid':
        invoice = event.data.object
        stripe_sub_id = invoice.subscription # Get Stripe Subscription ID from the invoice
        if stripe_sub_id:
            current_app.logger.info(f"Webhook processing: invoice.paid for Stripe invoice {invoice.id}, subscription {stripe_sub_id}")
            existing_sub = UserSubscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
            if existing_sub:
                # A paid invoice usually means the subscription is active (or continues to be)
                existing_sub.status = 'active' 
                if invoice.period_start: # Use invoice period if available
                    existing_sub.current_period_starts_at = datetime.fromtimestamp(invoice.period_start)
                if invoice.period_end:
                    existing_sub.current_period_ends_at = datetime.fromtimestamp(invoice.period_end)
                existing_sub.cancel_at_period_end = False # A payment usually means it's not ending at period end anymore
                # If it was a trial and this is the first payment, update trial_ends_at if necessary or clear it
                # (Stripe object for subscription might be more accurate for trial_ends_at)
                try:
                    db.session.commit()
                    current_app.logger.info(f"Updated local subscription {existing_sub.id} to active due to paid invoice for Stripe sub {stripe_sub_id}")
                except Exception as e_commit:
                    db.session.rollback()
                    current_app.logger.error(f"Error committing update for subscription {stripe_sub_id} from invoice: {e_commit}")
            else:
                current_app.logger.warning(f"Received invoice.paid for unknown Stripe subscription ID: {stripe_sub_id}")
        else:
            current_app.logger.info(f"Webhook: invoice.paid for invoice {invoice.id} not linked to a subscription (e.g., one-time payment). No action on UserSubscription.")

    else:
        current_app.logger.info(f'Stripe webhook: Unhandled event type {event.type}')

    return jsonify(received=True), 200