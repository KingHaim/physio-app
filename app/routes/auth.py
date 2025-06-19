from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from app.models import User, db
from app.forms import RegistrationForm, LoginForm

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
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            # Set session as permanent if remember me is checked
            if form.remember_me.data:
                session.permanent = True
            
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or not is_safe_url(next_page):
                next_page = url_for('main.index')
            return redirect(next_page)
        flash('Invalid email or password', 'danger')
    
    return render_template('auth/login.html', form=form, supported_locales=current_app.config['BABEL_SUPPORTED_LOCALES'])

@auth.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.root'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return render_template('auth/register.html', form=form, supported_locales=current_app.config['BABEL_SUPPORTED_LOCALES']) 

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return render_template('auth/register.html', form=form, supported_locales=current_app.config['BABEL_SUPPORTED_LOCALES'])
        
        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        
        # Make the first registered user an admin ONLY if no other users exist
        if User.query.count() == 0:
            user.is_admin = True
            user.role = 'admin' # Also set role to admin
        else:
            user.role = 'physio' # Default role for other users
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    elif request.method == 'POST':
        # Flash form errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", 'danger')
    
    return render_template('auth/register.html', form=form, supported_locales=current_app.config['BABEL_SUPPORTED_LOCALES']) 