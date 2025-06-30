"""
Custom decorators for the application
"""
from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user

def email_verified_required(f):
    """
    Decorator to require email verification for accessing certain routes
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and not current_user.email_verified:
            flash('Por favor verifica tu email antes de acceder a esta funcionalidad.', 'warning')
            return redirect(url_for('auth.resend_verification'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """
    Decorator to require admin privileges
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acceso denegado. Se requieren privilegios de administrador.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def physio_required(f):
    """
    Decorator to require physio role
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if current_user.role not in ['physio', 'admin']:
            flash('Acceso denegado. Solo fisioterapeutas pueden acceder a esta funcionalidad.', 'danger')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function
