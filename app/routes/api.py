from flask import Blueprint, jsonify, current_app, request
import requests
from datetime import datetime, timedelta, date
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
                    # Patient exists, check if treatment already exists for this patient and start_time
                    existing_treatment = Treatment.query.filter_by(
                        patient_id=patient.id,
                        created_at=start_time
                        # Consider adding calendly_invitee_uri if it was reliably unique before
                    ).first()
                    
                    if not existing_treatment:
                        new_treatment = Treatment(
                            patient_id=patient.id,
                            practitioner_id=current_user.id,
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
    """Try to find a matching patient using name and email, scoped to the current user."""
    # First try exact email match for the current user
    patient = Patient.query.filter_by(contact=email, practitioner_id=current_user.id).first()
    if patient:
        return patient
    
    # Try name matching (first name only) for the current user
    first_name = name.split()[0].lower()
    potential_matches = Patient.query.filter(
        Patient.practitioner_id == current_user.id,
        func.lower(Patient.name).like(f"{first_name}%")
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
        Patient.practitioner_id == current_user.id,
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
        patient = Patient.query.filter_by(id=patient_id, practitioner_id=current_user.id).first_or_404('Patient not found or not authorized')
        
        booking.status = 'Matched'
        booking.matched_patient_id = patient_id
        
        existing_treatment = Treatment.query.filter_by(
            created_at=booking.start_time,
            patient_id=patient_id
        ).first()
        
        if not existing_treatment:
            treatment = Treatment(
                patient_id=patient.id,
                created_at=booking.start_time,
                treatment_type=booking.event_type,
                status="Scheduled",
                notes=f"Linked to Calendly booking. Matched by admin user.",
                calendly_invitee_uri=booking.calendly_invitee_id,
                practitioner_id=current_user.id
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
            practitioner_id=current_user.id
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
                practitioner_id=current_user.id
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
        patient = Patient.query.filter_by(id=id, practitioner_id=current_user.id).first_or_404()
        # Full report generation logic should be here
        report_content = "Report generation logic is complex and omitted for this summary. It should call an AI model."
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
            'message': 'Report generated successfully',
            'report_id': report.id
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Exception in generate_patient_report: {str(e)}")
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
        
        patient = Patient.query.filter_by(id=patient_id, practitioner_id=current_user.id).first_or_404()
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
            Patient.practitioner_id == current_user.id,
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
    patient = Patient.query.filter_by(id=patient_id, practitioner_id=current_user.id).first_or_404()

    treatment = Treatment(
        patient_id=patient_id,
        practitioner_id=current_user.id,
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
        patient = Patient.query.filter_by(id=report.patient_id, practitioner_id=current_user.id).first_or_404()

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
        patient = Patient.query.filter_by(id=id, practitioner_id=current_user.id).first_or_404()
        # AI generation logic here
        prescription_content = "AI Generated Exercise Prescription"
        return jsonify({
            'success': True,
            'prescription': prescription_content
        })
    except Exception as e:
        current_app.logger.error(f"Error in generate_exercise_prescription: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

@api.route('/treatment/<int:id>/set-payment', methods=['POST'])
@login_required
def set_treatment_payment_method(id):
    try:
        data = request.get_json()
        payment_method = data.get('payment_method')
        treatment = Treatment.query.filter_by(id=id, practitioner_id=current_user.id).first_or_404()
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
        treatment = Treatment.query.filter_by(id=id, practitioner_id=current_user.id).first_or_404()
        treatment.fee = fee_value
        db.session.commit()
        return jsonify({'success': True, 'new_fee': fee_value})
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
        treatment = Treatment.query.filter_by(id=id, practitioner_id=current_user.id).first_or_404()
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
        data = db.session.query(
            Treatment.treatment_type,
            func.sum(Treatment.fee_charged).label('total_fee')
        ).join(Patient, Patient.id == Treatment.patient_id) \
         .filter(Patient.user_id == current_user.id, Treatment.fee_charged.isnot(None)) \
         .group_by(Treatment.treatment_type).all()
        
        result = [{'treatment_type': item.treatment_type or 'Uncategorized', 'total_fee': float(item.total_fee or 0)} for item in data]
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
        data = db.session.query(
            Patient.name,
            func.sum(Treatment.fee_charged).label('total_revenue')
        ).join(Treatment, Patient.id == Treatment.patient_id) \
         .filter(Patient.user_id == current_user.id, Treatment.fee_charged.isnot(None)) \
         .group_by(Patient.name) \
         .order_by(func.sum(Treatment.fee_charged).desc()) \
         .limit(10).all()
        
        results = [{'name': name, 'revenue': float(total_revenue or 0)} for name, total_revenue in data]
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
    try:
        data = request.get_json()
        plan_id = data.get('plan_id')

        plan = Plan.query.filter_by(id=plan_id).first_or_404()
        
        if not plan.stripe_price_id:
            return jsonify({'error': f'Plan \'{plan.name}\' does not have a Stripe Price ID configured.'}), 400

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': plan.stripe_price_id, 'quantity': 1}],
            mode='subscription',
            success_url=url_for('main.subscription_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('main.pricing', _external=True),
            client_reference_id=str(current_user.id),
            customer_email=current_user.email
        )
        return jsonify({'sessionId': checkout_session.id})

    except Exception as e:
        current_app.logger.error(f"Error in create_checkout_session: {str(e)}", exc_info=True)
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
    user_id = session.get('client_reference_id')
    stripe_customer_id = session.get('customer')
    stripe_subscription_id = session.get('subscription')

    user = User.query.get(user_id)
    if not user:
        current_app.logger.error(f"Webhook Error: No user found with ID {user_id}")
        return

    user.stripe_customer_id = stripe_customer_id
    
    line_item = stripe.checkout.Session.list_line_items(session.id, limit=1).data[0]
    stripe_price_id = line_item.price.id
    plan = Plan.query.filter_by(stripe_price_id=stripe_price_id).first()

    if not plan:
        current_app.logger.error(f"Webhook Error: No plan found with stripe_price_id {stripe_price_id}")
        return

    # Deactivate old subscriptions
    UserSubscription.query.filter_by(user_id=user_id).update({"status": "canceled"})

    new_subscription = UserSubscription(
        user_id=user.id,
        plan_id=plan.id,
        stripe_subscription_id=stripe_subscription_id,
        status='active'
    )
    db.session.add(new_subscription)
    db.session.commit()
    current_app.logger.info(f"New subscription created for user {user.id}")

def handle_subscription_change(subscription_data):
    stripe_subscription_id = subscription_data.id
    subscription = UserSubscription.query.filter_by(stripe_subscription_id=stripe_subscription_id).first()
    
    if subscription:
        subscription.status = subscription_data.status
        if subscription_data.get('ended_at'):
            subscription.ended_at = datetime.fromtimestamp(subscription_data.get('ended_at'))
        db.session.commit()
        current_app.logger.info(f"Subscription {stripe_subscription_id} status updated to {subscription.status}")

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