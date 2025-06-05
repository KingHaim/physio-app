from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, PasswordField, DecimalField, SelectField
from wtforms.validators import DataRequired, Optional, Length, Email, URL, EqualTo, NumberRange

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    # For now, plan selection is handled on the backend, defaulting to 'free'
    # We could add a RadioField here later if we want users to select a plan at registration
    # plan = RadioField('Choose Your Plan', choices=[('free', 'Free Plan'), ('pro', 'Pro Plan ($19.99/month)')], default='free')
    submit = SubmitField('Register')

class ClinicForm(FlaskForm):
    name = StringField('Clinic Name', validators=[DataRequired(), Length(max=150)])
    address_line1 = StringField('Address Line 1', validators=[Optional(), Length(max=150)])
    address_line2 = StringField('Address Line 2', validators=[Optional(), Length(max=150)])
    city = StringField('City', validators=[Optional(), Length(max=100)])
    postcode = StringField('Postcode', validators=[Optional(), Length(max=20)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=30)])
    email = StringField('Clinic Email', validators=[Optional(), Email(), Length(max=120)])
    website = StringField('Website', validators=[Optional(), URL(), Length(max=120)])
    submit = SubmitField('Save Clinic Information')

# We can add other forms here later, for example, a UserProfileForm
class UserProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
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
    calendly_api_key = TextAreaField('Calendly API Key', 
                                     validators=[Optional()],
                                     render_kw={"rows": 3, "placeholder": "Paste your Calendly Personal Access Token here..."})
    submit = SubmitField('Save API Keys')

# Renamed from FixedCostForm
class FinancialSettingsForm(FlaskForm):
    # Field for setting the overall contribution base
    autonomo_contribution_base = DecimalField('Set Your Fixed Autónomo Contribution Base (€)', 
                                            validators=[Optional(), NumberRange(min=0)],
                                            places=2,
                                            description="Leave blank to use automatic calculation based on income brackets.")
    submit_base = SubmitField('Save Contribution Base') # Separate submit for this

    # Fields for adding individual fixed costs
    description = StringField('Cost Description', validators=[Optional(), Length(max=150)])
    monthly_amount = DecimalField('Monthly Amount (£)', 
                                  validators=[Optional(), NumberRange(min=0)],
                                  places=2) 
    submit_add_cost = SubmitField('Add Fixed Cost') # Separate submit for adding costs 