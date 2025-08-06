"""
Google Calendar OAuth2 routes and API endpoints
"""

from flask import Blueprint, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.google_calendar_service import google_calendar_service
from app import db
from app.utils import sync_calendly_for_user  # Import existing sync function for comparison

google_calendar_bp = Blueprint('google_calendar', __name__, url_prefix='/google-calendar')

@google_calendar_bp.route('/connect')
@login_required
def connect():
    """Initiate Google Calendar OAuth2 flow"""
    try:
        authorization_url = google_calendar_service.get_authorization_url(current_user.id)
        if authorization_url:
            return redirect(authorization_url)
        else:
            flash('Google Calendar integration is not configured properly. Please check the server configuration.', 'error')
            return redirect(url_for('main.user_settings'))
    except Exception as e:
        flash(f'Error connecting to Google Calendar: {str(e)}', 'error')
        return redirect(url_for('main.user_settings'))

@google_calendar_bp.route('/disconnect')
@login_required
def disconnect():
    """Disconnect Google Calendar integration"""
    try:
        # Clear Google Calendar tokens and settings
        current_user.google_calendar_token = None
        current_user.google_calendar_refresh_token = None
        current_user.google_calendar_enabled = False
        current_user.google_calendar_primary_calendar_id = None
        current_user.google_calendar_last_sync = None
        
        db.session.commit()
        flash('Google Calendar has been disconnected successfully.', 'success')
        
    except Exception as e:
        flash(f'Error disconnecting Google Calendar: {str(e)}', 'error')
    
    return redirect(url_for('main.user_settings'))

@google_calendar_bp.route('/callback')
def oauth_callback():
    """Handle OAuth2 callback from Google"""
    try:
        authorization_code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        if error:
            flash(f'Google Calendar authorization failed: {error}', 'error')
            return redirect(url_for('main.user_settings'))
        
        if not authorization_code or not state:
            flash('Invalid callback from Google Calendar.', 'error')
            return redirect(url_for('main.user_settings'))
        
        result = google_calendar_service.handle_oauth_callback(authorization_code, state)
        
        if result['success']:
            flash('Google Calendar connected successfully! You can now sync your calendar events.', 'success')
        else:
            flash(f'Failed to connect Google Calendar: {result.get("error", "Unknown error")}', 'error')
        
    except Exception as e:
        flash(f'Error processing Google Calendar callback: {str(e)}', 'error')
    
    return redirect(url_for('main.user_settings'))

@google_calendar_bp.route('/sync', methods=['POST'])
@login_required
def sync_events():
    """Sync Google Calendar events for the current user"""
    try:
        if not current_user.google_calendar_configured:
            return jsonify({
                'success': False, 
                'error': 'Google Calendar is not properly configured. Please connect your account first.'
            }), 400
        
        result = google_calendar_service.sync_events_for_user(current_user)
        
        if 'error' in result:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
        
        return jsonify({
            'success': True,
            'message': f'Sync completed successfully. {result["new_treatments"]} new treatments created.',
            'new_treatments': result['new_treatments']
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@google_calendar_bp.route('/create-event', methods=['POST'])
@login_required
def create_event():
    """Create a new event in Google Calendar"""
    try:
        if not current_user.google_calendar_configured:
            return jsonify({
                'success': False,
                'error': 'Google Calendar is not properly configured.'
            }), 400
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['summary', 'start_time', 'end_time']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Prepare event data for Google Calendar API
        event_data = {
            'summary': data['summary'],
            'description': data.get('description', ''),
            'start': {
                'dateTime': data['start_time'],
                'timeZone': data.get('timezone', 'UTC')
            },
            'end': {
                'dateTime': data['end_time'],
                'timeZone': data.get('timezone', 'UTC')
            }
        }
        
        # Add attendees if provided
        if 'attendees' in data and data['attendees']:
            event_data['attendees'] = [{'email': email} for email in data['attendees']]
        
        # Add location if provided
        if 'location' in data:
            event_data['location'] = data['location']
        
        result = google_calendar_service.create_calendar_event(current_user, event_data)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Event created successfully in Google Calendar.',
                'event_id': result['event_id'],
                'event_link': result.get('event_link')
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@google_calendar_bp.route('/status')
@login_required
def status():
    """Get Google Calendar connection status for current user"""
    try:
        is_configured = current_user.google_calendar_configured
        last_sync = None
        
        if current_user.google_calendar_last_sync:
            last_sync = current_user.google_calendar_last_sync.isoformat()
        
        return jsonify({
            'connected': is_configured,
            'enabled': current_user.google_calendar_enabled,
            'last_sync': last_sync,
            'primary_calendar_id': current_user.google_calendar_primary_calendar_id
        })
        
    except Exception as e:
        return jsonify({
            'connected': False,
            'error': str(e)
        }), 500 