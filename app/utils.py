from datetime import datetime, timedelta
from flask import current_app
from app.models import Treatment, Patient, RecurringAppointment, db
from sqlalchemy import func, and_
import logging
import json

def mark_past_treatments_as_completed(user_id=None):
    """Mark past treatments with status 'Scheduled' as 'Completed'"""
    try:
        today = datetime.now().date()
        
        query = Treatment.query.filter(
            and_(
                Treatment.created_at < today,
                Treatment.status == 'Scheduled'
            )
        )

        if user_id:
            query = query.join(Patient).filter(Patient.user_id == user_id)
        
        past_treatments = query.all()
        
        count = 0
        for treatment in past_treatments:
            treatment.status = 'Completed'
            count += 1
        
        if count > 0:
            db.session.commit()
            current_app.logger.info(
                "Automatically marked %s past treatments as Completed (user_id: %s)",
                count,
                user_id if user_id else 'global'
            )
        
        return count
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking past treatments as completed: {str(e)}")
        raise


def convert_past_recurring_to_treatments(user_id=None):
    """
    Convert past recurring appointment occurrences to actual Treatment records.
    This ensures all past appointments are properly recorded in the treatment history.
    """
    try:
        today = datetime.now().date()
        created_count = 0
        
        # Get recurring appointments to process
        recurring_query = RecurringAppointment.query.filter(
            RecurringAppointment.is_active == True,
            RecurringAppointment.start_date <= today
        )
        
        if user_id:
            recurring_query = recurring_query.join(Patient).filter(Patient.user_id == user_id)
        
        active_rules = recurring_query.all()
        
        for rule in active_rules:
            if not rule.patient or not rule.time_of_day:
                continue
                
            # Start from rule start date, end at today (don't create future treatments)
            current_date = rule.start_date
            end_date = min(today, rule.end_date) if rule.end_date else today
            
            while current_date <= end_date:
                is_valid_occurrence = False
                
                # Check based on recurrence type
                if rule.recurrence_type == 'weekly':
                    if current_date.weekday() == rule.start_date.weekday():
                        is_valid_occurrence = True
                elif rule.recurrence_type == 'daily-mon-fri':
                    if current_date.weekday() < 5:  # Monday to Friday
                        is_valid_occurrence = True
                elif rule.recurrence_type == 'daily':
                    is_valid_occurrence = True
                
                if is_valid_occurrence:
                    # Combine date with the rule's time_of_day
                    occurrence_datetime = datetime.combine(current_date, rule.time_of_day)
                    
                    # Check if a treatment already exists for this exact datetime and patient
                    exists = Treatment.query.filter_by(
                        patient_id=rule.patient_id,
                        created_at=occurrence_datetime
                    ).first()
                    
                    if not exists:
                        # Determine status based on how old the appointment is
                        if current_date < today:
                            # Past appointments default to completed
                            status = 'Completed'
                        else:
                            # Today's appointments are scheduled
                            status = 'Scheduled'
                        
                        # Create the new treatment record
                        new_treatment = Treatment(
                            patient_id=rule.patient_id,
                            treatment_type=rule.treatment_type,
                            notes=f"Auto-generated from recurring rule #{rule.id}",
                            status=status,
                            provider=rule.provider,
                            created_at=occurrence_datetime,
                            updated_at=datetime.now(),
                            location=rule.location,
                            fee_charged=rule.fee_charged,
                            payment_method=rule.payment_method
                        )
                        db.session.add(new_treatment)
                        created_count += 1
                
                # Move to the next day
                current_date += timedelta(days=1)
        
        if created_count > 0:
            db.session.commit()
            current_app.logger.info(
                "Auto-converted %s past recurring appointments to treatments (user_id: %s)",
                created_count,
                user_id if user_id else 'global'
            )
        
        return created_count
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error converting past recurring appointments: {str(e)}")
        raise


