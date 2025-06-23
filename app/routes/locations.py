from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from flask_babel import _
from app import db
from app.models import Location
from app.forms import LocationForm

locations = Blueprint('locations', __name__)

@locations.route('/locations')
@login_required
def manage_locations():
    """Location management page"""
    user_locations = Location.query.filter_by(user_id=current_user.id, is_active=True).all()
    return render_template('locations/manage.html', locations=user_locations)

@locations.route('/locations/new', methods=['GET', 'POST'])
@login_required
def add_location():
    """Add a new location"""
    form = LocationForm()
    
    if form.validate_on_submit():
        location = Location(
            user_id=current_user.id,
            name=form.name.data,
            address=form.address.data,
            phone=form.phone.data,
            email=form.email.data,
            first_session_fee=form.first_session_fee.data,
            subsequent_session_fee=form.subsequent_session_fee.data,
            fee_percentage=form.fee_percentage.data,
            location_type=form.location_type.data
        )
        
        db.session.add(location)
        db.session.commit()
        
        flash(_('Location "%(name)s" has been added successfully!', name=location.name), 'success')
        return redirect(url_for('locations.manage_locations'))
    
    return render_template('locations/form.html', form=form, title=_('Add Location'))

@locations.route('/locations/<int:location_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_location(location_id):
    """Edit an existing location"""
    location = Location.query.filter_by(id=location_id, user_id=current_user.id).first_or_404()
    form = LocationForm(obj=location)
    
    if form.validate_on_submit():
        location.name = form.name.data
        location.address = form.address.data
        location.phone = form.phone.data
        location.email = form.email.data
        location.first_session_fee = form.first_session_fee.data
        location.subsequent_session_fee = form.subsequent_session_fee.data
        location.fee_percentage = form.fee_percentage.data
        location.location_type = form.location_type.data
        
        db.session.commit()
        
        flash(_('Location "%(name)s" has been updated successfully!', name=location.name), 'success')
        return redirect(url_for('locations.manage_locations'))
    
    return render_template('locations/form.html', form=form, location=location, title=_('Edit Location'))

@locations.route('/locations/<int:location_id>/delete', methods=['POST'])
@login_required
def delete_location(location_id):
    """Delete (deactivate) a location"""
    location = Location.query.filter_by(id=location_id, user_id=current_user.id).first_or_404()
    
    # Check if location has any treatments
    treatment_count = len(location.treatments)
    appointment_count = len(location.recurring_appointments)
    
    if treatment_count > 0 or appointment_count > 0:
        # Don't actually delete, just deactivate
        location.is_active = False
        db.session.commit()
        flash(_('Location "%(name)s" has been deactivated (it has %(treatments)d treatments and %(appointments)d appointments).', 
                name=location.name, treatments=treatment_count, appointments=appointment_count), 'warning')
    else:
        # Safe to delete
        db.session.delete(location)
        db.session.commit()
        flash(_('Location "%(name)s" has been deleted successfully!', name=location.name), 'success')
    
    return redirect(url_for('locations.manage_locations'))

@locations.route('/api/locations')
@login_required
def api_locations():
    """API endpoint to get user's active locations"""
    user_locations = Location.query.filter_by(user_id=current_user.id, is_active=True).all()
    
    locations_data = []
    for location in user_locations:
        locations_data.append({
            'id': location.id,
            'name': location.name,
            'type': location.location_type,
            'first_session_fee': location.first_session_fee,
            'subsequent_session_fee': location.subsequent_session_fee,
            'fee_percentage': location.fee_percentage
        })
    
    return jsonify(locations_data) 