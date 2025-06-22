from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, PasswordField, DecimalField, SelectField, BooleanField
from wtforms.validators import DataRequired, Optional, Length, Email, URL, EqualTo, NumberRange
from wtforms.fields import DateField
from flask_babel import lazy_gettext as _l

class RegistrationForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired(), Length(min=3, max=64)])
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

class ClinicForm(FlaskForm):
    clinic_name = StringField('Clinic Name', validators=[DataRequired(), Length(max=150)])
    clinic_address = StringField('Clinic Address', validators=[Optional(), Length(max=200)])
    clinic_phone = StringField('Phone Number', validators=[Optional(), Length(max=30)])
    clinic_email = StringField('Clinic Email', validators=[Optional(), Email(), Length(max=120)])
    clinic_website = StringField('Website', validators=[Optional(), URL(), Length(max=120)])
    clinic_description = TextAreaField('Description', validators=[Optional()])
    clinic_first_session_fee = DecimalField('First Session Fee (€)', validators=[Optional(), NumberRange(min=0)], places=2)
    clinic_subsequent_session_fee = DecimalField('Subsequent Session Fee (€)', validators=[Optional(), NumberRange(min=0)], places=2)
    clinic_percentage_agreement = BooleanField('Percentage Agreement')
    clinic_percentage_amount = DecimalField('Clinic Share (%)', validators=[Optional(), NumberRange(min=0, max=100)], places=2)
    submit = SubmitField('Save Clinic Information')

# We can add other forms here later, for example, a UserProfileForm
class UserProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField('First Name', validators=[Optional(), Length(max=64)])
    last_name = StringField('Last Name', validators=[Optional(), Length(max=64)])
    date_of_birth = DateField('Date of Birth', format='%Y-%m-%d', validators=[Optional()])
    sex = SelectField('Sex', choices=[('Masculino', 'Masculino'), ('Femenino', 'Femenino'), ('Otro', 'Otro')], validators=[Optional()])
    license_number = StringField('License Number', validators=[Optional(), Length(max=32)])
    current_password = PasswordField('Current Password', validators=[Optional(), Length(min=6)])
    new_password = PasswordField('New Password', validators=[Optional(), Length(min=6)])
    confirm_new_password = PasswordField('Confirm New Password', 
                                         validators=[Optional(), EqualTo('new_password', message='New passwords must match.')])
    submit = SubmitField('Update Profile')

class UpdateEmailForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    submit_email = SubmitField('Update Email')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_new_password = PasswordField('Confirm New Password', 
                                         validators=[DataRequired(), EqualTo('new_password', message='New passwords must match.')])
    submit_password = SubmitField('Change Password')

class ApiIntegrationsForm(FlaskForm):
    # Integration checkboxes
    enable_calendly = BooleanField('Enable Calendly Integration')
    # Future integrations can be added here:
    # enable_stripe = BooleanField('Enable Stripe Integration')
    # enable_google_calendar = BooleanField('Enable Google Calendar Integration')
    # enable_zoom = BooleanField('Enable Zoom Integration')
    
    # Calendly fields (will be shown/hidden based on checkbox)
    calendly_api_key = TextAreaField('Calendly API Key', 
                                     validators=[Optional()],
                                     render_kw={"rows": 3, "placeholder": "Paste your Calendly Personal Access Token here..."})
    calendly_user_uri = StringField('Calendly User URI', 
                                   validators=[Optional(), URL()],
                                   render_kw={"placeholder": "https://api.calendly.com/users/your-user-id"})
    
    # Future API fields can be added here:
    # stripe_secret_key = StringField('Stripe Secret Key', validators=[Optional()])
    # google_calendar_credentials = TextAreaField('Google Calendar Credentials', validators=[Optional()])
    
    submit = SubmitField('Save API Keys')

# Renamed from FixedCostForm
class FinancialSettingsForm(FlaskForm):
    # Field for setting the overall contribution base
    contribution_base = DecimalField('Set Your Fixed Autónomo Contribution Base (€)', 
                                   validators=[Optional(), NumberRange(min=0)],
                                   places=2,
                                   description="Leave blank to use automatic calculation based on income brackets.")
    submit_base = SubmitField('Save Contribution Base') # Separate submit for this

    # Fields for adding individual fixed costs
    description = StringField('Cost Description', validators=[Optional(), Length(max=150)])
    monthly_amount = DecimalField('Monthly Amount (€)', 
                                validators=[Optional(), NumberRange(min=0)],
                                places=2) 
    submit_add_cost = SubmitField('Add Fixed Cost') # Separate submit for adding costs 

class UserConsentForm(FlaskForm):
    purpose = SelectField('Purpose', validators=[DataRequired()], choices=[
        ('', 'Select Purpose'),
        ('treatment', 'Treatment'),
        ('data_processing', 'Data Processing'),
        ('marketing', 'Marketing Communications'),
        ('research', 'Research Participation'),
        ('other', 'Other')
    ])
    expires_at = DateField('Expiry Date', validators=[Optional()])
    notes = TextAreaField('Additional Notes', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Record Consent') 