from flask import Blueprint, jsonify, current_app, request
import requests
from datetime import datetime, timedelta, date
from app.models import Treatment, Treatment as Appointment, Patient, UnmatchedCalendlyBooking, PatientReport, Plan, User, UserSubscription
from app import db, csrf
from sqlalchemy.sql import func, or_, case
import os
import json
from flask_login import login_required, current_user
import traceback
import stripe
from flask import url_for
from generate_patient_report import format_treatment_history
from app.crypto_utils import decrypt_text

api = Blueprint('api', __name__)

@api.route('/sync-calendly-events', methods=['GET'])
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
                    # First check if a treatment with this Calendly invitee UUID already exists
                    existing_treatment = Treatment.query.filter_by(
                        calendly_invitee_uri=invitee_uuid_for_booking
                    ).first()
                    
                    if existing_treatment:
                        # If it exists but for a different patient, update the patient_id
                        if existing_treatment.patient_id != patient.id:
                            existing_treatment.patient_id = patient.id
                            existing_treatment.notes += f"\nUpdated patient assignment on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
                        current_app.logger.info(f"Treatment already exists with invitee UUID {invitee_uuid_for_booking}. Updated patient if needed.")
                        if existing_unmatched_booking and existing_unmatched_booking.status == 'Pending':
                            existing_unmatched_booking.status = 'Matched'
                            existing_unmatched_booking.matched_patient_id = patient.id
                    else:
                        # Only create a new treatment if one doesn't exist with this invitee UUID
                        new_treatment = Treatment(
                            patient_id=patient.id,
                            created_at=start_time,
                            treatment_type=event_type_name,
                            status="Scheduled",
                            notes=f"Booked via Calendly. Synced by {current_user.email}. Duration: {int((end_time - start_time).total_seconds() / 60)} min.",
                            calendly_invitee_uri=invitee_uuid_for_booking  # Store just the UUID
                        )
                        db.session.add(new_treatment)
                        synced_treatments_count += 1
                        created_new_treatment = True
                        current_app.logger.info(f"Created new Treatment for existing patient {patient.id} by user {current_user.id} from Calendly event {event_uuid}, invitee {invitee_uuid_for_booking}")
                        if existing_unmatched_booking: # If it was pending and now we created a treatment
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
    """Try to find a matching patient using name and email, scoped to the current user."""
    # First try exact email match for the current user
    patient = Patient.query.filter_by(contact=email, user_id=current_user.id).first()
    if patient:
        return patient
    
    # Try name matching (first name only) for the current user
    first_name = name.split()[0].lower()
    potential_matches = Patient.query.filter(
        Patient.user_id == current_user.id,
        func.lower(Patient._name).like(f"{first_name}%")
    ).all()
    
    if len(potential_matches) == 1:
        # If only one match, return it
        return potential_matches[0]
    
    # No confident match found
    return None

@api.route('/patients/search')
@login_required
def search_patients():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    patients = Patient.query.filter(
        Patient.user_id == current_user.id,
        or_(
            Patient._name.ilike(f'%{query}%'),
            Patient.contact.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'contact': p.contact,
        'diagnosis': p.diagnosis,
        'status': p.status
    } for p in patients])

