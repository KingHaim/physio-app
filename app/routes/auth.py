from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, current_user, login_required
from app.models import User, db
from app.forms import RegistrationForm, LoginForm
from app.email_utils import send_verification_email, send_welcome_email
from datetime import datetime
import logging

# If the above import fails, try this alternative:
# from werkzeug.utils import url_parse
# If that also fails, use this workaround:
# def url_parse(url):
#     """Simple URL parser to extract netloc."""
#     if '//' in url:
#         _, url = url.split('//', 1)
#     if '/' in url:
#         url, _ = url.split('/', 1)
#     return type('ParseResult', (), {'netloc': url})

# Add this function instead
def is_safe_url(target):
    """Check if the URL is safe for redirects."""
    ref_url = request.host_url
    # Simple check to ensure the redirect URL belongs to the same site
    return target.startswith(ref_url) if target else False

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        current_app.logger.info(f"User already authenticated: {current_user.email} (ID: {current_user.id})")
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        current_app.logger.info(f"Login attempt for email: {form.email.data}")
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            current_app.logger.info(f"Password verified for user: {user.email} (ID: {user.id})")
            
            # TEMPORAL: Email verification disabled - skip email verification check
            # if not user.email_verified:
            #     flash('Por favor verifica tu email antes de iniciar sesión. Revisa tu bandeja de entrada.', 'warning')
            #     return render_template('auth/login.html', form=form, supported_locales=current_app.config['BABEL_SUPPORTED_LOCALES'])
            
            # Set session as permanent if remember me is checked
            if form.remember_me.data:
                session.permanent = True
            
            # Clear any existing session data that might interfere
            session.clear()
            
            current_app.logger.info(f"About to call login_user for: {user.email} (ID: {user.id})")
            login_user(user, remember=form.remember_me.data)
            current_app.logger.info(f"login_user completed. Current user is now: {current_user.email if current_user.is_authenticated else 'Not authenticated'}")
            
            # Set user's preferred language in session if available
            if user.language:
                session['lang'] = user.language
                current_app.logger.info(f"Set user's preferred language '{user.language}' in session")
            
            next_page = request.args.get('next')
            if not next_page or not is_safe_url(next_page):
                next_page = url_for('main.index')
            current_app.logger.info(f"Redirecting to: {next_page}")
            return redirect(next_page)
        else:
            current_app.logger.warning(f"Failed login attempt for email: {form.email.data}")
        flash('Invalid email or password', 'danger')
    
    return render_template('auth/login.html', form=form, supported_locales=current_app.config['BABEL_SUPPORTED_LOCALES'])

@auth.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth.route('/clear-session')
def clear_session():
    """Clear session data - useful for debugging login issues"""
    from flask import session
    logout_user()
    session.clear()
    flash('Session cleared successfully', 'info')
    return redirect(url_for('auth.login'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.root'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return render_template('auth/register.html', form=form, supported_locales=current_app.config['BABEL_SUPPORTED_LOCALES'])
        
        # Create new user
        user = User(username=email, email=email)
        user.set_password(password)
        
        # Set consent information
        if form.consent_checkbox.data:
            user.consent_given = True
            user.consent_date = datetime.utcnow()
        
        # Make the first registered user an admin ONLY if no other users exist
        if User.query.count() == 0:
            user.is_admin = True
            user.role = 'admin'
            user.email_verified = True  # TEMPORAL: Auto-verify new users until email system is configured
        else:
            user.role = 'physio'
            user.email_verified = True  # TEMPORAL: Auto-verify new users until email system is configured
        
        db.session.add(user)
        db.session.commit()
        
        # TEMPORAL: Skip verification email sending until email system is configured
        # Send verification email (unless it's the first admin user)
        # if not user.is_admin:
        #     try:
        #         if send_verification_email(user):
        #             flash('¡Registro exitoso! Te hemos enviado un email de verificación. Revisa tu bandeja de entrada.', 'success')
        #         else:
        #             flash('Registro exitoso, pero hubo un problema enviando el email de verificación. Contacta al soporte.', 'warning')
        #     except Exception as e:
        #         current_app.logger.error(f"Error sending verification email: {str(e)}")
        #         flash('Registro exitoso, pero hubo un problema enviando el email de verificación. Contacta al soporte.', 'warning')
        # else:
        #     flash('Registration successful! You can now log in.', 'success')
        
        flash('¡Registro exitoso! Ya puedes iniciar sesión.', 'success')
        
        return redirect(url_for('auth.login'))
    elif request.method == 'POST':
        # Flash form errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", 'danger')
    
    return render_template('auth/register.html', form=form, supported_locales=current_app.config['BABEL_SUPPORTED_LOCALES'])

@auth.route('/verify-email/<token>')
def verify_email(token):
    """Verify email address using token"""
    if current_user.is_authenticated and current_user.email_verified:
        flash('Tu email ya ha sido verificado.', 'info')
        return redirect(url_for('main.index'))
    
    # Find user by token
    user = User.query.filter_by(email_verification_token=token).first()
    
    if not user:
        # If not found by direct token match, try to find by hashed token
        import hashlib
        hashed_token = hashlib.sha256(token.encode()).hexdigest()
        user = User.query.filter_by(email_verification_token=hashed_token).first()
    
    if not user:
        flash('Enlace de verificación inválido o expirado.', 'danger')
        return redirect(url_for('auth.login'))
    
    # Verify the token
    if user.verify_email_token(token):
        db.session.commit()
        current_app.logger.info(f"Email verified successfully for user: {user.email}")
        
        # Send welcome email
        try:
            send_welcome_email(user)
        except Exception as e:
            current_app.logger.error(f"Error sending welcome email: {str(e)}")
        
        flash('¡Email verificado exitosamente! Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))
    else:
        flash('Enlace de verificación inválido o expirado.', 'danger')
        return redirect(url_for('auth.login'))

@auth.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    """Resend verification email"""
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash('Por favor introduce tu email.', 'danger')
            return render_template('auth/resend_verification.html')
        
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('No se encontró una cuenta con ese email.', 'danger')
            return render_template('auth/resend_verification.html')
        
        if user.email_verified:
            flash('Tu email ya ha sido verificado.', 'info')
            return redirect(url_for('auth.login'))
        
        # Send new verification email
        try:
            if send_verification_email(user):
                db.session.commit()
                flash('Email de verificación reenviado. Revisa tu bandeja de entrada.', 'success')
            else:
                flash('Hubo un problema enviando el email. Inténtalo más tarde.', 'danger')
        except Exception as e:
            current_app.logger.error(f"Error resending verification email: {str(e)}")
            flash('Hubo un problema enviando el email. Inténtalo más tarde.', 'danger')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/resend_verification.html') 