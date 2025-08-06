"""
Google Calendar API integration service
Handles OAuth2 authentication, token management, and calendar operations
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import requests
from flask import current_app, url_for
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.models import User, Treatment, Patient, UnmatchedCalendlyBooking
from app import db

class GoogleCalendarService:
    """Service class for Google Calendar API operations"""
    
    # Required scopes for calendar access
    SCOPES = [
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    
    def __init__(self):
        pass
    
    def get_user_credentials_config(self, user):
        """Get user's own Google Calendar app credentials"""
        return {
            'client_id': user.google_calendar_client_id,
            'client_secret': user.google_calendar_client_secret,
            'redirect_uri': user.google_calendar_redirect_uri or self._get_default_redirect_uri()
        }
    
    def _get_default_redirect_uri(self):
        """Generate default redirect URI"""
        from flask import request, url_for
        try:
            return url_for('google_calendar.oauth_callback', _external=True)
        except:
            return 'http://localhost:5000/google-calendar/callback'
    
    def get_authorization_url(self, user_id: int) -> Optional[str]:
        """Generate OAuth2 authorization URL for user"""
        from app.models import User
        user = User.query.get(user_id)
        if not user or not user.google_calendar_app_configured:
            current_app.logger.warning(f"Google Calendar not configured for user {user_id}")
            return None
        
        config = self.get_user_credentials_config(user)
            
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": config['client_id'],
                        "client_secret": config['client_secret'],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [config['redirect_uri']]
                    }
                },
                scopes=self.SCOPES
            )
            flow.redirect_uri = config['redirect_uri']
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent',  # Force consent to get refresh token
                state=str(user_id)  # Include user_id in state for verification
            )
            
            return authorization_url
            
        except Exception as e:
            current_app.logger.error(f"Error generating Google OAuth URL: {str(e)}")
            return None
    
    def handle_oauth_callback(self, authorization_code: str, state: str) -> Dict[str, Any]:
        """Handle OAuth2 callback and exchange code for tokens"""
        try:
            user_id = int(state)
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            if not user.google_calendar_app_configured:
                return {'success': False, 'error': 'User has not configured Google Calendar app credentials'}
            
            config = self.get_user_credentials_config(user)
            
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": config['client_id'],
                        "client_secret": config['client_secret'],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [config['redirect_uri']]
                    }
                },
                scopes=self.SCOPES,
                state=state
            )
            flow.redirect_uri = config['redirect_uri']
            
            # Exchange authorization code for tokens
            flow.fetch_token(code=authorization_code)
            credentials = flow.credentials
            
            # Store tokens securely in user model
            user.google_calendar_token = credentials.token
            user.google_calendar_refresh_token = credentials.refresh_token
            user.google_calendar_enabled = True
            user.google_calendar_primary_calendar_id = 'primary'
            
            db.session.commit()
            
            current_app.logger.info(f"Google Calendar successfully connected for user {user_id}")
            return {'success': True, 'message': 'Google Calendar connected successfully'}
            
        except Exception as e:
            current_app.logger.error(f"Error in Google OAuth callback: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_credentials(self, user: User) -> Optional[Credentials]:
        """Get valid credentials for a user, refreshing if necessary"""
        if not user.google_calendar_configured:
            return None
        
        try:
            config = self.get_user_credentials_config(user)
            credentials = Credentials(
                token=user.google_calendar_token,
                refresh_token=user.google_calendar_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=config['client_id'],
                client_secret=config['client_secret'],
                scopes=self.SCOPES
            )
            
            # Refresh token if needed
            if credentials.expired:
                from google.auth.transport.requests import Request
                credentials.refresh(Request())
                
                # Update stored tokens
                user.google_calendar_token = credentials.token
                if credentials.refresh_token:
                    user.google_calendar_refresh_token = credentials.refresh_token
                db.session.commit()
                
                current_app.logger.info(f"Refreshed Google Calendar tokens for user {user.id}")
            
            return credentials
            
        except Exception as e:
            current_app.logger.error(f"Error getting Google Calendar credentials for user {user.id}: {str(e)}")
            return None
    
    def get_calendar_service(self, user: User):
        """Get authenticated Google Calendar service"""
        credentials = self.get_credentials(user)
        if not credentials:
            return None
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            return service
        except Exception as e:
            current_app.logger.error(f"Error building Google Calendar service for user {user.id}: {str(e)}")
            return None
    
    def sync_events_for_user(self, user: User) -> Dict[str, int]:
        """Sync Google Calendar events for a specific user"""
        service = self.get_calendar_service(user)
        if not service:
            return {'new_treatments': 0, 'error': 'Unable to connect to Google Calendar'}
        
        try:
            # Get events from the last 30 days to next 90 days
            time_min = (datetime.utcnow() - timedelta(days=30)).isoformat() + 'Z'
            time_max = (datetime.utcnow() + timedelta(days=90)).isoformat() + 'Z'
            
            events_result = service.events().list(
                calendarId=user.google_calendar_primary_calendar_id or 'primary',
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime',
                maxResults=100
            ).execute()
            
            events = events_result.get('items', [])
            new_treatments_count = 0
            
            for event in events:
                # Skip events without start time or summary
                if 'start' not in event or 'summary' not in event:
                    continue
                
                event_id = event['id']
                event_summary = event['summary']
                event_description = event.get('description', '')
                
                # Parse start and end times
                start_time_str = event['start'].get('dateTime', event['start'].get('date'))
                end_time_str = event['end'].get('dateTime', event['end'].get('date'))
                
                if not start_time_str:
                    continue
                
                try:
                    # Handle both datetime and date formats
                    if 'T' in start_time_str:
                        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00')) if end_time_str else start_time + timedelta(hours=1)
                    else:
                        start_time = datetime.fromisoformat(start_time_str)
                        end_time = datetime.fromisoformat(end_time_str) if end_time_str else start_time + timedelta(hours=1)
                except ValueError:
                    continue
                
                # Check if treatment already exists for this event
                existing_treatment = Treatment.query.filter_by(
                    google_calendar_event_id=event_id
                ).join(Patient).filter(Patient.user_id == user.id).first()
                
                if existing_treatment:
                    continue
                
                # Try to match with existing patients based on attendees or description
                patient = self._match_patient_from_event(user, event)
                
                if patient:
                    # Create treatment from Google Calendar event
                    treatment = Treatment(
                        patient_id=patient.id,
                        treatment_type='Appointment from Google Calendar',
                        session_date=start_time.date(),
                        session_time=start_time.time(),
                        duration_minutes=int((end_time - start_time).total_seconds() / 60),
                        assessment=event_description,
                        google_calendar_event_id=event_id,
                        google_calendar_event_summary=event_summary
                    )
                    
                    db.session.add(treatment)
                    new_treatments_count += 1
                    
                    current_app.logger.info(f"Created treatment from Google Calendar event {event_id} for patient {patient.id}")
            
            # Update last sync time
            user.google_calendar_last_sync = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.info(f"Google Calendar sync completed for user {user.id}: {new_treatments_count} new treatments")
            return {'new_treatments': new_treatments_count}
            
        except HttpError as e:
            current_app.logger.error(f"Google Calendar API error for user {user.id}: {str(e)}")
            return {'new_treatments': 0, 'error': f'Google Calendar API error: {str(e)}'}
        except Exception as e:
            current_app.logger.error(f"Error syncing Google Calendar for user {user.id}: {str(e)}")
            return {'new_treatments': 0, 'error': str(e)}
    
    def create_calendar_event(self, user: User, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new event in Google Calendar"""
        service = self.get_calendar_service(user)
        if not service:
            return {'success': False, 'error': 'Unable to connect to Google Calendar'}
        
        try:
            event = service.events().insert(
                calendarId=user.google_calendar_primary_calendar_id or 'primary',
                body=event_data
            ).execute()
            
            current_app.logger.info(f"Created Google Calendar event {event['id']} for user {user.id}")
            return {'success': True, 'event_id': event['id'], 'event_link': event.get('htmlLink')}
            
        except HttpError as e:
            current_app.logger.error(f"Error creating Google Calendar event for user {user.id}: {str(e)}")
            return {'success': False, 'error': f'Google Calendar API error: {str(e)}'}
        except Exception as e:
            current_app.logger.error(f"Error creating Google Calendar event for user {user.id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _match_patient_from_event(self, user: User, event: Dict[str, Any]) -> Optional[Patient]:
        """Try to match a Google Calendar event with an existing patient"""
        # Extract attendee emails
        attendees = event.get('attendees', [])
        attendee_emails = [attendee.get('email', '').lower() for attendee in attendees if attendee.get('email')]
        
        # Try to match by email first
        for email in attendee_emails:
            if email and '@' in email:
                patient = Patient.query.filter(
                    Patient.user_id == user.id,
                    Patient._email.ilike(f'%{email}%')  # Use encrypted field search
                ).first()
                if patient:
                    return patient
        
        # Try to match by name in summary or description
        event_text = f"{event.get('summary', '')} {event.get('description', '')}".lower()
        patients = Patient.query.filter_by(user_id=user.id).all()
        
        for patient in patients:
            if patient.name and patient.name.lower() in event_text:
                return patient
        
        # If no match found, you might want to create an "unmatched" record
        # similar to how Calendly works, but for now return None
        return None


# Initialize the service
google_calendar_service = GoogleCalendarService() 