@api.route('/calendly/match-booking', methods=['POST'])
@login_required
def match_calendly_booking():
    try:
        data = request.json
        booking_id = data.get('booking_id')
        patient_id = data.get('patient_id')
        
        if not booking_id or not patient_id:
            return jsonify({'success': False, 'error': 'Missing booking_id or patient_id'}), 400
        
        booking = UnmatchedCalendlyBooking.query.filter_by(id=booking_id, user_id=current_user.id).first_or_404('Booking not found or not authorized')
        patient = Patient.query.filter_by(id=patient_id, user_id=current_user.id).first_or_404('Patient not found or not authorized')
        
        booking.status = 'Matched'
        booking.matched_patient_id = patient_id
        
        # First check if a treatment with this Calendly invitee UUID already exists
        existing_treatment = Treatment.query.filter_by(
            calendly_invitee_uri=booking.calendly_invitee_id  # Using the UUID stored in UnmatchedCalendlyBooking
        ).first()
        
        if existing_treatment:
            # If it exists but for a different patient, update the patient_id
            if existing_treatment.patient_id != patient.id:
                existing_treatment.patient_id = patient.id
                existing_treatment.notes += f"\nUpdated patient assignment on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            # Only create a new treatment if one doesn't exist with this invitee UUID
            treatment = Treatment(
                patient_id=patient.id,
                created_at=booking.start_time,
                treatment_type=booking.event_type,
                status="Scheduled",
                notes=f"Linked to Calendly booking. Matched by admin user.",
                calendly_invitee_uri=booking.calendly_invitee_id  # Using the UUID stored in UnmatchedCalendlyBooking
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
        current_app.logger.error(f"Error in match_calendly_booking: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api.route('/calendly/create-patient-from-booking', methods=['POST'])
@login_required
def create_patient_from_booking():
    data = request.json
    booking_id = data.get('booking_id')
    
    if not booking_id:
        return jsonify({'success': False, 'error': 'Missing booking_id'}), 400
    
    try:
        booking = UnmatchedCalendlyBooking.query.filter_by(id=booking_id, user_id=current_user.id).first_or_404()
        
        existing_patient = Patient.query.filter_by(
            contact=booking.email,
            user_id=current_user.id
        ).first()
        
        if existing_patient:
            patient_id = existing_patient.id
        else:
            patient = Patient(
                name=booking.name,
                contact=booking.email,
                date_of_birth=None,
                diagnosis="Created from Calendly booking",
                treatment_plan="To be determined",
                notes=f"Patient created from Calendly booking on {datetime.now().strftime('%Y-%m-%d')}",
                status="Active",
                user_id=current_user.id
            )
            db.session.add(patient)
            db.session.flush()
            patient_id = patient.id
        
        booking.status = 'Matched'
        booking.matched_patient_id = patient_id
        
        db.session.commit()
        
        return jsonify({'success': True, 'patient_id': patient_id})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating patient from booking: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api.route('/appointment/<int:id>/status', methods=['POST'])
@login_required
def update_appointment_status(id):
    try:
        data = request.json
        status = data.get('status')
        
        if not status:
            return jsonify({'success': False, 'error': 'Status not provided'}), 400
        
        appointment = Treatment.query.filter_by(id=id, practitioner_id=current_user.id).first_or_404()
        appointment.status = status
        
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
        current_app.logger.error(f"Error updating appointment status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api.route('/patient/<int:id>/generate-report', methods=['POST'])
@login_required
def generate_patient_report(id):
    try:
        patient = Patient.query.filter_by(id=id, user_id=current_user.id).first_or_404()
        treatments_query = Treatment.query.filter_by(patient_id=id).order_by(Treatment.created_at).all()
        if not treatments_query:
            return jsonify({'success': False, 'message': 'No treatments found for this patient.'}), 400

        # Get the requested language from the request body
        data = request.get_json() or {}
        requested_language = data.get('language', 'en')  # Default to English if not specified
        
        # Validate language
        supported_languages = ['en', 'es', 'fr', 'it']
        if requested_language not in supported_languages:
            return jsonify({'success': False, 'message': f'Unsupported language. Supported languages: {", ".join(supported_languages)}'}), 400

        # Language mappings for AI instructions
        language_names = {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French', 
            'it': 'Italian'
        }
        
        # Convert Patient object to dict for format_treatment_history
        patient_dict = {
            'id': patient.id,
            'name': patient.name,
            'diagnosis': patient.diagnosis,
            'treatment_plan': getattr(patient, 'treatment_plan', None)
        }

        # Convert Treatment objects to dicts for format_treatment_history
        treatments = []
        for t in treatments_query:
            trigger_points = []
            if hasattr(t, 'trigger_points') and t.trigger_points:
                for tp in t.trigger_points:
                    trigger_points.append({
                        'muscle': getattr(tp, 'muscle', None),
                        'intensity': getattr(tp, 'intensity', None),
                        'type': getattr(tp, 'type', None),
                        'symptoms': getattr(tp, 'symptoms', None)
                    })
            treatment_dict = {
                'id': t.id,
                'created_at': t.created_at,
                'treatment_type': t.treatment_type,
                'notes': t.notes,
                'pain_level': t.pain_level,
                'movement_restriction': getattr(t, 'movement_restriction', None),
                'status': t.status,
                'trigger_points': trigger_points
            }
            treatments.append(treatment_dict)

        # Build user info dict with optional fields
        user_info = {
            'first_name': current_user.first_name,
            'last_name': current_user.last_name,
            'license_number': getattr(current_user, 'license_number', None),
            'college_acronym': getattr(current_user, 'college_acronym', None),
            'clinic_name': current_user.clinic_name
        }

        # Build the prompt for the AI
        base_prompt = format_treatment_history(patient_dict, treatments, user_info)
        
        # Add language instruction to the prompt
        language_instruction = f"\n\nIMPORTANT: Please generate this physiotherapy report entirely in {language_names[requested_language]}. Use professional physiotherapy terminology appropriate for {language_names[requested_language]}."
        
        prompt = base_prompt + language_instruction

        # Call DeepSeek
        import os, requests
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        if not api_key:
            return jsonify({
                'success': False, 
                'message': 'AI report generation requires a DeepSeek API key. Please contact your administrator to set up DEEPSEEK_API_KEY environment variable. For more info, visit: https://platform.deepseek.com/'
            }), 500

        # Modify system message to include language instruction
        system_message = f"You are a professional physiotherapist with expertise in creating detailed, evidence-based treatment progress reports. You use precise physiotherapy terminology while ensuring your reports remain clear and accessible. You must write all reports in {language_names[requested_language]} using professional medical terminology appropriate for that language."

        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 4000
            },
            timeout=90
        )
        if response.status_code != 200:
            return jsonify({'success': False, 'message': f"AI error: {response.text}"}), 500

        result = response.json()
        report_content = result['choices'][0]['message']['content']

        # Return the generated content for review instead of saving immediately
        return jsonify({
            'success': True,
            'message': 'Report generated successfully',
            'content': report_content,
            'language': requested_language
        })
    except Exception as e:
        current_app.logger.error(f"Exception in generate_patient_report: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api.route('/patient/<int:id>/save-report', methods=['POST'])
@login_required
def save_patient_report(id):
    try:
        patient = Patient.query.filter_by(id=id, user_id=current_user.id).first_or_404()
        
        # Get the edited content from the request
        data = request.get_json() or {}
        report_content = data.get('content', '')
        
        if not report_content:
            return jsonify({'success': False, 'message': 'Report content is required.'}), 400
        
        # Save the report as PatientReport
        report = PatientReport(
            patient_id=id,
            content=report_content,
            generated_date=datetime.now(),
            report_type='AI Generated'
        )
        db.session.add(report)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Report saved successfully',
            'report_id': report.id
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Exception in save_patient_report: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api.route('/report/<int:report_id>/update', methods=['PUT'])
@login_required
def update_report(report_id):
    try:
        report = PatientReport.query.get_or_404(report_id)
        patient = Patient.query.filter_by(id=report.patient_id, user_id=current_user.id).first_or_404()
        
        # Get the edited content from the request
        data = request.get_json() or {}
        new_content = data.get('content', '')
        
        if not new_content:
            return jsonify({'success': False, 'message': 'Report content is required.'}), 400
        
        # Update the report content
        report.content = new_content
        report.generated_date = datetime.now()  # Update the modification date
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Report updated successfully',
            'report_id': report.id
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Exception in update_report: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api.route('/patient/<int:id>/mark-past-as-completed', methods=['POST'])
@login_required
def mark_past_as_completed(id):
    try:
        today = datetime.now().date()
        
        updated_count = Treatment.query.filter(
            Treatment.patient_id == id,
            Treatment.practitioner_id == current_user.id,
            func.date(Treatment.created_at) < today,
            Treatment.status != 'Completed'
        ).update({'status': 'Completed'}, synchronize_session=False)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'count': updated_count,
            'message': f'{updated_count} past treatments marked as Completed.'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in mark_past_as_completed: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api.route('/patients/<int:patient_id>/status', methods=['POST'])
@login_required
def update_patient_status(patient_id):
    try:
        data = request.json
        status = data.get('status')
        
        if not status or status not in ['Active', 'Inactive', 'Completed', 'Pending Review']:
            return jsonify({'success': False, 'error': 'Invalid status'}), 400
        
        patient = Patient.query.filter_by(id=patient_id, user_id=current_user.id).first_or_404()
        patient.status = status
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Patient status updated to {status}'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating patient status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api.route('/patients/bulk-update-status', methods=['POST'])
@login_required
def bulk_update_patient_status():
    try:
        data = request.json
        patient_ids = data.get('patient_ids', [])
        status = data.get('status')
        
        if not status or status not in ['Active', 'Inactive', 'Completed', 'Pending Review']:
            return jsonify({'success': False, 'error': 'Invalid status'}), 400
        
        if not patient_ids:
            return jsonify({'success': False, 'error': 'No patients selected'}), 400
        
        updated_count = Patient.query.filter(
            Patient.user_id == current_user.id,
            Patient.id.in_(patient_ids)
        ).update({'status': status}, synchronize_session=False)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Updated {updated_count} patients to {status}'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in bulk update patient status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api.route('/treatments', methods=['POST'])
@login_required
def create_treatment():
    data = request.json
    patient_id = data.get('patient_id')
    
    # Ensure patient belongs to the current user
    patient = Patient.query.filter_by(id=patient_id, user_id=current_user.id).first_or_404()

    treatment = Treatment(
        patient_id=patient_id,
        created_at=datetime.now(),
        treatment_type=data.get('treatment_type'),
        pain_level=data.get('pain_level')
    )
    
    db.session.add(treatment)
    db.session.commit()
    
    return jsonify({'success': True, 'id': treatment.id})

@api.route('/report/<int:id>', methods=['DELETE'])
@login_required
def delete_report(id):
    try:
        report = PatientReport.query.get_or_404(id)
        patient = Patient.query.filter_by(id=report.patient_id, user_id=current_user.id).first_or_404()

        db.session.delete(report)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Report {id} successfully deleted'
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting report: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api.route('/patient/<int:id>/generate-exercise-prescription', methods=['POST'])
@login_required
def generate_exercise_prescription(id):
    try:
        patient = Patient.query.filter_by(id=id, user_id=current_user.id).first_or_404()
        treatments_query = Treatment.query.filter_by(patient_id=id).order_by(Treatment.created_at).all()
        if not treatments_query:
            return jsonify({'success': False, 'message': 'No treatments found for this patient.'}), 400

        # Get the requested language from the request body
        data = request.get_json() or {}
        requested_language = data.get('language', 'en')  # Default to English if not specified
        
        # Validate language
        supported_languages = ['en', 'es', 'fr', 'it']
        if requested_language not in supported_languages:
            return jsonify({'success': False, 'message': f'Unsupported language. Supported languages: {", ".join(supported_languages)}'}), 400

        # Language mappings for AI instructions
        language_names = {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French', 
            'it': 'Italian'
        }

        # Convert Patient object to dict
        patient_dict = {
            'id': patient.id,
            'name': patient.name,
            'diagnosis': patient.diagnosis,
            'treatment_plan': getattr(patient, 'treatment_plan', None)
        }

        # Convert Treatment objects to dicts
        treatments = []
        for t in treatments_query:
            trigger_points = []
            if hasattr(t, 'trigger_points') and t.trigger_points:
                for tp in t.trigger_points:
                    trigger_points.append({
                        'muscle': getattr(tp, 'muscle', None),
                        'intensity': getattr(tp, 'intensity', None),
                        'type': getattr(tp, 'type', None),
                        'symptoms': getattr(tp, 'symptoms', None)
                    })
            treatment_dict = {
                'id': t.id,
                'created_at': t.created_at,
                'treatment_type': t.treatment_type,
                'notes': t.notes,
                'pain_level': t.pain_level,
                'movement_restriction': getattr(t, 'movement_restriction', None),
                'status': t.status,
                'trigger_points': trigger_points
            }
            treatments.append(treatment_dict)

        # Build the prompt for exercise prescription with language instruction
        prompt = f"""
        You are a physiotherapist. Based on the following patient data and treatment history, generate a detailed home exercise program for the patient to continue their rehabilitation at home. 
        Focus on safety, progression, and clear instructions. Include 3-5 exercises, sets/reps, and any precautions. 
        Use patient-friendly language.

        IMPORTANT: Please generate this exercise prescription entirely in {language_names[requested_language]}. Use professional physiotherapy terminology appropriate for {language_names[requested_language]}.

        # Patient Data
        - Diagnosis: {patient_dict['diagnosis']}
        - Treatment Plan: {patient_dict['treatment_plan']}
        - Total Sessions: {len(treatments)}
        - Most recent session notes: {treatments[-1]['notes'] if treatments else 'N/A'}

        # Treatment History (summary)
        {', '.join([t['treatment_type'] for t in treatments if t['treatment_type']])}

        # Please format the program with headings, bullet points, and clear sections in markdown format.
        """

        # Call DeepSeek
        import os, requests
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        if not api_key:
            return jsonify({
                'success': False, 
                'message': 'AI exercise prescription requires a DeepSeek API key. Please contact your administrator to set up DEEPSEEK_API_KEY environment variable. For more info, visit: https://platform.deepseek.com/'
            }), 500

        # Modify system message to include language instruction
        system_message = f"You are a professional physiotherapist with expertise in creating home exercise programs. You must write all exercise prescriptions in {language_names[requested_language]} using professional physiotherapy terminology appropriate for that language. Use patient-friendly language while maintaining clinical accuracy."

        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 2000
            },
            timeout=90
        )
        if response.status_code != 200:
            return jsonify({'success': False, 'message': f"AI error: {response.text}"}), 500

        result = response.json()
        prescription_content = result['choices'][0]['message']['content']

        # Save as PatientReport type 'Exercise Homework'
        from app.models import PatientReport
        from datetime import datetime
        report = PatientReport(
            patient_id=id,
            content=prescription_content,
            generated_date=datetime.now(),
            report_type='Exercise Homework'
        )
        db.session.add(report)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Exercise prescription generated successfully',
            'report_id': report.id,
            'language': requested_language
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in generate_exercise_prescription: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api.route('/treatment/<int:id>/set-payment', methods=['POST'])
@login_required
def set_treatment_payment_method(id):
    try:
        data = request.get_json()
        payment_method = data.get('payment_method')
        treatment = Treatment.query.join(Patient).filter(
            Treatment.id == id,
            Patient.user_id == current_user.id
        ).first_or_404()
        treatment.payment_method = payment_method
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@api.route('/treatment/<int:id>/set-fee', methods=['POST'])
@login_required
def set_treatment_fee(id):
    try:
        data = request.get_json()
        fee_value = float(data['fee'])
        treatment = Treatment.query.join(Patient).filter(
            Treatment.id == id,
            Patient.user_id == current_user.id
        ).first_or_404()
        treatment.fee_charged = fee_value
        # Calculate clinic and therapist share
        clinic_percentage = current_user.clinic_percentage_amount or 0
        clinic_share = fee_value * (clinic_percentage / 100)
        therapist_share = fee_value - clinic_share
        treatment.clinic_share = clinic_share
        treatment.therapist_share = therapist_share
        db.session.commit()
        return jsonify({'success': True, 'new_fee': fee_value, 'clinic_share': clinic_share, 'therapist_share': therapist_share})
    except (ValueError, KeyError):
        return jsonify({'success': False, 'message': 'Invalid fee provided.'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

@api.route('/treatment/<int:id>/set-location', methods=['POST'])
@login_required
def set_treatment_location(id):
    try:
        data = request.get_json()
        location_value = data.get('location')
        treatment = Treatment.query.join(Patient).filter(
            Treatment.id == id,
            Patient.user_id == current_user.id
        ).first_or_404()
        treatment.location = location_value
        # Auto-fee logic can be added here
        db.session.commit()
        return jsonify({'success': True, 'location': location_value})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"!!! UNEXPECTED Error setting location for treatment {id}: {e} !!!")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

# --- Analytics API Endpoints ---

# Helper to get start of month
def start_of_month(dt):
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

@api.route('/analytics/treatments-by-month')
@login_required
def treatments_by_month():
    try:
        data_query = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.count(Treatment.id).label('count')
        ).join(Patient, Patient.id == Treatment.patient_id) \
         .filter(Patient.user_id == current_user.id) \
         .group_by(func.strftime('%Y-%m', Treatment.created_at)) \
         .order_by(func.strftime('%Y-%m', Treatment.created_at)) \
         .all()
        
        result = [{'month': item.month, 'count': item.count} for item in data_query]
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching treatments-by-month for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/analytics/patients-by-month')
@login_required
def patients_by_month():
    try:
        data = db.session.query(
            func.strftime('%Y-%m', Patient.created_at).label('month'),
            func.count(Patient.id).label('count')
        ).filter(Patient.user_id == current_user.id) \
         .group_by(func.strftime('%Y-%m', Patient.created_at)) \
         .order_by(func.strftime('%Y-%m', Patient.created_at)) \
         .all()
        result = [{'month': r.month, 'count': r.count} for r in data]
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching patients-by-month for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/analytics/revenue-by-visit-type')
@login_required
def revenue_by_visit_type():
    try:
        # First check if we have any treatments with fees for this user
        treatment_count = db.session.query(Treatment).join(Patient).filter(
            Patient.user_id == current_user.id,
            Treatment.fee_charged.isnot(None),
            Treatment.fee_charged > 0
        ).count()
        
        if treatment_count == 0:
            current_app.logger.info(f"No treatments with fees found for user {current_user.id}")
            return jsonify([])
        
        data = db.session.query(
            Treatment.treatment_type,
            func.sum(Treatment.fee_charged).label('total_fee')
        ).join(Patient, Patient.id == Treatment.patient_id) \
         .filter(
            Patient.user_id == current_user.id, 
            Treatment.fee_charged.isnot(None),
            Treatment.fee_charged > 0
         ) \
         .group_by(Treatment.treatment_type).all()
        
        result = []
        for item in data:
            treatment_type = item.treatment_type or 'Uncategorized'
            total_fee = float(item.total_fee or 0)
            if total_fee > 0:  # Only include types with actual revenue
                result.append({
                    'treatment_type': treatment_type, 
                    'total_fee': total_fee
                })
        
        current_app.logger.info(f"Successfully fetched {len(result)} revenue types for user {current_user.id}")
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching revenue-by-visit-type for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/analytics/revenue-by-location')
@login_required
def revenue_by_location():
    try:
        data = db.session.query(
            Treatment.location,
            func.sum(Treatment.fee_charged).label('total_fee')
        ).join(Patient, Patient.id == Treatment.patient_id) \
         .filter(Patient.user_id == current_user.id, Treatment.fee_charged.isnot(None)) \
         .group_by(Treatment.location).all()
        
        result = [{'location': item.location or 'Unknown', 'total_fee': float(item.total_fee or 0)} for item in data]
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching revenue-by-location for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/analytics/common-diagnoses')
@login_required
def common_diagnoses():
    try:
        data = db.session.query(
            Patient.diagnosis,
            func.count(Patient.id).label('count')
        ).filter(Patient.user_id == current_user.id, Patient.diagnosis.isnot(None)) \
         .group_by(Patient.diagnosis) \
         .order_by(func.count(Patient.id).desc()) \
         .limit(10).all()

        result = [{'diagnosis': item.diagnosis, 'count': item.count} for item in data]
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching common-diagnoses for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/analytics/patient-status')
@login_required
def patient_status_distribution():
    try:
        data = db.session.query(
            Patient.status,
            func.count(Patient.id).label('count')
        ).filter(Patient.user_id == current_user.id) \
         .group_by(Patient.status).all()
        
        result = [{'status': item.status, 'count': item.count} for item in data]
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching patient-status for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/analytics/payment-methods')
@login_required
def payment_method_distribution():
    try:
        data = db.session.query(
            Treatment.payment_method,
            func.count(Treatment.id).label('count')
        ).join(Patient, Patient.id == Treatment.patient_id) \
         .filter(Patient.user_id == current_user.id, Treatment.payment_method.isnot(None)) \
         .group_by(Treatment.payment_method).all()
         
        result = [{'payment_method': item.payment_method, 'count': item.count} for item in data]
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching payment-methods for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/analytics/costaspine-fee-data')
@login_required
def get_costaspine_fee_data():
    try:
        data = db.session.query(
            func.sum(Treatment.fee_charged).label('total_fee'),
            func.count(Treatment.id).label('total_sessions')
        ).join(Patient, Patient.id == Treatment.patient_id) \
         .filter(
            Patient.user_id == current_user.id,
            Treatment.fee_charged.isnot(None)
        ).one()
        return jsonify({'total_fee': float(data.total_fee or 0), 'total_sessions': data.total_sessions})
    except Exception as e:
        current_app.logger.error(f"Error fetching costaspine-fee-data for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/analytics/cancellations-by-month')
@login_required
def cancellations_by_month():
    """Get monthly cancellation statistics"""
    try:
        data_query = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.count(Treatment.id).label('count')
        ).join(Patient, Patient.id == Treatment.patient_id) \
         .filter(
            Patient.user_id == current_user.id,
            Treatment.status == 'Cancelled'
         ) \
         .group_by(func.strftime('%Y-%m', Treatment.created_at)) \
         .order_by(func.strftime('%Y-%m', Treatment.created_at)) \
         .all()
        
        result = [{'month': item.month, 'count': item.count} for item in data_query]
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching cancellations-by-month for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/analytics/cancellation-rates')
@login_required
def cancellation_rates():
    """Get cancellation rates by month"""
    try:
        # Get total appointments and cancellations by month
        monthly_stats = db.session.query(
            func.strftime('%Y-%m', Treatment.created_at).label('month'),
            func.count(Treatment.id).label('total'),
            func.sum(case(
                (Treatment.status == 'Cancelled', 1),
                else_=0
            )).label('cancelled')
        ).join(Patient, Patient.id == Treatment.patient_id) \
         .filter(Patient.user_id == current_user.id) \
         .group_by(func.strftime('%Y-%m', Treatment.created_at)) \
         .order_by(func.strftime('%Y-%m', Treatment.created_at)) \
         .all()
        
        result = []
        for item in monthly_stats:
            cancellation_rate = (item.cancelled / item.total * 100) if item.total > 0 else 0
            result.append({
                'month': item.month,
                'total': item.total,
                'cancelled': item.cancelled,
                'cancellation_rate': round(cancellation_rate, 2)
            })
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching cancellation-rates for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/patient/<int:patient_id>/cancellation-rate')
@login_required
def patient_cancellation_rate(patient_id):
    """Get cancellation rate for a specific patient"""
    try:
        # Verify patient belongs to current user
        patient = Patient.query.filter_by(id=patient_id, user_id=current_user.id).first_or_404()
        
        # Get total appointments and cancellations for this patient
        stats = db.session.query(
            func.count(Treatment.id).label('total'),
            func.sum(case(
                (Treatment.status == 'Cancelled', 1),
                else_=0
            )).label('cancelled')
        ).filter(Treatment.patient_id == patient_id).first()
        
        total = stats.total or 0
        cancelled = stats.cancelled or 0
        cancellation_rate = (cancelled / total * 100) if total > 0 else 0
        
        return jsonify({
            'patient_id': patient_id,
            'patient_name': patient.name,
            'total_appointments': total,
            'cancelled_appointments': cancelled,
            'cancellation_rate': round(cancellation_rate, 2)
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching cancellation rate for patient {patient_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/treatment/<int:treatment_id>/cancel', methods=['POST'])
@login_required
def cancel_treatment(treatment_id):
    """Cancel a specific treatment/appointment"""
    try:
        # Get the treatment and verify it belongs to current user's patient
        treatment = Treatment.query.join(Patient).filter(
            Treatment.id == treatment_id,
            Patient.user_id == current_user.id
        ).first_or_404()
        
        # Get cancellation reason from request
        data = request.get_json() or {}
        cancellation_reason = data.get('reason', 'No reason provided')
        
        # Update treatment status
        treatment.status = 'Cancelled'
        
        # Optionally store cancellation reason in notes
        current_notes = treatment.notes or ''
        if current_notes:
            treatment.notes = f"{current_notes}\n\n--- CANCELLED ---\nReason: {cancellation_reason}\nCancelled at: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        else:
            treatment.notes = f"--- CANCELLED ---\nReason: {cancellation_reason}\nCancelled at: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Treatment cancelled successfully',
            'treatment_id': treatment_id,
            'status': treatment.status
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error cancelling treatment {treatment_id}: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api.route('/recurring-appointment/cancel-occurrence', methods=['POST'])
@login_required
def cancel_recurring_occurrence():
    """Cancel a specific occurrence of a recurring appointment"""
    try:
        data = request.get_json() or {}
        
        # Get parameters from request
        recurring_rule_id = data.get('recurring_rule_id')
        appointment_date = data.get('date')
        appointment_time = data.get('time')
        cancellation_reason = data.get('reason', 'Recurring appointment cancelled')
        
        if not all([recurring_rule_id, appointment_date, appointment_time]):
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
        
        # Get the recurring rule and verify it belongs to current user
        from app.models import RecurringAppointment
        recurring_rule = RecurringAppointment.query.join(Patient).filter(
            RecurringAppointment.id == recurring_rule_id,
            Patient.user_id == current_user.id
        ).first_or_404()
        
        # Parse the date and time to create a datetime
        try:
            # Convert relative date to actual date
            today = datetime.utcnow().date()
            if appointment_date == 'Today':
                appt_date = today
            elif appointment_date == 'Tomorrow':
                appt_date = today + timedelta(days=1)
            elif appointment_date in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                # Find next occurrence of this weekday
                weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                target_weekday = weekdays.index(appointment_date)
                current_weekday = today.weekday()
                if target_weekday <= current_weekday:
                    days_ahead = target_weekday + 7 - current_weekday
                else:
                    days_ahead = target_weekday - current_weekday
                appt_date = today + timedelta(days=days_ahead)
            else:
                # Try to parse date format like "Jan 15"
                current_year = today.year
                try:
                    appt_date = datetime.strptime(f"{current_year} {appointment_date}", '%Y %b %d').date()
                    if appt_date < today:
                        appt_date = datetime.strptime(f"{current_year + 1} {appointment_date}", '%Y %b %d').date()
                except ValueError:
                    return jsonify({'success': False, 'error': 'Invalid date format'}), 400
            
            # Parse time
            appt_time = datetime.strptime(appointment_time, '%H:%M').time()
            appointment_datetime = datetime.combine(appt_date, appt_time)
            
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error parsing date/time: {str(e)}'}), 400
        
        # Check if a treatment already exists for this datetime
        existing_treatment = Treatment.query.filter(
            Treatment.patient_id == recurring_rule.patient_id,
            Treatment.created_at == appointment_datetime
        ).first()
        
        if existing_treatment:
            # If treatment exists, just cancel it
            existing_treatment.status = 'Cancelled'
            existing_treatment.notes = f"{existing_treatment.notes or ''}\n\n--- CANCELLED ---\nReason: {cancellation_reason}\nCancelled at: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            treatment_id = existing_treatment.id
        else:
            # Create a new cancelled treatment to "block" this slot
            new_treatment = Treatment(
                patient_id=recurring_rule.patient_id,
                treatment_type=recurring_rule.treatment_type,
                status='Cancelled',
                created_at=appointment_datetime,
                location=recurring_rule.location,
                fee_charged=recurring_rule.fee_charged,
                notes=f"--- CANCELLED ---\nReason: {cancellation_reason}\nCancelled at: {datetime.now().strftime('%Y-%m-%d %H:%M')}\nOriginally from recurring rule #{recurring_rule_id}"
            )
            db.session.add(new_treatment)
            db.session.flush()  # Get the ID
            treatment_id = new_treatment.id
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Recurring appointment occurrence cancelled successfully',
            'treatment_id': treatment_id,
            'appointment_datetime': appointment_datetime.isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error cancelling recurring occurrence: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api.route('/sync-appointments', methods=['POST'])
@login_required
def sync_appointments_manually():
    """Manually trigger appointment synchronization"""
    try:
        if current_user.role not in ['physio', 'admin']:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        user_id = None if current_user.is_admin else current_user.id
        
        from app.utils import auto_sync_appointments
        sync_result = auto_sync_appointments(user_id)
        
        return jsonify({
            'success': True,
            'message': 'Appointments synchronized successfully',
            'created_treatments': sync_result['created_treatments'],
            'completed_treatments': sync_result['completed_treatments']
        })
    except Exception as e:
        current_app.logger.error(f"Error in manual appointment sync for user {current_user.id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api.route('/analytics/recently-inactive-patients')
@login_required
def recently_inactive_patients():
    try:
        three_months_ago = datetime.utcnow() - timedelta(days=90)
        
        subquery = db.session.query(
            Treatment.patient_id,
            func.max(Treatment.created_at).label('last_visit_date')
        ).join(Patient, Patient.id == Treatment.patient_id) \
         .filter(Patient.user_id == current_user.id).group_by(Treatment.patient_id).subquery()

        patients = db.session.query(
            Patient,
            subquery.c.last_visit_date
        ).join(subquery, Patient.id == subquery.c.patient_id) \
         .filter(Patient.user_id == current_user.id, Patient.status == 'Active', subquery.c.last_visit_date < three_months_ago) \
         .order_by(subquery.c.last_visit_date.desc()).all()

        return jsonify([{'name': p.Patient.name, 'last_visit': p.last_visit_date.isoformat()} for p in patients])
    except Exception as e:
        current_app.logger.error(f"Error fetching recently-inactive-patients for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/analytics/top-patients-by-revenue')
@login_required
def top_patients_by_revenue():
    try:
        # First check if we have any treatments with fees for this user
        treatment_count = db.session.query(Treatment).join(Patient).filter(
            Patient.user_id == current_user.id,
            Treatment.fee_charged.isnot(None),
            Treatment.fee_charged > 0
        ).count()
        
        if treatment_count == 0:
            current_app.logger.info(f"No treatments with fees found for user {current_user.id}")
            return jsonify([])
        
        data = db.session.query(
            Patient._name,
            func.sum(Treatment.fee_charged).label('total_revenue')
        ).join(Treatment, Patient.id == Treatment.patient_id) \
         .filter(
            Patient.user_id == current_user.id, 
            Treatment.fee_charged.isnot(None),
            Treatment.fee_charged > 0
         ) \
         .group_by(Patient._name) \
         .order_by(func.sum(Treatment.fee_charged).desc()) \
         .limit(10).all()
        
        results = []
        for name, total_revenue in data:
            try:
                decrypted_name = decrypt_text(name) if name else 'Unknown Patient'
                results.append({
                    'name': decrypted_name, 
                    'revenue': float(total_revenue or 0)
                })
            except Exception as decrypt_error:
                current_app.logger.warning(f"Failed to decrypt patient name: {decrypt_error}")
                results.append({
                    'name': 'Patient (Name Error)', 
                    'revenue': float(total_revenue or 0)
                })
        
        current_app.logger.info(f"Successfully fetched {len(results)} top patients for user {current_user.id}")
        return jsonify(results)
    except Exception as e:
        current_app.logger.error(f"Error fetching top-patients-by-revenue for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/analytics/costaspine-service-fee')
@login_required
def costaspine_service_fee():
    try:
        
        # Calculate different time periods
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        start_of_month = today.replace(day=1)
        start_of_year = today.replace(month=1, day=1)
        
        # Convert to datetime objects for filtering
        start_of_week_dt = datetime.combine(start_of_week, datetime.min.time())
        end_of_week_dt = datetime.combine(end_of_week, datetime.max.time())
        start_of_month_dt = datetime.combine(start_of_month, datetime.min.time())
        start_of_year_dt = datetime.combine(start_of_year, datetime.min.time())
        
        # Base query for CostaSpine treatments
        base_query = db.session.query(func.sum(Treatment.fee_charged).label('total_fee')) \
                    .join(Patient, Patient.id == Treatment.patient_id) \
                    .filter(
                        Patient.user_id == current_user.id,
                        Treatment.location == 'CostaSpine Clinic',
                        Treatment.fee_charged.isnot(None)
                    )
        
        # All time
        all_time_total = base_query.scalar() or 0
        
        # This year
        this_year_total = base_query.filter(Treatment.created_at >= start_of_year_dt).scalar() or 0
        
        # This month  
        this_month_total = base_query.filter(Treatment.created_at >= start_of_month_dt).scalar() or 0
        
        # This week
        this_week_total = base_query.filter(
            Treatment.created_at >= start_of_week_dt,
            Treatment.created_at <= end_of_week_dt
        ).scalar() or 0
        
        # Calculate 30% fee for each period
        result = {
            'all_time': float(all_time_total * 0.30),
            'this_year': float(this_year_total * 0.30),
            'this_month': float(this_month_total * 0.30),
            'this_week': float(this_week_total * 0.30)
        }
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching costaspine-service-fee for user {current_user.id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Failed to fetch data"}), 500

@api.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Create Stripe checkout session for individual subscriptions."""
    # PAYMENT PROCESSING TEMPORARILY DISABLED
    return jsonify({
        'error': 'Payment processing is temporarily paused for system upgrades. Please contact support for assistance.'
    }), 503
    
    try:
        data = request.get_json()
        plan_id = data.get('plan_id')

        # Only allow individual plans for this endpoint
        plan = Plan.query.filter_by(id=plan_id, plan_type='individual').first_or_404()
        
        if not plan.stripe_price_id:
            return jsonify({'error': f'Individual plan \'{plan.name}\' does not have a Stripe Price ID configured.'}), 400

        # Ensure user is not in a clinic (individual plans are for solo practitioners)
        if current_user.is_in_clinic:
            return jsonify({'error': 'You are part of a clinic. Please use clinic plans instead.'}), 400

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': plan.stripe_price_id, 'quantity': 1}],
            mode='subscription',
            success_url=url_for('main.subscription_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('main.pricing_individual', _external=True),
            client_reference_id=str(current_user.id),
            customer_email=current_user.email,
            metadata={
                'plan_type': 'individual'
            }
        )
        return jsonify({'sessionId': checkout_session.id})

    except Exception as e:
        current_app.logger.error(f"Error in create_checkout_session: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred.'}), 500

@api.route('/get-plan-by-slug', methods=['POST'])
@login_required
def get_plan_by_slug():
    """Get plan ID by slug."""
    try:
        data = request.get_json()
        slug = data.get('slug')
        
        if not slug:
            return jsonify({'error': 'Plan slug is required'}), 400
        
        plan = Plan.query.filter_by(slug=slug, is_active=True).first()
        if not plan:
            return jsonify({'error': 'Plan not found'}), 404
        
        return jsonify({'plan_id': plan.id, 'name': plan.name})
    
    except Exception as e:
        current_app.logger.error(f"Error in get_plan_by_slug: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred.'}), 500

@api.route('/create-clinic-checkout-session', methods=['POST'])
@login_required
def create_clinic_checkout_session():
    """Create Stripe checkout session for clinic subscriptions."""
    # PAYMENT PROCESSING TEMPORARILY DISABLED
    return jsonify({
        'error': 'Payment processing is temporarily paused for system upgrades. Please contact support for assistance.'
    }), 503
    
    try:
        data = request.get_json()
        plan_id = data.get('plan_id')

        plan = Plan.query.filter_by(id=plan_id, plan_type='clinic').first_or_404()
        
        if not plan.stripe_price_id:
            return jsonify({'error': f'Clinic plan \'{plan.name}\' does not have a Stripe Price ID configured.'}), 400

        # Check if user is in a clinic and can manage it
        if not current_user.is_in_clinic:
            return jsonify({'error': 'You must be part of a clinic to subscribe to clinic plans.'}), 400
        
        if not current_user.is_clinic_admin:
            return jsonify({'error': 'Only clinic administrators can manage clinic subscriptions.'}), 400

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': plan.stripe_price_id, 'quantity': 1}],
            mode='subscription',
            success_url=url_for('main.subscription_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('main.pricing_clinic', _external=True),
            client_reference_id=f"clinic_{current_user.clinic.id}",
            customer_email=current_user.email,
            metadata={
                'clinic_id': current_user.clinic.id,
                'plan_type': 'clinic'
            }
        )
        return jsonify({'sessionId': checkout_session.id})

    except Exception as e:
        current_app.logger.error(f"Error in create_clinic_checkout_session: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred.'}), 500

@api.route('/stripe-webhooks', methods=['POST'])
def stripe_webhooks():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        current_app.logger.error(f"Stripe webhook error: {e}")
        return jsonify(error=str(e)), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session(session)
    elif event['type'] in ['customer.subscription.updated', 'customer.subscription.deleted']:
        subscription = event['data']['object']
        handle_subscription_change(subscription)
    
    return jsonify(received=True), 200

def handle_checkout_session(session):
    client_reference_id = session.get('client_reference_id')
    stripe_customer_id = session.get('customer')
    stripe_subscription_id = session.get('subscription')
    metadata = session.get('metadata', {})
    plan_type = metadata.get('plan_type', 'individual')  # Default to individual for backward compatibility

    # Parse client_reference_id to determine if it's individual or clinic
    if client_reference_id and client_reference_id.startswith('clinic_'):
        # Clinic subscription
        clinic_id = client_reference_id.replace('clinic_', '')
        handle_clinic_checkout_session(session, clinic_id, stripe_customer_id, stripe_subscription_id)
    else:
        # Individual subscription
        user_id = client_reference_id
        handle_individual_checkout_session(session, user_id, stripe_customer_id, stripe_subscription_id)

def handle_individual_checkout_session(session, user_id, stripe_customer_id, stripe_subscription_id):
    """Handle checkout session for individual subscriptions."""
    user = User.query.get(user_id)
    if not user:
        current_app.logger.error(f"Webhook Error: No user found with ID {user_id}")
        return

    user.stripe_customer_id = stripe_customer_id
    
    line_item = stripe.checkout.Session.list_line_items(session.id, limit=1).data[0]
    stripe_price_id = line_item.price.id
    plan = Plan.query.filter_by(stripe_price_id=stripe_price_id, plan_type='individual').first()

    if not plan:
        current_app.logger.error(f"Webhook Error: No individual plan found with stripe_price_id {stripe_price_id}")
        return

    # Deactivate old individual subscriptions
    UserSubscription.query.filter_by(user_id=user_id).update({"status": "canceled"})

    new_subscription = UserSubscription(
        user_id=user.id,
        plan_id=plan.id,
        stripe_subscription_id=stripe_subscription_id,
        status='active'
    )
    db.session.add(new_subscription)
    db.session.commit()
    current_app.logger.info(f"New individual subscription created for user {user.id}")

def handle_clinic_checkout_session(session, clinic_id, stripe_customer_id, stripe_subscription_id):
    """Handle checkout session for clinic subscriptions."""
    from app.models import Clinic, ClinicSubscription
    
    clinic = Clinic.query.get(clinic_id)
    if not clinic:
        current_app.logger.error(f"Webhook Error: No clinic found with ID {clinic_id}")
        return
    
    line_item = stripe.checkout.Session.list_line_items(session.id, limit=1).data[0]
    stripe_price_id = line_item.price.id
    plan = Plan.query.filter_by(stripe_price_id=stripe_price_id, plan_type='clinic').first()

    if not plan:
        current_app.logger.error(f"Webhook Error: No clinic plan found with stripe_price_id {stripe_price_id}")
        return

    # Deactivate old clinic subscriptions
    ClinicSubscription.query.filter_by(clinic_id=clinic_id).update({"status": "canceled"})

    new_subscription = ClinicSubscription(
        clinic_id=clinic.id,
        plan_id=plan.id,
        stripe_subscription_id=stripe_subscription_id,
        status='active'
    )
    db.session.add(new_subscription)
    db.session.commit()
    current_app.logger.info(f"New clinic subscription created for clinic {clinic.id}")

def handle_subscription_change(subscription_data):
    from app.models import ClinicSubscription
    
    stripe_subscription_id = subscription_data.id
    
    # Try to find individual subscription first
    individual_subscription = UserSubscription.query.filter_by(stripe_subscription_id=stripe_subscription_id).first()
    
    if individual_subscription:
        individual_subscription.status = subscription_data.status
        if subscription_data.get('ended_at'):
            individual_subscription.ended_at = datetime.fromtimestamp(subscription_data.get('ended_at'))
        db.session.commit()
        current_app.logger.info(f"Individual subscription {stripe_subscription_id} status updated to {individual_subscription.status}")
        return
    
    # Try to find clinic subscription
    clinic_subscription = ClinicSubscription.query.filter_by(stripe_subscription_id=stripe_subscription_id).first()
    
    if clinic_subscription:
        clinic_subscription.status = subscription_data.status
        if subscription_data.get('ended_at'):
            clinic_subscription.ended_at = datetime.fromtimestamp(subscription_data.get('ended_at'))
        db.session.commit()
        current_app.logger.info(f"Clinic subscription {stripe_subscription_id} status updated to {clinic_subscription.status}")
        return
    
    current_app.logger.warning(f"No subscription found for stripe_subscription_id {stripe_subscription_id}")

@api.route('/invoices')
@login_required
def list_invoices():
    customer_id = current_user.stripe_customer_id
    if not customer_id:
        return jsonify({'success': False, 'message': 'No Stripe customer ID found.'}), 400

    try:
        invoices = stripe.Invoice.list(customer=customer_id, limit=20)
        result = []
        for inv in invoices.auto_paging_iter():
            result.append({
                'number': inv.number,
                'amount_paid': inv.amount_paid,
                'currency': inv.currency,
                'created': inv.created,
                'invoice_pdf': inv.invoice_pdf
            })
        return jsonify({'success': True, 'invoices': result})
    except Exception as e:
        current_app.logger.error(f"Error fetching invoices for user {current_user.id}: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve invoices.'}), 500

@api.route('/patient/<int:patient_id>/generate-clinical-analysis', methods=['POST'])
@login_required
@csrf.exempt
def generate_patient_clinical_analysis(patient_id):
    """Generate AI clinical analysis for a specific patient and save to their profile"""
    try:
        # Log the start of the analysis
        current_app.logger.info(f"Starting clinical analysis for patient {patient_id} by user {current_user.id}")
        
        # Get the patient
        patient = Patient.query.filter_by(id=patient_id, user_id=current_user.id).first()
        if not patient:
            current_app.logger.warning(f"Patient {patient_id} not found for user {current_user.id}")
            return jsonify({'success': False, 'error': 'Patient not found'}), 404
        
        current_app.logger.info(f"Found patient: {patient.name}, diagnosis: {patient.diagnosis}")
        current_app.logger.info(f"Patient anamnesis length: {len(patient.anamnesis) if patient.anamnesis else 0}")
        
        # Get user's preferred language
        user_language = getattr(current_user, 'language', 'es')
        current_app.logger.info(f"Using user's preferred language: {user_language}")
        
        # Collect all patient data for analysis
        clinical_context = {
            'chief_complaint': '',  # From anamnesis
            'diagnosis': patient.diagnosis or '',
            'pain_level': '',
            'onset_date': '',
            'mechanism': '',
            'medical_history': {
                'conditions': [],
                'surgeries': [],
                'medications': '',
                'allergies': []
            },
            'functional_assessment': {
                'pain_characteristics': [],
                'functional_limitations': [],
                'rom_assessment': '',
                'strength_assessment': ''
            },
            'patient_demographics': {
                'age': calculate_age_from_dob(patient.date_of_birth.strftime('%Y-%m-%d') if patient.date_of_birth else ''),
                'gender': '',
                'occupation': '',
                'activity_level': ''
            }
        }
        
        # Parse anamnesis data if available
        if patient.anamnesis:
            try:
                import json
                # Try to parse as JSON first
                anamnesis_data = json.loads(patient.anamnesis)
                clinical_context.update({
                    'chief_complaint': anamnesis_data.get('anamnesis_chief_complaint', ''),
                    'pain_level': anamnesis_data.get('anamnesis_pain_scale', ''),
                    'onset_date': anamnesis_data.get('anamnesis_onset_date', ''),
                    'mechanism': anamnesis_data.get('anamnesis_mechanism', ''),
                })
                clinical_context['patient_demographics'].update({
                    'gender': anamnesis_data.get('anamnesis_gender', ''),
                    'occupation': anamnesis_data.get('anamnesis_occupation', ''),
                    'activity_level': anamnesis_data.get('anamnesis_physical_activity', '')
                })
                clinical_context['medical_history'].update({
                    'conditions': anamnesis_data.get('history_conditions', []),
                    'surgeries': anamnesis_data.get('surgery_description', []),
                    'medications': anamnesis_data.get('anamnesis_medications', ''),
                    'allergies': anamnesis_data.get('allergies', [])
                })
                clinical_context['functional_assessment'].update({
                    'pain_characteristics': anamnesis_data.get('pain_characteristics', []),
                    'functional_limitations': anamnesis_data.get('functional_limitations', []),
                    'rom_assessment': anamnesis_data.get('rom_area', ''),
                    'strength_assessment': anamnesis_data.get('strength_muscle_group', '')
                })
                current_app.logger.info("Anamnesis parsed as JSON format")
            except (json.JSONDecodeError, TypeError):
                # If not JSON, treat as plain text and extract what we can
                current_app.logger.info("Anamnesis is in plain text format, extracting information...")
                anamnesis_text = patient.anamnesis.lower()
                
                # Extract chief complaint from the text
                if 'motivo' in anamnesis_text or 'consulta' in anamnesis_text:
                    lines = patient.anamnesis.split('\n')
                    for line in lines:
                        if 'motivo' in line.lower() and ':' in line:
                            clinical_context['chief_complaint'] = line.split(':', 1)[1].strip()
                            break
                
                # Extract pain level
                import re
                pain_match = re.search(r'(\d+)/10', anamnesis_text)
                if pain_match:
                    clinical_context['pain_level'] = pain_match.group(1)
                
                # Extract age if available
                age_match = re.search(r'edad[:\s]*(\d+)', anamnesis_text)
                if age_match:
                    clinical_context['patient_demographics']['age'] = int(age_match.group(1))
                
                # Use the full anamnesis text as additional context
                clinical_context['anamnesis_full_text'] = patient.anamnesis
                
                current_app.logger.info(f"Extracted from plain text - Chief complaint: {clinical_context['chief_complaint']}, Pain level: {clinical_context['pain_level']}")
        else:
            current_app.logger.warning("No anamnesis data found for patient")
        
                # Generate AI suggestions using the existing function with user's language
        suggestions = generate_clinical_suggestions_ai(clinical_context, user_language)

        # Check if we have DeepSeek API configured to inform the user
        deepseek_api_key = current_app.config.get('DEEPSEEK_API_KEY')
        analysis_type = "AI-powered (DeepSeek)" if deepseek_api_key else "Rule-based (No AI key configured)"
        
        current_app.logger.info(f"Clinical analysis completed using: {analysis_type}")
        
        # Save suggestions to patient profile
        import json
        from datetime import datetime
        
        # Convert arrays to plain text strings for display
        def format_suggestions_as_text(suggestions_list):
            if not suggestions_list:
                return ""
            return "\n".join([f"• {item}" for item in suggestions_list])
        
        patient.ai_suggested_tests = format_suggestions_as_text(suggestions.get('tests', []))
        patient.ai_red_flags = format_suggestions_as_text(suggestions.get('red_flags', []))
        patient.ai_yellow_flags = format_suggestions_as_text(suggestions.get('yellow_flags', []))
        patient.ai_clinical_notes = format_suggestions_as_text(suggestions.get('clinical_notes', []))
        patient.ai_analysis_date = datetime.utcnow()
        
        db.session.commit()
        
        current_app.logger.info(f"Clinical analysis saved to patient {patient_id} profile")
        
        return jsonify({
            'success': True,
            'message': f'Clinical analysis completed and saved to patient profile ({analysis_type})',
            'suggestions': suggestions,
            'analysis_type': analysis_type,
            'analysis_date': patient.ai_analysis_date.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        current_app.logger.error(f"Error generating clinical analysis for patient {patient_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error generating clinical analysis: {str(e)}'
        }), 500

@api.route('/generate-ai-suggestions', methods=['POST'])
@login_required
def generate_ai_suggestions():
    """Generate clinical suggestions using AI based on anamnesis data in the user's preferred language"""
    try:
        data = request.get_json()
        anamnesis_data = data.get('anamnesis_data', {})
        
        # Get user's preferred language
        user_language = getattr(current_user, 'language', 'es')
        current_app.logger.info(f"Using user's preferred language: {user_language}")
        
        # Prepare the clinical data for AI analysis
        clinical_context = {
            'chief_complaint': anamnesis_data.get('anamnesis_chief_complaint', ''),
            'diagnosis': anamnesis_data.get('diagnosis', ''),
            'pain_level': anamnesis_data.get('anamnesis_pain_scale', ''),
            'onset_date': anamnesis_data.get('anamnesis_onset_date', ''),
            'mechanism': anamnesis_data.get('anamnesis_mechanism', ''),
            'medical_history': {
                'conditions': anamnesis_data.get('history_conditions', []),
                'surgeries': anamnesis_data.get('surgery_description', []),
                'medications': anamnesis_data.get('anamnesis_medications', ''),
                'allergies': anamnesis_data.get('allergies', [])
            },
            'functional_assessment': {
                'pain_characteristics': anamnesis_data.get('pain_characteristics', []),
                'functional_limitations': anamnesis_data.get('functional_limitations', []),
                'rom_assessment': anamnesis_data.get('rom_area', ''),
                'strength_assessment': anamnesis_data.get('strength_muscle_group', '')
            },
            'patient_demographics': {
                'age': calculate_age_from_dob(anamnesis_data.get('date_of_birth', '')),
                'gender': anamnesis_data.get('anamnesis_gender', ''),
                'occupation': anamnesis_data.get('anamnesis_occupation', ''),
                'activity_level': anamnesis_data.get('anamnesis_physical_activity', '')
            }
        }
        
        # Generate AI suggestions using DeepSeek or fallback with user's language
        suggestions = generate_clinical_suggestions_ai(clinical_context, user_language)
        
        return jsonify({
            'success': True,
            'suggestions': suggestions
        })
        
    except Exception as e:
        current_app.logger.error(f"Error generating AI suggestions: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error generating suggestions: {str(e)}'
        }), 500

def calculate_age_from_dob(dob_string):
    """Calculate age from date of birth string"""
    if not dob_string:
        return None
    try:
        dob = datetime.strptime(dob_string, '%Y-%m-%d').date()
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except:
        return None

def generate_clinical_suggestions_ai(clinical_context, language='es'):
    """Generate clinical suggestions using DeepSeek AI based on clinical context data in the user's preferred language"""
    try:
        # Use the provided language or default to Spanish
        
        # Define language instructions for the AI
        language_instructions = {
            'en': "Please respond in English.",
            'es': "Por favor responde en español.",
            'it': "Per favore rispondi in italiano.",
            'fr': "Veuillez répondre en français.",
            'de': "Bitte antworten Sie auf Deutsch.",
            'pt': "Por favor responda em português."
        }
        
        language_instruction = language_instructions.get(language, language_instructions['es'])
        current_app.logger.info(f"Generating clinical analysis in language: {language}")
        
        deepseek_api_key = current_app.config.get('DEEPSEEK_API_KEY')
        
        if deepseek_api_key:
            from openai import OpenAI
            
            # Initialize the OpenAI client with DeepSeek's API endpoint
            client = OpenAI(
                api_key=deepseek_api_key,
                base_url="https://api.deepseek.com"
            )
            
            current_app.logger.info("DeepSeek API client initialized for clinical suggestions")
            
            # Anonymize the clinical data for privacy compliance
            anonymized_data = {
                'chief_complaint': clinical_context.get('chief_complaint', ''),
                'diagnosis': clinical_context.get('diagnosis', ''),
                'pain_level': clinical_context.get('pain_level', ''),
                'onset_timing': anonymize_date(clinical_context.get('onset_date', '')),
                'mechanism': clinical_context.get('mechanism', ''),
                'age_range': anonymize_age(clinical_context['patient_demographics'].get('age')),
                'gender': clinical_context['patient_demographics'].get('gender', ''),
                'occupation_type': anonymize_occupation(clinical_context['patient_demographics'].get('occupation', '')),
                'activity_level': clinical_context['patient_demographics'].get('activity_level', ''),
                'medical_conditions': clinical_context['medical_history'].get('conditions', []),
                'surgery_types': anonymize_surgeries(clinical_context['medical_history'].get('surgeries', [])),
                'medication_types': anonymize_medications(clinical_context['medical_history'].get('medications', '')),
                'allergy_types': clinical_context['medical_history'].get('allergies', []),
                'pain_characteristics': clinical_context['functional_assessment'].get('pain_characteristics', []),
                'functional_limitations': clinical_context['functional_assessment'].get('functional_limitations', []),
                'rom_area': clinical_context['functional_assessment'].get('rom_assessment', ''),
                'strength_area': clinical_context['functional_assessment'].get('strength_assessment', '')
            }
            
            current_app.logger.info(f"Anonymized data prepared - Diagnosis: {anonymized_data['diagnosis']}")
            
            # Prepare additional anamnesis section if available
            additional_anamnesis = ""
            if clinical_context.get('anamnesis_full_text'):
                newline_char = "\n"
                additional_anamnesis = f"ADDITIONAL CLINICAL NOTES FROM ANAMNESIS:{newline_char}{clinical_context.get('anamnesis_full_text', '')}"
            
            # Prepare the anonymized prompt for clinical analysis
            prompt = f"""
{language_instruction}

As an experienced physiotherapist, analyze the following ANONYMIZED patient case and provide clinical recommendations in {language.upper()}:

CLINICAL PRESENTATION:
- Chief Complaint: {anonymized_data['chief_complaint']}
- Primary Diagnosis: {anonymized_data['diagnosis']}
- Pain Level: {anonymized_data['pain_level']}/10
- Onset: {anonymized_data['onset_timing']} ({anonymized_data['mechanism']})
- Age Range: {anonymized_data['age_range']}
- Gender: {anonymized_data['gender']}
- Occupation Type: {anonymized_data['occupation_type']}
- Activity Level: {anonymized_data['activity_level']}

MEDICAL HISTORY:
- Previous Conditions: {', '.join(anonymized_data['medical_conditions']) if anonymized_data['medical_conditions'] else 'None reported'}
- Previous Surgery Types: {', '.join(anonymized_data['surgery_types']) if anonymized_data['surgery_types'] else 'None reported'}
- Medication Categories: {anonymized_data['medication_types'] or 'None reported'}
- Allergy Types: {', '.join(anonymized_data['allergy_types']) if anonymized_data['allergy_types'] else 'None reported'}

FUNCTIONAL ASSESSMENT:
- Pain Characteristics: {', '.join(anonymized_data['pain_characteristics']) if anonymized_data['pain_characteristics'] else 'Not specified'}
- Functional Limitations: {', '.join(anonymized_data['functional_limitations']) if anonymized_data['functional_limitations'] else 'Not specified'}
- ROM Assessment Area: {anonymized_data['rom_area'] or 'Not specified'}
- Strength Assessment Area: {anonymized_data['strength_area'] or 'Not specified'}

{additional_anamnesis}

Please provide your recommendations in JSON format with the following structure:
{{
    "tests": ["list of specific clinical tests to perform"],
    "red_flags": ["list of serious warning signs to watch for"],
    "yellow_flags": ["list of psychosocial factors to consider"],
    "clinical_notes": ["list of additional clinical considerations and recommendations"]
}}

Focus on evidence-based recommendations specific to the presented condition. Include 3-5 items in each category when relevant.
"""
            
            current_app.logger.info("Making API call to DeepSeek")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": f"You are an expert physiotherapist providing clinical recommendations based on ANONYMIZED patient assessment data. Always respond with valid JSON in {language.upper()} language. Never request or use any personally identifiable information. {language_instruction}"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            # Parse the AI response
            ai_response = response.choices[0].message.content.strip()
            current_app.logger.info(f"DeepSeek API response received: {ai_response[:100]}...")
            
            # Try to extract JSON from the response
            import json
            import re
            
            # Look for JSON within the response
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if json_match:
                suggestions_json = json.loads(json_match.group())
                
                # Log anonymized analysis for compliance tracking
                current_app.logger.info(f"AI clinical analysis completed for anonymized case: {anonymized_data['diagnosis']} - Age: {anonymized_data['age_range']} - Pain: {anonymized_data['pain_level']}/10 - Language: {language}")
                
                return suggestions_json
            else:
                current_app.logger.warning("Failed to parse JSON from DeepSeek response, using fallback")
                # Fallback if JSON parsing fails
                return generate_fallback_suggestions(clinical_context, language)
                
        else:
            current_app.logger.info("No DeepSeek API key configured, using fallback suggestions")
            # Fallback to rule-based suggestions if no API key
            return generate_fallback_suggestions(clinical_context, language)
            
    except Exception as e:
        current_app.logger.error(f"Error with AI suggestions: {str(e)}")
        current_app.logger.info("Using fallback suggestions due to error")
        return generate_fallback_suggestions(clinical_context, language)

def anonymize_date(date_string):
    """Convert specific dates to relative time periods"""
    if not date_string:
        return "Not specified"
    
    try:
        from datetime import datetime, date
        onset_date = datetime.strptime(date_string, '%Y-%m-%d').date()
        today = date.today()
        days_ago = (today - onset_date).days
        
        if days_ago < 7:
            return "Within the last week"
        elif days_ago < 30:
            return "2-4 weeks ago"
        elif days_ago < 90:
            return "1-3 months ago"
        elif days_ago < 365:
            return "3-12 months ago"
        else:
            return "Over a year ago"
    except:
        return "Not specified"

def anonymize_age(age):
    """Convert specific age to age ranges"""
    if not age:
        return "Not specified"
    
    if age < 18:
        return "Under 18"
    elif age < 30:
        return "18-29"
    elif age < 45:
        return "30-44"
    elif age < 60:
        return "45-59"
    elif age < 75:
        return "60-74"
    else:
        return "75+"

def anonymize_occupation(occupation):
    """Convert specific occupations to general categories"""
    if not occupation:
        return "Not specified"
    
    occupation_lower = occupation.lower()
    
    # Desk/office work
    if any(word in occupation_lower for word in ['office', 'desk', 'computer', 'admin', 'manager', 'accountant', 'lawyer', 'engineer']):
        return "Desk/office work"
    
    # Physical labor
    elif any(word in occupation_lower for word in ['construction', 'mechanic', 'factory', 'warehouse', 'delivery', 'manual', 'laborer']):
        return "Physical labor"
    
    # Healthcare
    elif any(word in occupation_lower for word in ['nurse', 'doctor', 'healthcare', 'medical', 'physio', 'therapist']):
        return "Healthcare worker"
    
    # Education
    elif any(word in occupation_lower for word in ['teacher', 'professor', 'education', 'school']):
        return "Education sector"
    
    # Service industry
    elif any(word in occupation_lower for word in ['waiter', 'retail', 'customer', 'service', 'sales', 'chef', 'cook']):
        return "Service industry"
    
    # Driving/transport
    elif any(word in occupation_lower for word in ['driver', 'transport', 'taxi', 'truck', 'delivery']):
        return "Transportation"
    
    # Retired
    elif any(word in occupation_lower for word in ['retired', 'pension']):
        return "Retired"
    
    # Student
    elif any(word in occupation_lower for word in ['student', 'university', 'college']):
        return "Student"
    
    else:
        return "Other profession"

def anonymize_surgeries(surgeries):
    """Convert specific surgery descriptions to general categories"""
    if not surgeries:
        return []
    
    anonymized = []
    for surgery in surgeries:
        if not surgery:
            continue
            
        surgery_lower = surgery.lower()
        
        if any(word in surgery_lower for word in ['knee', 'acl', 'meniscus', 'patella']):
            anonymized.append("Knee surgery")
        elif any(word in surgery_lower for word in ['shoulder', 'rotator', 'clavicle']):
            anonymized.append("Shoulder surgery")
        elif any(word in surgery_lower for word in ['hip', 'femur']):
            anonymized.append("Hip surgery")
        elif any(word in surgery_lower for word in ['spine', 'back', 'lumbar', 'cervical', 'disc']):
            anonymized.append("Spinal surgery")
        elif any(word in surgery_lower for word in ['ankle', 'foot']):
            anonymized.append("Foot/ankle surgery")
        elif any(word in surgery_lower for word in ['wrist', 'hand', 'finger']):
            anonymized.append("Hand/wrist surgery")
        elif any(word in surgery_lower for word in ['elbow']):
            anonymized.append("Elbow surgery")
        else:
            anonymized.append("Other orthopedic surgery")
    
    return list(set(anonymized))  # Remove duplicates

def anonymize_medications(medications):
    """Convert specific medications to general categories"""
    if not medications:
        return "None reported"
    
    medications_lower = medications.lower()
    categories = []
    
    if any(word in medications_lower for word in ['ibuprofen', 'naproxen', 'diclofenac', 'nsaid']):
        categories.append("NSAIDs")
    if any(word in medications_lower for word in ['paracetamol', 'acetaminophen', 'tylenol']):
        categories.append("Analgesics")
    if any(word in medications_lower for word in ['opioid', 'morphine', 'codeine', 'tramadol']):
        categories.append("Opioid pain medications")
    if any(word in medications_lower for word in ['muscle relaxant', 'baclofen', 'cyclobenzaprine']):
        categories.append("Muscle relaxants")
    if any(word in medications_lower for word in ['antidepressant', 'ssri', 'antianxiety']):
        categories.append("Mood medications")
    if any(word in medications_lower for word in ['blood pressure', 'hypertension', 'ace inhibitor']):
        categories.append("Cardiovascular medications")
    if any(word in medications_lower for word in ['diabetes', 'insulin', 'metformin']):
        categories.append("Diabetes medications")
    if any(word in medications_lower for word in ['supplement', 'vitamin', 'calcium', 'magnesium']):
        categories.append("Supplements/vitamins")
    
    if not categories:
        return "Other medications"
    
    return ", ".join(categories)

def generate_fallback_suggestions(clinical_context, language='es'):
    """Generate basic suggestions when AI is not available"""
    
    # Define multilingual suggestions
    translations = {
        'es': {
            'shoulder_tests': [
                "Test de impingement de Neer",
                "Test de Hawkins-Kennedy",
                "Test de la lata vacía (Jobe)",
                "Signo de retraso de rotación externa"
            ],
            'knee_tests': [
                "Test de Lachman (LCA)",
                "Test de McMurray (menisco)",
                "Test de aprensión rotuliana",
                "Evaluación de sentadilla unipodal"
            ],
            'back_tests': [
                "Test de elevación de pierna recta",
                "Test de Slump",
                "Tests de tensión neural",
                "ROM de flexión/extensión lumbar"
            ],
            'red_flags': [
                "Considerar patología relacionada con la edad (>50 años)",
                "Dolor nocturno - descartar patología grave"
            ],
            'yellow_flags': [
                "Considerar factores laborales y ergonomía"
            ],
            'clinical_notes': [
                "Documentar mediciones basales para seguimiento",
                "Considerar educación del paciente sobre manejo de la condición"
            ]
        },
        'en': {
            'shoulder_tests': [
                "Neer impingement test",
                "Hawkins-Kennedy test",
                "Empty can test (Jobe test)",
                "External rotation lag sign"
            ],
            'knee_tests': [
                "Lachman test (ACL)",
                "McMurray test (meniscus)",
                "Patellar apprehension test",
                "Single leg squat assessment"
            ],
            'back_tests': [
                "Straight leg raise test",
                "Slump test",
                "Neural tension tests",
                "Lumbar flexion/extension ROM"
            ],
            'red_flags': [
                "Consider age-related pathology (>50 years)",
                "Night pain - rule out serious pathology"
            ],
            'yellow_flags': [
                "Consider work-related factors and ergonomics"
            ],
            'clinical_notes': [
                "Document baseline measurements for progress tracking",
                "Consider patient education on condition management"
            ]
        },
        'it': {
            'shoulder_tests': [
                "Test di impingement di Neer",
                "Test di Hawkins-Kennedy",
                "Test della lattina vuota (Jobe)",
                "Segno di ritardo di rotazione esterna"
            ],
            'knee_tests': [
                "Test di Lachman (LCA)",
                "Test di McMurray (menisco)",
                "Test di apprensione rotulea",
                "Valutazione squat monopodalico"
            ],
            'back_tests': [
                "Test di sollevamento gamba tesa",
                "Test di Slump",
                "Test di tensione neurale",
                "ROM flessione/estensione lombare"
            ],
            'red_flags': [
                "Considerare patologia legata all'età (>50 anni)",
                "Dolore notturno - escludere patologia grave"
            ],
            'yellow_flags': [
                "Considerare fattori lavorativi ed ergonomia"
            ],
            'clinical_notes': [
                "Documentare misurazioni basali per il monitoraggio",
                "Considerare educazione del paziente sulla gestione della condizione"
            ]
        }
    }
    
    # Default to Spanish if language not supported
    lang_data = translations.get(language, translations['es'])
    
    suggestions = {
        "tests": [],
        "red_flags": [],
        "yellow_flags": [],
        "clinical_notes": []
    }
    
    # Basic rule-based suggestions based on diagnosis and symptoms
    diagnosis = clinical_context.get('diagnosis', '').lower()
    chief_complaint = clinical_context.get('chief_complaint', '').lower()
    
    # Basic test recommendations
    if 'shoulder' in diagnosis or 'shoulder' in chief_complaint or 'hombro' in diagnosis or 'hombro' in chief_complaint:
        suggestions["tests"].extend(lang_data['shoulder_tests'])
    
    if 'knee' in diagnosis or 'knee' in chief_complaint or 'rodilla' in diagnosis or 'rodilla' in chief_complaint:
        suggestions["tests"].extend(lang_data['knee_tests'])
    
    if any(word in diagnosis or word in chief_complaint for word in ['back', 'lumbar', 'espalda', 'lumbar']):
        suggestions["tests"].extend(lang_data['back_tests'])
    
    # Red flags based on age and symptoms
    age = clinical_context['patient_demographics'].get('age', 0)
    if age and age > 50:
        suggestions["red_flags"].append(lang_data['red_flags'][0])
    
    if any(phrase in chief_complaint for phrase in ['night pain', 'constant pain', 'dolor nocturno', 'dolor constante']):
        suggestions["red_flags"].append(lang_data['red_flags'][1])
    
    # Yellow flags
    if clinical_context['patient_demographics'].get('occupation'):
        suggestions["yellow_flags"].append(lang_data['yellow_flags'][0])
    
    # Clinical notes
    suggestions["clinical_notes"].extend(lang_data['clinical_notes'])
    
    return suggestions