def sync_calendly_for_user(user):
    """
    Sync Calendly events for a specific user
    """
    try:
        if not user.calendly_api_token or not user.calendly_user_uri:
            return {'new_treatments': 0, 'new_unmatched_bookings': 0}
        
        import requests
        from datetime import timedelta
        from app.models import UnmatchedCalendlyBooking, Patient, Treatment
        
        api_token = user.calendly_api_token
        user_calendly_uri_for_events = user.calendly_user_uri
        
        headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'PhysioTracker/1.0'
        }
        
        # Get scheduled events for the next 30 days
        min_time = datetime.utcnow().isoformat() + 'Z'
        max_time = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
        
        events_url = 'https://api.calendly.com/scheduled_events'
        params = {
            'user': user_calendly_uri_for_events,
            'min_start_time': min_time,
            'max_start_time': max_time,
            'status': 'active',
            'sort': 'start_time:asc'
        }
        
        events_response = requests.get(events_url, headers=headers, params=params, timeout=10)
        
        if events_response.status_code != 200:
            current_app.logger.warning(f"Calendly sync failed for user {user.id}: {events_response.status_code}")
            return {'new_treatments': 0, 'new_unmatched_bookings': 0}
        
        events = events_response.json()['collection']
        synced_treatments_count = 0
        newly_created_unmatched_bookings_count = 0
        
        for event in events:
            event_uri = event['uri']
            event_uuid = event_uri.split('/')[-1]
            
            invitees_url = f'https://api.calendly.com/scheduled_events/{event_uuid}/invitees'
            invitees_response = requests.get(invitees_url, headers=headers, timeout=10)
            
            if invitees_response.status_code != 200:
                continue
            
            invitees = invitees_response.json()['collection']
            
            for invitee in invitees:
                invitee_uri = invitee['uri']
                invitee_uuid = invitee_uri.split('/')[-1]
                
                name = invitee['name']
                email = invitee['email']
                start_time = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                event_type_name = event['name']
                
                # Check if already exists
                existing_unmatched_booking = UnmatchedCalendlyBooking.query.filter_by(
                    calendly_invitee_id=invitee_uuid,
                    user_id=user.id
                ).first()
                
                if existing_unmatched_booking:
                    continue  # Skip if already processed
                
                # Try to find matching patient by email
                patient = Patient.query.filter_by(email=email, user_id=user.id).first()
                
                if patient:
                    # Create treatment directly
                    treatment = Treatment(
                        patient_id=patient.id,
                        created_at=start_time,
                        treatment_type=event_type_name,
                        status="Scheduled",
                        provider=user.email,
                        notes=f"Auto-synced from Calendly. Invitee: {name} ({email})",
                        calendly_invitee_uri=invitee_uuid
                    )
                    db.session.add(treatment)
                    synced_treatments_count += 1
                else:
                    # Create unmatched booking for review
                    unmatched_booking = UnmatchedCalendlyBooking(
                        user_id=user.id,
                        name=name,
                        email=email,
                        event_type=event_type_name,
                        start_time=start_time,
                        calendly_invitee_id=invitee_uuid,
                        status='Pending'
                    )
                    db.session.add(unmatched_booking)
                    newly_created_unmatched_bookings_count += 1
        
        db.session.commit()
        
        return {
            'new_treatments': synced_treatments_count,
            'new_unmatched_bookings': newly_created_unmatched_bookings_count
        }
        
    except Exception as e:
        current_app.logger.error(f"Error syncing Calendly for user {user.id}: {str(e)}")
        return {'new_treatments': 0, 'new_unmatched_bookings': 0}


def auto_sync_appointments(user_id=None):
    """
    Combined function to sync all appointment data:
    1. Convert past recurring appointments to treatments
    2. Mark past treatments as completed
    3. Sync Calendly events (if configured)
    """
    try:
        created_count = convert_past_recurring_to_treatments(user_id)
        completed_count = mark_past_treatments_as_completed(user_id)
        
        # Sync Calendly for the specific user
        calendly_synced = {'new_treatments': 0, 'new_unmatched_bookings': 0}
        if user_id:
            from app.models import User
            user = User.query.get(user_id)
            if user:
                calendly_synced = sync_calendly_for_user(user)
        
        return {
            'created_treatments': created_count,
            'completed_treatments': completed_count,
            'calendly_treatments': calendly_synced['new_treatments'],
            'calendly_bookings': calendly_synced['new_unmatched_bookings']
        }
    except Exception as e:
        current_app.logger.error(f"Error in auto_sync_appointments: {str(e)}")
        raise


def mark_inactive_patients(user_id=None):
    """Mark patients as 'Inactive' if they haven't had a booking in the last 2 months"""
    try:
        today = datetime.now().date()
        two_months_ago = today - timedelta(days=60)
        
        patient_query = Patient.query.filter_by(status='Active')
        if user_id:
            patient_query = patient_query.filter_by(user_id=user_id)
        
        active_patients = patient_query.all()
        
        count = 0
        for patient in active_patients:
            # When checking latest_treatment, it should also be implicitly filtered by user if patient list is filtered.
            # However, for clarity or if patient list wasn't pre-filtered, you might join Treatment and filter by Patient.user_id here too.
            # For now, relying on the active_patients list being correctly filtered.
            latest_treatment = Treatment.query.filter_by(patient_id=patient.id).order_by(Treatment.created_at.desc()).first()
            
            if not latest_treatment or latest_treatment.created_at.date() < two_months_ago:
                patient.status = 'Inactive'
                count += 1
        
        if count > 0:
            db.session.commit()
            current_app.logger.info(
                "Automatically marked %s patients as Inactive (user_id: %s)",
                count,
                user_id if user_id else 'global'
            )
        
        return count
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking patients as inactive: {str(e)}")
        raise

