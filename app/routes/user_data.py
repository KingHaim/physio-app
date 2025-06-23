from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, request
from flask_login import login_required, current_user, logout_user
from app import db
from datetime import datetime

user_data = Blueprint('user_data', __name__)

@user_data.route('/my-data')
@login_required
def my_data():
    user = current_user
    # Add more fields as needed
    user_info = {
        'username': user.email,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else None,
        'sex': user.sex,
        'license_number': user.license_number,
        'clinic_name': user.clinic_name,
        'clinic_address': user.clinic_address,
        'clinic_phone': user.clinic_phone,
        'clinic_email': user.clinic_email,
        'clinic_website': user.clinic_website,
        'clinic_description': user.clinic_description,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'consent_given': user.consent_given,
        'consent_date': user.consent_date.isoformat() if user.consent_date else None,
        'is_deleted': user.is_deleted,
    }
    return render_template('user_data/my_data.html', user_info=user_info)

@user_data.route('/export_data')
@login_required
def export_data():
    user = current_user
    data = {
        'username': user.email,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else None,
        'sex': user.sex,
        'license_number': user.license_number,
        'clinic_name': user.clinic_name,
        'clinic_address': user.clinic_address,
        'clinic_phone': user.clinic_phone,
        'clinic_email': user.clinic_email,
        'clinic_website': user.clinic_website,
        'clinic_description': user.clinic_description,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'consent_given': user.consent_given,
        'consent_date': user.consent_date.isoformat() if user.consent_date else None,
        'is_deleted': user.is_deleted,
    }
    return jsonify(data)

@user_data.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user = current_user
    user.is_deleted = True
    db.session.commit()
    logout_user()
    flash('Your account has been marked for deletion. If this was a mistake, contact support.', 'info')
    return redirect(url_for('auth.login'))

@user_data.route('/user/profile', methods=['GET'])
@login_required
def get_user_profile():
    user = current_user
    return jsonify({
        'id': user.id,
        'email': user.email,
        'username': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else None,
        'sex': user.sex,
        'license_number': user.license_number,
        'clinic_name': user.clinic_name,
        'clinic_address': user.clinic_address,
        'clinic_phone': user.clinic_phone,
        'clinic_email': user.clinic_email,
        'clinic_website': user.clinic_website,
        'clinic_description': user.clinic_description,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'consent_given': user.consent_given,
        'consent_date': user.consent_date.isoformat() if user.consent_date else None,
        'is_deleted': user.is_deleted,
        'is_admin': user.is_admin,
    }) 