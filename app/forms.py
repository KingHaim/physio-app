from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, PasswordField, DecimalField, SelectField, BooleanField
from wtforms.validators import DataRequired, Optional, Length, Email, URL, EqualTo, NumberRange
from wtforms.fields import DateField
from flask_babel import lazy_gettext as _l

class RegistrationForm(FlaskForm):
    email = StringField(_l('Email'), validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField(_l('Password'), validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(_l('Confirm Password'), validators=[DataRequired(), EqualTo('password')])
    consent_checkbox = BooleanField(_l('I agree to the <a href="/privacy" target="_blank">Privacy Policy</a> and <a href="/terms" target="_blank">Terms & Conditions</a>'), validators=[DataRequired()])
    # For now, plan selection is handled on the backend, defaulting to 'free'
    # We could add a RadioField here later if we want users to select a plan at registration
    # plan = RadioField('Choose Your Plan', choices=[('free', 'Free Plan'), ('pro', 'Pro Plan ($19.99/month)')], default='free')
    submit = SubmitField(_l('Register'))

class LoginForm(FlaskForm):
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    remember_me = BooleanField(_l('Remember Me'))
    submit = SubmitField(_l('Sign In'))

class LocationForm(FlaskForm):
    name = StringField(_l('Location Name'), validators=[DataRequired(), Length(max=150)])
    address = StringField(_l('Address'), validators=[Optional(), Length(max=200)])
    phone = StringField(_l('Phone Number'), validators=[Optional(), Length(max=30)])
    email = StringField(_l('Email'), validators=[Optional(), Email(), Length(max=120)])
    location_type = SelectField(_l('Location Type'), 
                               choices=[('Clinic', _l('Clinic')), ('Home Visit', _l('Home Visit')), ('External', _l('External Location'))],
                               default='Clinic')
    first_session_fee = DecimalField(_l('First Session Fee (€)'), validators=[Optional(), NumberRange(min=0)], places=2)
    subsequent_session_fee = DecimalField(_l('Subsequent Session Fee (€)'), validators=[Optional(), NumberRange(min=0)], places=2)
    fee_percentage = DecimalField(_l('Clinic Fee Percentage (%)'), validators=[Optional(), NumberRange(min=0, max=100)], places=2)
    submit = SubmitField(_l('Save Location'))

class ClinicForm(FlaskForm):
    clinic_name = StringField(_l('Clinic Name'), validators=[DataRequired(), Length(max=150)])
    clinic_address = StringField(_l('Clinic Address'), validators=[Optional(), Length(max=200)])
    clinic_phone = StringField(_l('Phone Number'), validators=[Optional(), Length(max=30)])
    clinic_email = StringField(_l('Clinic Email'), validators=[Optional(), Email(), Length(max=120)])
    clinic_website = StringField(_l('Website'), validators=[Optional(), URL(), Length(max=120)])
    clinic_description = TextAreaField(_l('Description'), validators=[Optional()])
    clinic_first_session_fee = DecimalField(_l('First Session Fee (€)'), validators=[Optional(), NumberRange(min=0)], places=2)
    clinic_subsequent_session_fee = DecimalField(_l('Subsequent Session Fee (€)'), validators=[Optional(), NumberRange(min=0)], places=2)
    clinic_percentage_agreement = BooleanField(_l('Percentage Agreement'))
    clinic_percentage_amount = DecimalField(_l('Clinic Share (%)'), validators=[Optional(), NumberRange(min=0, max=100)], places=2)
    submit = SubmitField(_l('Save Clinic Information'))

# We can add other forms here later, for example, a UserProfileForm
class UserProfileForm(FlaskForm):
    email = StringField(_l('Email'), validators=[Optional(), Email(), Length(max=120)])
    first_name = StringField(_l('First Name'), validators=[Optional(), Length(max=64)])
    last_name = StringField(_l('Last Name'), validators=[Optional(), Length(max=64)])
    date_of_birth = DateField(_l('Date of Birth'), format='%Y-%m-%d', validators=[Optional()])
    sex = SelectField(_l('Sex'), choices=[('Masculino', _l('Male')), ('Femenino', _l('Female')), ('Otro', _l('Other'))], validators=[Optional()])
    license_number = StringField(_l('License Number'), validators=[Optional(), Length(max=64)])
    current_password = PasswordField(_l('Current Password'), validators=[Optional(), Length(min=6)])
    new_password = PasswordField(_l('New Password'), validators=[Optional(), Length(min=6)])
    confirm_new_password = PasswordField(_l('Confirm New Password'), 
                                         validators=[Optional(), EqualTo('new_password', message=_l('New passwords must match.'))])
    submit = SubmitField(_l('Update Profile'))

class UpdateEmailForm(FlaskForm):
    email = StringField(_l('Email'), validators=[DataRequired(), Email(), Length(max=120)])
    submit_email = SubmitField(_l('Update Email'))

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(_l('Current Password'), validators=[DataRequired()])
    new_password = PasswordField(_l('New Password'), validators=[DataRequired(), Length(min=6)])
    confirm_new_password = PasswordField(_l('Confirm New Password'), 
                                         validators=[DataRequired(), EqualTo('new_password', message=_l('New passwords must match.'))])
    submit_password = SubmitField(_l('Change Password'))

class ApiIntegrationsForm(FlaskForm):
    # Integration checkboxes
    enable_calendly = BooleanField(_l('Enable Calendly Integration'))
    # Future integrations can be added here:
    # enable_stripe = BooleanField('Enable Stripe Integration')
    # enable_google_calendar = BooleanField('Enable Google Calendar Integration')
    # enable_zoom = BooleanField('Enable Zoom Integration')
    
    # Calendly fields (will be shown/hidden based on checkbox)
    calendly_api_key = TextAreaField(_l('Calendly API Key'), 
                                     validators=[Optional()],
                                     render_kw={"rows": 3, "placeholder": _l("Paste your Calendly Personal Access Token here...")})
    calendly_user_uri = StringField(_l('Calendly User URI'), 
                                   validators=[Optional(), URL()],
                                   render_kw={"placeholder": "https://api.calendly.com/users/your-user-id"})
    
    # Future API fields can be added here:
    # stripe_secret_key = StringField('Stripe Secret Key', validators=[Optional()])
    # google_calendar_credentials = TextAreaField('Google Calendar Credentials', validators=[Optional()])
    
    submit = SubmitField(_l('Save API Keys'))

# Renamed from FixedCostForm
class FinancialSettingsForm(FlaskForm):
    # Field for setting the overall contribution base
    contribution_base = DecimalField(_l('Set Your Fixed Autónomo Contribution Base (€)'), 
                                   validators=[Optional(), NumberRange(min=0)],
                                   places=2,
                                   description=_l("Leave blank to use automatic calculation based on income brackets."))
    submit_base = SubmitField(_l('Save Contribution Base')) # Separate submit for this

    # Fields for adding individual fixed costs
    description = StringField(_l('Cost Description'), validators=[Optional(), Length(max=150)])
    monthly_amount = DecimalField(_l('Monthly Amount (€)'), 
                                validators=[Optional(), NumberRange(min=0)],
                                places=2) 
    submit_add_cost = SubmitField(_l('Add Fixed Cost')) # Separate submit for adding costs 

class UserConsentForm(FlaskForm):
    purpose = SelectField(_l('Purpose'), validators=[DataRequired()], choices=[
        ('', _l('Select Purpose')),
        ('treatment', _l('Treatment')),
        ('data_processing', _l('Data Processing')),
        ('marketing', _l('Marketing Communications')),
        ('research', _l('Research Participation')),
        ('other', _l('Other'))
    ])
    expires_at = DateField(_l('Expiry Date'), validators=[Optional()])
    notes = TextAreaField(_l('Additional Notes'), validators=[Optional(), Length(max=500)])
    submit = SubmitField(_l('Record Consent')) 