def log_sensitive_operation(operation_type, user_id, details=None, success=True):
    """
    Log sensitive operations for security monitoring.
    
    Args:
        operation_type (str): Type of operation (e.g., 'login', 'data_access', 'payment')
        user_id (int): ID of the user performing the operation
        details (dict): Additional details about the operation
        success (bool): Whether the operation was successful
    """
    try:
        from app.models import SecurityLog
        from flask import request
        
        log_entry = SecurityLog(
            user_id=user_id,
            event_type=operation_type,
            details=json.dumps(details) if details else None,
            success=success,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None,
            created_at=datetime.utcnow()
        )
        
        db.session.add(log_entry)
        db.session.commit()
        
        # Also log to application logger
        level = logging.INFO if success else logging.WARNING
        current_app.logger.log(level, 
            f"Sensitive operation: {operation_type} by user {user_id} - "
            f"Success: {success}, Details: {details}")
            
    except Exception as e:
        current_app.logger.error(f"Failed to log sensitive operation: {str(e)}")
        # Don't raise the exception to avoid breaking the main operation

def log_api_access(endpoint, user_id=None, method='GET', status_code=200, response_time=None):
    """
    Log API access for monitoring and analytics.
    
    Args:
        endpoint (str): API endpoint being accessed
        user_id (int): ID of the user making the request
        method (str): HTTP method used
        status_code (int): HTTP status code returned
        response_time (float): Response time in seconds
    """
    try:
        # Log to application logger
        user_info = f"user_id:{user_id}" if user_id else "anonymous"
        current_app.logger.info(
            f"API Access: {method} {endpoint} - {user_info} - "
            f"Status: {status_code} - "
            f"Response Time: {response_time:.3f}s" if response_time else "N/A"
        )
        
        # Log sensitive API endpoints with extra detail
        sensitive_endpoints = [
            '/api/patients', '/api/treatments', '/api/payments',
            '/auth/', '/webhooks/', '/admin/'
        ]
        
        if any(endpoint.startswith(ep) for ep in sensitive_endpoints):
            current_app.logger.warning(
                f"SENSITIVE API ACCESS: {method} {endpoint} - {user_info} - "
                f"Status: {status_code}"
            )
            
    except Exception as e:
        current_app.logger.error(f"Failed to log API access: {str(e)}")

def monitor_database_performance():
    """
    Monitor database performance and log slow queries.
    This is a basic implementation - you might want to use more sophisticated tools.
    """
    try:
        # Get database connection info
        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        db_type = 'postgresql' if 'postgresql' in db_uri else 'sqlite' if 'sqlite' in db_uri else 'unknown'
        
        current_app.logger.info(f"Database type: {db_type}")
        
        # For PostgreSQL, you could add more sophisticated monitoring here
        if db_type == 'postgresql':
            # Example: Check connection pool status
            current_app.logger.info("PostgreSQL database monitoring active")
            
    except Exception as e:
        current_app.logger.error(f"Database monitoring error: {str(e)}")

def log_error_with_context(error, context=None):
    """
    Log errors with additional context for better debugging.
    
    Args:
        error (Exception): The error that occurred
        context (dict): Additional context about the error
    """
    try:
        from flask import request
        
        error_context = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.utcnow().isoformat(),
            'endpoint': request.endpoint if request else None,
            'method': request.method if request else None,
            'user_id': current_app.current_user.id if hasattr(current_app, 'current_user') and current_app.current_user.is_authenticated else None,
            'ip_address': request.remote_addr if request else None,
            'user_agent': request.headers.get('User-Agent') if request else None,
            'additional_context': context or {}
        }
        
        current_app.logger.error(f"Error with context: {error_context}")
        
        # If Sentry is configured, this will also be sent there
        import sentry_sdk
        if sentry_sdk.Hub.current.client:
            sentry_sdk.capture_exception(error)
            
    except Exception as e:
        current_app.logger.error(f"Failed to log error with context: {str(e)}")
