from flask import Blueprint, request, jsonify, flash, redirect, url_for, session
from flask_login import login_required, current_user
from flask_babel import _
from app.models import db, User, Location
from app.forms import WelcomeOnboardingForm

onboarding = Blueprint('onboarding', __name__)

@onboarding.route('/api/user-onboarding-data')
@login_required
def get_user_onboarding_data():
    """Get user's current data to pre-populate the onboarding form"""
    user_data = {
        'language': current_user.language or 'en',
        'first_name': current_user.first_name or '',
        'last_name': current_user.last_name or '',
        'clinic_name': current_user.clinic_name or '',
        'pays_commission': current_user.clinic_percentage_agreement or False,
        'commission_percentage': current_user.clinic_percentage_amount or '',
        'first_session_fee': current_user.clinic_first_session_fee or '',
        'subsequent_session_fee': current_user.clinic_subsequent_session_fee or '',
        'work_type': determine_work_type(current_user),
        'needs_onboarding': current_user.is_new_user
    }
    
    return jsonify(user_data)

@onboarding.route('/api/save-onboarding', methods=['POST'])
@login_required
def save_onboarding():
    """Save onboarding data without validating the entire form"""
    try:
        data = request.get_json()
        
        # Update user language preference
        if 'language' in data and data['language']:
            current_user.language = data['language']
            session['language'] = data['language']
        
        # Update personal information
        if 'first_name' in data and data['first_name']:
            current_user.first_name = data['first_name']
        if 'last_name' in data and data['last_name']:
            current_user.last_name = data['last_name']
        
        # Update work setup based on selection
        work_type = data.get('work_type')
        
        if work_type in ['clinic_employee', 'mixed'] and data.get('clinic_name'):
            current_user.clinic_name = data['clinic_name']
            if data.get('pays_commission') and data.get('commission_percentage'):
                current_user.clinic_percentage_agreement = True
                current_user.clinic_percentage_amount = float(data['commission_percentage'])
        
        # Update fee structure
        if data.get('first_session_fee'):
            try:
                current_user.clinic_first_session_fee = float(data['first_session_fee'])
            except (ValueError, TypeError):
                pass
                
        if data.get('subsequent_session_fee'):
            try:
                current_user.clinic_subsequent_session_fee = float(data['subsequent_session_fee'])
            except (ValueError, TypeError):
                pass
        
        # Create or update default locations based on work type
        if work_type and 'create_locations' in data and data['create_locations']:
            # Remove existing default locations
            existing_locations = Location.query.filter_by(user_id=current_user.id).all()
            for loc in existing_locations:
                if loc.name in ['Home Visit', 'Main Clinic'] or loc.name == current_user.clinic_name:
                    db.session.delete(loc)
            
            if work_type == 'freelance':
                # Create "Home Visit" location
                home_location = Location(
                    user_id=current_user.id,
                    name='Home Visit',
                    location_type='Home Visit',
                    first_session_fee=current_user.clinic_first_session_fee,
                    subsequent_session_fee=current_user.clinic_subsequent_session_fee
                )
                db.session.add(home_location)
            elif work_type == 'clinic_employee':
                # Create clinic location
                clinic_location = Location(
                    user_id=current_user.id,
                    name=current_user.clinic_name or 'Main Clinic',
                    location_type='Clinic',
                    first_session_fee=current_user.clinic_first_session_fee,
                    subsequent_session_fee=current_user.clinic_subsequent_session_fee,
                    fee_percentage=current_user.clinic_percentage_amount
                )
                db.session.add(clinic_location)
            elif work_type == 'mixed':
                # Create both locations
                clinic_location = Location(
                    user_id=current_user.id,
                    name=current_user.clinic_name or 'Main Clinic',
                    location_type='Clinic',
                    first_session_fee=current_user.clinic_first_session_fee,
                    subsequent_session_fee=current_user.clinic_subsequent_session_fee,
                    fee_percentage=current_user.clinic_percentage_amount
                )
                home_location = Location(
                    user_id=current_user.id,
                    name='Home Visit',
                    location_type='Home Visit',
                    first_session_fee=current_user.clinic_first_session_fee,
                    subsequent_session_fee=current_user.clinic_subsequent_session_fee
                )
                db.session.add(clinic_location)
                db.session.add(home_location)
        
        # Mark user as no longer new
        if data.get('complete_onboarding'):
            current_user.is_new_user = False
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': _('Profile updated successfully!')
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False, 
            'message': _('An error occurred while saving your profile. Please try again.'),
            'error': str(e)
        }), 500

def determine_work_type(user):
    """Determine the user's work type based on their current data"""
    has_clinic = bool(user.clinic_name)
    has_commission = bool(user.clinic_percentage_agreement)
    
    # Check if user has locations
    user_locations = Location.query.filter_by(user_id=user.id).all()
    has_home_location = any(loc.location_type == 'Home Visit' for loc in user_locations)
    has_clinic_location = any(loc.location_type == 'Clinic' for loc in user_locations)
    
    if has_clinic and has_home_location:
        return 'mixed'
    elif has_clinic or has_clinic_location:
        return 'clinic_employee'
    elif has_home_location:
        return 'freelance'
    else:
        return ''  # No work type determined yet 