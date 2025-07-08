from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.models import db, Clinic, ClinicMembership, ClinicSubscription, Plan, User
from app.forms import ClinicForm
from datetime import datetime, timedelta
import secrets
import string
from functools import wraps

clinic = Blueprint('clinic', __name__)

def clinic_plan_required(f):
    """Decorator to ensure user has a clinic plan (Standard or Premium)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user has an individual plan that includes clinic features
        user_plan = current_user.active_plan
        if user_plan and user_plan.slug in ['standard-usd', 'premium-usd']:
            return f(*args, **kwargs)
        
        # Check if user is in a clinic with a valid plan
        if current_user.is_in_clinic:
            clinic_obj = current_user.clinic
            clinic_plan = clinic_obj.active_plan
            if clinic_plan and clinic_plan.slug in ['standard-usd', 'premium-usd']:
                return f(*args, **kwargs)
        
        # Admin override - allow for development/testing purposes only
        # Remove this in production or add a separate admin clinic management interface
        if current_user.is_admin:
            flash('Admin access: Clinic features normally require a Standard or Premium plan.', 'info')
            return f(*args, **kwargs)
        
        # User doesn't have clinic plan access
        flash('Clinic features require a Standard or Premium plan. Please upgrade to access clinic functionality.', 'warning')
        return redirect(url_for('main.manage_subscription'))
    
    return decorated_function

@clinic.route('/dashboard')
@login_required
@clinic_plan_required
def dashboard():
    """Clinic dashboard - main page for clinic management"""
    if not current_user.is_in_clinic:
        return redirect(url_for('clinic.choose_option'))
    
    clinic_obj = current_user.clinic
    membership = current_user.active_clinic_membership
    
    # Get clinic stats
    members = clinic_obj.active_members.all()
    practitioners = clinic_obj.practitioners.all()
    total_patients = clinic_obj.patient_count
    
    # Get recent activity (you can expand this later)
    recent_activity = []
    
    return render_template('clinic/dashboard.html', 
                         clinic=clinic_obj,
                         membership=membership,
                         members=members,
                         practitioners=practitioners,
                         total_patients=total_patients,
                         recent_activity=recent_activity)

@clinic.route('/choose')
@login_required
def choose_option():
    """Choose whether to create a new clinic or join an existing one"""
    if current_user.is_in_clinic:
        return redirect(url_for('clinic.dashboard'))
    
    # Check if user has clinic plan before showing options
    if not current_user.is_admin:
        user_plan = current_user.active_plan
        if not user_plan or user_plan.slug not in ['standard-usd', 'premium-usd']:
            flash('Clinic features require a Standard or Premium plan. Please upgrade to access clinic functionality.', 'warning')
            return redirect(url_for('main.manage_subscription'))
    
    return render_template('clinic/choose_option.html')

@clinic.route('/create', methods=['GET', 'POST'])
@login_required
@clinic_plan_required
def create():
    """Create a new clinic"""
    if current_user.is_in_clinic:
        flash('You are already part of a clinic.', 'warning')
        return redirect(url_for('clinic.dashboard'))
    
    # For GET requests, redirect to user settings with clinic tab active
    if request.method == 'GET':
        flash('Please fill out your clinic information to create a new clinic.', 'info')
        return redirect(url_for('main.user_settings', tab='clinic'))
    
    form = ClinicForm()
    if form.validate_on_submit():
        try:
            # Create the clinic
            clinic_obj = Clinic(
                name=form.clinic_name.data,
                description=form.clinic_description.data,
                address=form.clinic_address.data,
                phone=form.clinic_phone.data,
                email=form.clinic_email.data,
                website=form.clinic_website.data,
                clinic_first_session_fee=form.clinic_first_session_fee.data,
                clinic_subsequent_session_fee=form.clinic_subsequent_session_fee.data,
                clinic_percentage_agreement=form.clinic_percentage_agreement.data,
                clinic_percentage_amount=form.clinic_percentage_amount.data
            )
            db.session.add(clinic_obj)
            db.session.flush()  # Get the clinic ID
            
            # Create membership for the creator (as admin)
            membership = ClinicMembership(
                user_id=current_user.id,
                clinic_id=clinic_obj.id,
                role='admin',
                joined_at=datetime.utcnow()
            )
            membership.set_permissions_by_role()
            db.session.add(membership)
            
            db.session.commit()
            flash(f'Clinic "{clinic_obj.name}" created successfully! You are now the clinic administrator.', 'success')
            return redirect(url_for('clinic.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while creating the clinic. Please try again.', 'error')
            current_app.logger.error(f"Error creating clinic: {str(e)}")
    
    # If form validation fails, redirect back to user settings with errors
    return redirect(url_for('main.user_settings', tab='clinic'))

@clinic.route('/join')
@login_required
@clinic_plan_required
def join():
    """Join an existing clinic via invitation"""
    if current_user.is_in_clinic:
        flash('You are already part of a clinic.', 'warning')
        return redirect(url_for('clinic.dashboard'))
    
    return render_template('clinic/join.html')

@clinic.route('/join/<token>')
@login_required
@clinic_plan_required
def join_with_token(token):
    """Join a clinic using an invitation token"""
    if current_user.is_in_clinic:
        flash('You are already part of a clinic.', 'warning')
        return redirect(url_for('clinic.dashboard'))
    
    # Find the invitation
    invitation = ClinicMembership.query.filter_by(
        invitation_token=token,
        is_active=False
    ).first()
    
    if not invitation:
        flash('Invalid or expired invitation link.', 'error')
        return redirect(url_for('clinic.choose_option'))
    
    # Check if invitation is expired
    if invitation.invitation_expires_at and invitation.invitation_expires_at < datetime.utcnow():
        flash('This invitation has expired.', 'error')
        return redirect(url_for('clinic.choose_option'))
    
    # Check if user is already the invited user
    if invitation.user_id != current_user.id:
        flash('This invitation is not for your account.', 'error')
        return redirect(url_for('clinic.choose_option'))
    
    try:
        # Activate the membership
        invitation.is_active = True
        invitation.joined_at = datetime.utcnow()
        invitation.invitation_token = None  # Clear the token
        
        # Mark user as no longer new since they're joining a clinic
        current_user.is_new_user = False
        
        db.session.commit()
        flash(f'Successfully joined {invitation.clinic.name}!', 'success')
        return redirect(url_for('clinic.dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while joining the clinic. Please try again.', 'error')
        current_app.logger.error(f"Error joining clinic: {str(e)}")
    
    return redirect(url_for('clinic.choose_option'))

@clinic.route('/members')
@login_required
@clinic_plan_required
def members():
    """Manage clinic members"""
    if not current_user.is_in_clinic:
        return redirect(url_for('clinic.choose_option'))
    
    clinic_obj = current_user.clinic
    membership = current_user.active_clinic_membership
    
    if not membership.can_manage_practitioners:
        flash('You do not have permission to manage practitioners.', 'error')
        return redirect(url_for('clinic.dashboard'))
    
    members = clinic_obj.active_members.all()
    
    return render_template('clinic/members.html', 
                         clinic=clinic_obj,
                         membership=membership,
                         members=members)

@clinic.route('/invite', methods=['POST'])
@login_required
@clinic_plan_required
def invite_practitioner():
    """Invite a new practitioner to the clinic"""
    if not current_user.is_in_clinic:
        return jsonify({'success': False, 'message': 'You are not part of a clinic'}), 400
    
    clinic_obj = current_user.clinic
    membership = current_user.active_clinic_membership
    
    if not membership.can_manage_practitioners:
        return jsonify({'success': False, 'message': 'You do not have permission to invite practitioners'}), 403
    
    data = request.get_json()
    email = data.get('email')
    role = data.get('role', 'practitioner')
    
    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400
    
    if role not in ['practitioner', 'assistant']:
        return jsonify({'success': False, 'message': 'Invalid role'}), 400
    
    # Check if clinic can add more practitioners
    if not clinic_obj.can_add_practitioner():
        return jsonify({'success': False, 'message': 'Clinic has reached its practitioner limit'}), 400
    
    try:
        # Find existing user
        user = User.query.filter_by(email=email).first()
        
        if user:
            # User exists - check if they're already in a clinic
            if user.is_in_clinic:
                return jsonify({'success': False, 'message': 'User is already part of a clinic'}), 400
            
            # Check if there's already a pending invitation for this user
            existing_invitation = ClinicMembership.query.filter_by(
                user_id=user.id,
                clinic_id=clinic_obj.id
            ).first()
            
            if existing_invitation:
                if existing_invitation.is_active:
                    return jsonify({'success': False, 'message': 'User is already a member of this clinic'}), 400
                else:
                    # Update existing invitation
                    existing_invitation.role = role
                    existing_invitation.invitation_expires_at = datetime.utcnow() + timedelta(days=7)
                    existing_invitation.invited_by_user_id = current_user.id
                    existing_invitation.invited_at = datetime.utcnow()
                    invitation = existing_invitation
            else:
                # Create new invitation for existing user
                invitation = ClinicMembership(
                    user_id=user.id,
                    clinic_id=clinic_obj.id,
                    role=role,
                    is_active=False,
                    invitation_expires_at=datetime.utcnow() + timedelta(days=7),
                    invited_by_user_id=current_user.id
                )
                invitation.set_permissions_by_role()
                db.session.add(invitation)
                
            message_type = "existing_user"
        else:
            # User doesn't exist - create invitation without user_id (they'll register later)
            # Check if there's already a pending invitation for this email
            existing_invitation = ClinicMembership.query.filter_by(
                clinic_id=clinic_obj.id,
                invited_email=email,
                user_id=None
            ).filter(
                ClinicMembership.invitation_expires_at > datetime.utcnow()
            ).first()
            
            if existing_invitation:
                # Update existing invitation
                existing_invitation.role = role
                existing_invitation.invitation_expires_at = datetime.utcnow() + timedelta(days=7)
                existing_invitation.invited_by_user_id = current_user.id
                existing_invitation.invited_at = datetime.utcnow()
                invitation = existing_invitation
            else:
                # Create new invitation for non-existing user
                invitation = ClinicMembership(
                    user_id=None,  # Will be set when they register
                    clinic_id=clinic_obj.id,
                    role=role,
                    is_active=False,
                    invitation_expires_at=datetime.utcnow() + timedelta(days=7),
                    invited_by_user_id=current_user.id,
                    invited_email=email  # Store the email for later matching
                )
                invitation.set_permissions_by_role()
                db.session.add(invitation)
            
            message_type = "new_user"
        
        # Generate invitation token
        invitation.invitation_token = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        
        db.session.commit()
        
        # In a real application, you would send an email here
        if message_type == "existing_user":
            invitation_link = url_for('clinic.join_with_token', token=invitation.invitation_token, _external=True)
            message = f'Invitation sent to existing user {email}'
        else:
            invitation_link = url_for('clinic.register_and_join', token=invitation.invitation_token, email=email, _external=True)
            message = f'Invitation sent to {email}. They will be able to create an account and join the clinic.'
        
        return jsonify({
            'success': True, 
            'message': message,
            'invitation_link': invitation_link  # For now, return the link (in production, send via email)
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error inviting practitioner: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while sending the invitation'}), 500

@clinic.route('/settings', methods=['GET', 'POST'])
@login_required
@clinic_plan_required
def settings():
    """Manage clinic settings"""
    if not current_user.is_in_clinic:
        return redirect(url_for('clinic.choose_option'))
    
    clinic_obj = current_user.clinic
    membership = current_user.active_clinic_membership
    
    if not membership.can_manage_settings:
        flash('You do not have permission to manage clinic settings.', 'error')
        return redirect(url_for('clinic.dashboard'))
    
    # For GET requests, redirect to user settings with clinic tab active
    if request.method == 'GET':
        return redirect(url_for('main.user_settings', tab='clinic'))
    
    form = ClinicForm(obj=clinic_obj)
    if form.validate_on_submit():
        try:
            clinic_obj.name = form.clinic_name.data
            clinic_obj.description = form.clinic_description.data
            clinic_obj.address = form.clinic_address.data
            clinic_obj.phone = form.clinic_phone.data
            clinic_obj.email = form.clinic_email.data
            clinic_obj.website = form.clinic_website.data
            clinic_obj.clinic_first_session_fee = form.clinic_first_session_fee.data
            clinic_obj.clinic_subsequent_session_fee = form.clinic_subsequent_session_fee.data
            clinic_obj.clinic_percentage_agreement = form.clinic_percentage_agreement.data
            clinic_obj.clinic_percentage_amount = form.clinic_percentage_amount.data
            
            db.session.commit()
            flash('Clinic settings updated successfully!', 'success')
            return redirect(url_for('main.user_settings', tab='clinic'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating clinic settings.', 'error')
            current_app.logger.error(f"Error updating clinic settings: {str(e)}")
    
    # If form validation fails, redirect back to user settings with errors
    return redirect(url_for('main.user_settings', tab='clinic'))

@clinic.route('/remove-member/<int:member_id>', methods=['POST'])
@login_required
@clinic_plan_required
def remove_member(member_id):
    """Remove a member from the clinic"""
    if not current_user.is_in_clinic:
        return jsonify({'success': False, 'message': 'You are not part of a clinic'}), 400
    
    clinic_obj = current_user.clinic
    membership = current_user.active_clinic_membership
    
    if not membership.can_manage_practitioners:
        return jsonify({'success': False, 'message': 'You do not have permission to remove members'}), 403
    
    # Find the member to remove
    member_to_remove = ClinicMembership.query.filter_by(
        id=member_id,
        clinic_id=clinic_obj.id,
        is_active=True
    ).first()
    
    if not member_to_remove:
        return jsonify({'success': False, 'message': 'Member not found'}), 404
    
    # Prevent removing yourself
    if member_to_remove.user_id == current_user.id:
        return jsonify({'success': False, 'message': 'You cannot remove yourself from the clinic'}), 400
    
    # Prevent removing the last admin
    if member_to_remove.role == 'admin':
        admin_count = clinic_obj.memberships.filter_by(role='admin', is_active=True).count()
        if admin_count <= 1:
            return jsonify({'success': False, 'message': 'Cannot remove the last administrator'}), 400
    
    try:
        member_to_remove.is_active = False
        member_to_remove.left_at = datetime.utcnow()
        
        db.session.commit()
        
        member_name = f"{member_to_remove.user.first_name} {member_to_remove.user.last_name}"
        return jsonify({
            'success': True, 
            'message': f'{member_name} has been removed from the clinic'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error removing clinic member: {e}")
        return jsonify({'success': False, 'message': 'An error occurred while removing the member'}), 500

@clinic.route('/update-member-permissions', methods=['POST'])
@login_required
@clinic_plan_required
def update_member_permissions():
    """Update permissions for a clinic member"""
    if not current_user.is_in_clinic:
        return jsonify({'success': False, 'message': 'You are not part of a clinic'}), 400
    
    clinic_obj = current_user.clinic
    membership = current_user.active_clinic_membership
    
    if not membership.can_manage_practitioners:
        return jsonify({'success': False, 'message': 'You do not have permission to manage member permissions'}), 403
    
    try:
        data = request.get_json()
        member_id = data.get('member_id')
        permissions = data.get('permissions', {})
        
        # Find the member to update
        member = ClinicMembership.query.filter_by(
            id=member_id,
            clinic_id=clinic_obj.id,
            is_active=True
        ).first()
        
        if not member:
            return jsonify({'success': False, 'message': 'Member not found'}), 404
        
        # Prevent updating admin permissions
        if member.role == 'admin':
            return jsonify({'success': False, 'message': 'Cannot update admin permissions'}), 400
        
        # Update permissions
        member.can_manage_patients = permissions.get('can_manage_patients', False)
        member.can_view_reports = permissions.get('can_view_reports', False)
        member.can_manage_billing = permissions.get('can_manage_billing', False)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Member permissions updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating member permissions: {e}")
        return jsonify({'success': False, 'message': 'An error occurred while updating permissions'}), 500

@clinic.route('/leave', methods=['POST'])
@login_required
@clinic_plan_required
def leave():
    """Leave the current clinic"""
    if not current_user.is_in_clinic:
        return jsonify({'success': False, 'message': 'You are not part of a clinic'}), 400
    
    membership = current_user.active_clinic_membership
    clinic_obj = current_user.clinic
    
    # Check if user is the only admin
    if membership.role == 'admin':
        admin_count = clinic_obj.memberships.filter_by(role='admin', is_active=True).count()
        if admin_count <= 1:
            return jsonify({'success': False, 'message': 'You cannot leave the clinic as you are the only administrator. Please assign another admin first.'}), 400
    
    try:
        membership.is_active = False
        membership.left_at = datetime.utcnow()
        
        db.session.commit()
        flash(f'You have left {clinic_obj.name}.', 'info')
        return jsonify({'success': True, 'redirect': url_for('clinic.choose_option')})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error leaving clinic: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while leaving the clinic'}), 500

@clinic.route('/register-and-join/<token>')
def register_and_join(token):
    """Allow new users to register and join clinic in one step"""
    invitation = ClinicMembership.query.filter_by(
        invitation_token=token,
        user_id=None,  # Only for invitations to non-users
        is_active=False
    ).first()
    
    if not invitation:
        flash('Invalid or expired invitation link', 'error')
        return redirect(url_for('auth.register'))
    
    if invitation.invitation_expires_at < datetime.utcnow():
        flash('This invitation has expired', 'error')
        return redirect(url_for('auth.register'))
    
    clinic_obj = invitation.clinic
    invited_by = User.query.get(invitation.invited_by_user_id)
    
    return render_template('clinic/register_and_join.html', 
                         invitation=invitation, 
                         clinic=clinic_obj, 
                         invited_by=invited_by,
                         email=invitation.invited_email)

@clinic.route('/complete-registration/<token>', methods=['POST'])
def complete_registration(token):
    """Complete registration and join clinic"""
    invitation = ClinicMembership.query.filter_by(
        invitation_token=token,
        user_id=None,
        is_active=False
    ).first()
    
    if not invitation or invitation.invitation_expires_at < datetime.utcnow():
        flash('Invalid or expired invitation link', 'error')
        return redirect(url_for('auth.register'))
    
    from app.forms import ClinicRegistrationForm
    form = ClinicRegistrationForm()
    
    if form.validate_on_submit():
        try:
            # Create new user
            user = User(
                username=form.username.data,
                email=invitation.invited_email,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                role='practitioner',
                is_new_user=False  # Don't show welcome flow for clinic users
            )
            user.set_password(form.password.data)
            
            # Add user to database
            db.session.add(user)
            db.session.flush()  # Get the user ID
            
            # Update invitation with user_id and activate
            invitation.user_id = user.id
            invitation.is_active = True
            invitation.invitation_token = None  # Clear the token
            invitation.joined_at = datetime.utcnow()
            
            db.session.commit()
            
            # Log the user in
            from flask_login import login_user
            login_user(user)
            
            flash(f'Welcome! You have successfully joined {invitation.clinic.name}', 'success')
            return redirect(url_for('clinic.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error completing registration: {e}")
            flash('An error occurred during registration. Please try again.', 'error')
    
    # If form validation fails, return to registration page with errors
    clinic_obj = invitation.clinic
    invited_by = User.query.get(invitation.invited_by_user_id)
    
    return render_template('clinic/register_and_join.html', 
                         invitation=invitation, 
                         clinic=clinic_obj, 
                         invited_by=invited_by,
                         email=invitation.invited_email,
                         form=form) 