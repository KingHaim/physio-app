# app/models.py
from datetime import datetime, timedelta
from . import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import JSON as SQLAlchemyJSON # Using generic SQLAlchemy JSON type
from sqlalchemy import desc # Required for ordering in current_subscription query
from typing import Optional, Tuple # Import Optional and Tuple for type hinting
from .crypto_utils import encrypt_token, decrypt_token, encrypt_text, decrypt_text
from flask import current_app

class Patient(db.Model):
    __tablename__ = 'patient'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    portal_user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', use_alter=True, name='fk_portal_user_id_user'),
        nullable=True, 
        unique=True
    )
    # Encrypted sensitive fields - database columns with underscore prefix
    # Increased length to accommodate encrypted data
    _name = db.Column("name", db.String(500), nullable=False)
    _email = db.Column("email", db.String(500))
    _phone = db.Column("phone", db.String(500))
    _notes = db.Column("notes", db.Text)
    _anamnesis = db.Column("anamnesis", db.Text)  # Clinical history/initial assessment
    
    # Non-sensitive fields remain as-is
    date_of_birth = db.Column(db.Date)
    contact = db.Column(db.String(100))
    diagnosis = db.Column(db.String(200))
    treatment_plan = db.Column(db.Text)
    status = db.Column(db.String(20), default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    treatments = db.relationship('Treatment', backref='patient', lazy=True)
    
    # New fields for extended contact and address information (non-sensitive)
    address_line1 = db.Column(db.String(100))
    address_line2 = db.Column(db.String(100))
    city = db.Column(db.String(50))
    postcode = db.Column(db.String(20))
    preferred_location = db.Column(db.String(50), default='Clinic')  # Clinic or Home Visit

    # AI Analysis fields
    ai_suggested_tests = db.Column(db.Text)  # JSON string with suggested functional tests
    ai_red_flags = db.Column(db.Text)  # Critical warnings
    ai_yellow_flags = db.Column(db.Text)  # Caution indicators
    ai_clinical_notes = db.Column(db.Text)  # Additional clinical considerations
    ai_analysis_date = db.Column(db.DateTime)  # When analysis was last performed

    # Referral system fields
    referred_by_patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=True)
    _referred_by_name = db.Column("referred_by_name", db.String(500), nullable=True)  # Encrypted field for non-patient referrals
    referral_notes = db.Column(db.Text, nullable=True)  # Additional referral information

    consents = db.relationship('UserConsent', backref='patient', lazy=True)
    
    # Self-referential relationship for patient referrals
    referred_by = db.relationship('Patient', remote_side=[id], backref='referrals', foreign_keys=[referred_by_patient_id])
    # Note: 'referrals' backref gives us all patients referred by this patient
    
    # Property getters and setters for encrypted fields
    @property
    def name(self):
        """Get decrypted patient name"""
        if self._name:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                return self._name
            return decrypt_text(self._name)
        return None

    @name.setter
    def name(self, value):
        """Set encrypted patient name"""
        if value:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                self._name = value
            else:
                self._name = encrypt_text(value)
        else:
            self._name = None

    @property
    def email(self):
        """Get decrypted patient email"""
        if self._email:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                return self._email
            return decrypt_text(self._email)
        return None

    @email.setter
    def email(self, value):
        """Set encrypted patient email"""
        if value:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                self._email = value
            else:
                self._email = encrypt_text(value)
        else:
            self._email = None

    @property
    def phone(self):
        """Get decrypted patient phone"""
        if self._phone:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                return self._phone
            return decrypt_text(self._phone)
        return None

    @phone.setter
    def phone(self, value):
        """Set encrypted patient phone"""
        if value:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                self._phone = value
            else:
                self._phone = encrypt_text(value)
        else:
            self._phone = None

    @property
    def notes(self):
        """Get decrypted patient notes"""
        if self._notes:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                return self._notes
            return decrypt_text(self._notes)
        return None

    @notes.setter
    def notes(self, value):
        """Set encrypted patient notes"""
        if value:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                self._notes = value
            else:
                self._notes = encrypt_text(value)
        else:
            self._notes = None

    @property
    def anamnesis(self):
        """Get decrypted patient anamnesis (clinical history)"""
        if self._anamnesis:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                return self._anamnesis
            return decrypt_text(self._anamnesis)
        return None

    @anamnesis.setter
    def anamnesis(self, value):
        """Set encrypted patient anamnesis (clinical history)"""
        if value:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                self._anamnesis = value
            else:
                self._anamnesis = encrypt_text(value)
        else:
            self._anamnesis = None

    @property
    def referred_by_name(self):
        """Get decrypted referral source name (for non-patient referrals)"""
        if self._referred_by_name:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                return self._referred_by_name
            return decrypt_text(self._referred_by_name)
        return None

    @referred_by_name.setter
    def referred_by_name(self, value):
        """Set encrypted referral source name (for non-patient referrals)"""
        if value:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                self._referred_by_name = value
            else:
                self._referred_by_name = encrypt_text(value)
        else:
            self._referred_by_name = None

    @property
    def referral_source(self):
        """Get the referral source - either a patient name or a custom name"""
        if self.referred_by:
            return self.referred_by.name
        elif self.referred_by_name:
            return self.referred_by_name
        return None

    def get_referral_chain(self, visited=None):
        """Get the complete referral chain leading to this patient"""
        if visited is None:
            visited = set()
        
        # Prevent infinite loops
        if self.id in visited:
            return []
        
        visited.add(self.id)
        chain = [self]
        
        if self.referred_by:
            parent_chain = self.referred_by.get_referral_chain(visited.copy())
            chain = parent_chain + chain
            
        return chain

    def get_referral_tree(self, visited=None):
        """Get the complete referral tree starting from this patient"""
        if visited is None:
            visited = set()
        
        # Prevent infinite loops
        if self.id in visited:
            return {'patient': self, 'referrals': []}
        
        visited.add(self.id)
        
        tree = {
            'patient': self,
            'referrals': []
        }
        
        for referred_patient in self.referrals:
            if referred_patient.id not in visited:
                subtree = referred_patient.get_referral_tree(visited.copy())
                tree['referrals'].append(subtree)
        
        return tree


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    
    # Fee structure per location
    first_session_fee = db.Column(db.Float, nullable=True)
    subsequent_session_fee = db.Column(db.Float, nullable=True)
    fee_percentage = db.Column(db.Float, nullable=True)  # Clinic's share %
    
    # Location type
    location_type = db.Column(db.String(50), default='Clinic')  # 'Clinic', 'Home Visit', 'External'
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    treatments = db.relationship('Treatment', backref='treatment_location', lazy=True)
    recurring_appointments = db.relationship('RecurringAppointment', backref='appointment_location', lazy=True)
    
    def __repr__(self):
        return f'<Location {self.name}>'


class Treatment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    treatment_type = db.Column(db.String(100), nullable=False)
    assessment = db.Column(db.Text)
    # Encrypted sensitive field
    _notes = db.Column("notes", db.Text)
    status = db.Column(db.String(50), default='Scheduled')
    provider = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    body_chart_url = db.Column(db.String(255))
    #next_appointment = db.Column(db.Date)
    
    # New fields
    pain_level = db.Column(db.Integer)
    movement_restriction = db.Column(db.String(255))
    evaluation_data = db.Column(db.JSON)
    
    # Fields for analytics and form
    location = db.Column(db.String(100))  # Legacy field for backward compatibility
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=True)  # New structured location
    visit_type = db.Column(db.String(50))
    fee_charged = db.Column(db.Float)
    payment_method = db.Column(db.String(50))
    
    # Field for Calendly integration
    calendly_invitee_uri = db.Column(db.String(255), nullable=True, index=True)
    
    # Fields for Google Calendar integration
    google_calendar_event_id = db.Column(db.String(255), nullable=True, index=True)
    google_calendar_event_summary = db.Column(db.String(255), nullable=True)
    
    trigger_points = db.relationship('TriggerPoint', backref='treatment', lazy=True)

    clinic_share = db.Column(db.Float)
    therapist_share = db.Column(db.Float)
    
    @property
    def location_name(self):
        """Get location name, preferring the structured location over legacy string"""
        if self.treatment_location:
            return self.treatment_location.name
        return self.location
    
    # Property getter and setter for encrypted notes field
    @property
    def notes(self):
        """Get decrypted treatment notes"""
        if self._notes:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                return self._notes
            return decrypt_text(self._notes)
        return None

    @notes.setter
    def notes(self, value):
        """Set encrypted treatment notes"""
        if value:
            # Check if encryption is disabled for testing
            if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
                self._notes = value
            else:
                self._notes = encrypt_text(value)
        else:
            self._notes = None

class TriggerPoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    treatment_id = db.Column(db.Integer, db.ForeignKey('treatment.id'), nullable=False)
    location_x = db.Column(db.Float, nullable=False)
    location_y = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(50))  # 'active', 'latent', or 'satellite'
    muscle = db.Column(db.String(100))
    intensity = db.Column(db.Integer)  # 1-10 scale
    symptoms = db.Column(db.Text)
    referral_pattern = db.Column(db.Text)

class UnmatchedCalendlyBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    event_type = db.Column(db.String(100))
    start_time = db.Column(db.DateTime)
    calendly_invitee_id = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Pending')  # Pending, Matched, Ignored
    matched_patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    matched_patient = db.relationship('Patient', backref='calendly_matches')

class PatientReport(db.Model):
    __tablename__ = 'patient_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    generated_date = db.Column(db.DateTime, default=datetime.now)
    report_type = db.Column(db.String(50), default='AI Generated')
    
    patient = db.relationship('Patient', backref=db.backref('reports', lazy=True))

class RecurringAppointment(db.Model):
    __tablename__ = 'recurring_appointment'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True) # Nullable for indefinite recurrence
    recurrence_type = db.Column(db.String(50), nullable=False) # e.g., 'daily-mon-fri', 'weekly'
    time_of_day = db.Column(db.Time, nullable=False)
    treatment_type = db.Column(db.String(150), nullable=False, default='Standard Session')
    notes = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(100), nullable=True)  # Legacy field for backward compatibility
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=True)  # New structured location
    provider = db.Column(db.String(100), nullable=True)
    fee_charged = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    payment_method = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = db.relationship('Patient', backref=db.backref('recurring_appointments', lazy=True))

    @property
    def location_name(self):
        """Get location name, preferring the structured location over legacy string"""
        if self.appointment_location:
            return self.appointment_location.name
        return self.location

    def __repr__(self):
        return f'<RecurringAppointment {self.id} for Patient {self.patient_id} ({self.recurrence_type})>'

# --- NEW: Model for storing practice-wide AI reports ---
class PatientAIConversation(db.Model):
    __tablename__ = 'patient_ai_conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_type = db.Column(db.String(10), nullable=False)  # 'user' or 'ai'
    message_content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('Patient', backref=db.backref('ai_conversations', lazy=True))
    user = db.relationship('User', backref=db.backref('ai_conversations', lazy=True))
    
    def __repr__(self):
        return f'<PatientAIConversation {self.id} for Patient {self.patient_id}>'

class PracticeReport(db.Model):
    __tablename__ = 'practice_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    user = db.relationship('User', backref=db.backref('practice_reports', lazy=True))

    def __repr__(self):
        return f'<PracticeReport {self.id}>'
# --- End NEW Model ---

# Subscription Models
class Plan(db.Model):
    __tablename__ = 'plans'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True) # e.g., "Basic", "Pro - Monthly"
    slug = db.Column(db.String(100), nullable=False, unique=True) # e.g., "basic", "pro_monthly"
    plan_type = db.Column(db.String(20), nullable=False, default='individual') # 'individual' or 'clinic'
    price_cents = db.Column(db.Integer, nullable=False) # Price in cents
    billing_interval = db.Column(db.String(50), nullable=False) # 'month', 'year'
    currency = db.Column(db.String(3), nullable=False, default='eur') # e.g., 'eur', 'usd'
    patient_limit = db.Column(db.Integer, nullable=True) # Null for unlimited
    practitioner_limit = db.Column(db.Integer, nullable=True) # Null for unlimited practitioners
    features = db.Column(SQLAlchemyJSON, nullable=True) # Store list of features or key-value pairs
    stripe_price_id = db.Column(db.String(255), nullable=True, unique=True) # Stripe Price ID
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    display_order = db.Column(db.Integer, default=0) # For ordering plans on a pricing page

    subscriptions = db.relationship('UserSubscription', backref='plan', lazy='dynamic')

    def __repr__(self):
        return f'<Plan {self.name}>'

class UserSubscription(db.Model):
    __tablename__ = 'user_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    stripe_subscription_id = db.Column(db.String(255), unique=True, nullable=True, index=True) # Nullable if created before Stripe sub
    status = db.Column(db.String(50), nullable=False, default='pending') # e.g., 'trialing', 'active', 'past_due', 'canceled', 'unpaid', 'pending'
    
    trial_starts_at = db.Column(db.DateTime, nullable=True)
    trial_ends_at = db.Column(db.DateTime, nullable=True)
    
    # Trial reminder email tracking
    trial_reminder_7_days_sent = db.Column(db.Boolean, default=False)
    trial_reminder_2_days_sent = db.Column(db.Boolean, default=False)
    trial_reminder_1_day_sent = db.Column(db.Boolean, default=False)
    
    current_period_starts_at = db.Column(db.DateTime, nullable=True)
    current_period_ends_at = db.Column(db.DateTime, nullable=True) # When the subscription renews or expires
    
    cancel_at_period_end = db.Column(db.Boolean, default=False, nullable=False)
    canceled_at = db.Column(db.DateTime, nullable=True) # When the subscription was actually canceled
    ended_at = db.Column(db.DateTime, nullable=True) # If the subscription fully ended (e.g. after cancellation period)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<UserSubscription {self.id} - User {self.user_id} - Plan {self.plan_id} - Status {self.status}>'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=True) # No longer unique or indexed
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Email verification fields
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verification_token = db.Column(db.String(255), nullable=True, index=True)
    email_verification_sent_at = db.Column(db.DateTime, nullable=True)
    
    # Personal fields
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    sex = db.Column(db.String(16), nullable=True)  # 'Masculino', 'Femenino', 'Otro'
    license_number = db.Column(db.String(64), nullable=True)
    college_acronym = db.Column(db.String(10), nullable=True)  # e.g. COFIB, ICOFCV, COFM
    
    # Clinic fields
    clinic_name = db.Column(db.String(150), nullable=True)
    clinic_address = db.Column(db.String(200), nullable=True)
    clinic_phone = db.Column(db.String(30), nullable=True)
    clinic_email = db.Column(db.String(120), nullable=True)
    clinic_website = db.Column(db.String(120), nullable=True)
    clinic_description = db.Column(db.Text, nullable=True)

    # Financial fields
    contribution_base = db.Column(db.Float, nullable=True)
    clinic_first_session_fee = db.Column(db.Float, nullable=True)
    clinic_subsequent_session_fee = db.Column(db.Float, nullable=True)
    clinic_percentage_agreement = db.Column(db.Boolean, default=False)
    clinic_percentage_amount = db.Column(db.Float, nullable=True)
    
    # Fiscal configuration fields
    tax_year = db.Column(db.Integer, default=2025)
    tax_brackets = db.Column(SQLAlchemyJSON, nullable=True)  # Store tax brackets as JSON
    autonomo_contribution_rate = db.Column(db.Float, default=0.314)
    tax_rate = db.Column(db.Float, default=0.19)
    clinic_fee_rate = db.Column(db.Float, default=0.30)
    currency_symbol = db.Column(db.String(5), default='€')
    revenue_currency_symbol = db.Column(db.String(5), default='£')
    
    # Stripe Customer ID
    stripe_customer_id = db.Column(db.String(255), nullable=True, unique=True, index=True)
    
    # Calendly specific fields
    calendly_api_key = db.Column(db.String(255), nullable=True)  # Legacy field - will be deprecated
    calendly_api_token_encrypted = db.Column(db.Text, nullable=True)  # New encrypted field
    calendly_user_uri = db.Column(db.String(255), nullable=True)
    calendly_enabled = db.Column(db.Boolean, default=False)  # Whether Calendly integration is enabled
    
    # Google Calendar specific fields
    google_calendar_token_encrypted = db.Column(db.Text, nullable=True)  # OAuth2 access token
    google_calendar_refresh_token_encrypted = db.Column(db.Text, nullable=True)  # OAuth2 refresh token
    google_calendar_enabled = db.Column(db.Boolean, default=False)
    google_calendar_primary_calendar_id = db.Column(db.String(255), nullable=True)  # Usually 'primary'
    google_calendar_last_sync = db.Column(db.DateTime, nullable=True)
    
    # User's own Google Calendar app credentials (for SaaS multi-tenant)
    google_calendar_client_id = db.Column(db.Text, nullable=True)  # User's own Client ID
    google_calendar_client_secret_encrypted = db.Column(db.Text, nullable=True)  # User's own Client Secret (encrypted)
    google_calendar_redirect_uri = db.Column(db.String(500), nullable=True)  # User's own redirect URI
    
    role = db.Column(db.String(20), default='physio')  # e.g., 'admin', 'physio'
    language = db.Column(db.String(5), default='en') # Add language preference field
    
    # Consent fields
    consent_given = db.Column(db.Boolean, default=False)
    consent_date = db.Column(db.DateTime, nullable=True)
    
    # OAuth fields
    oauth_provider = db.Column(db.String(50), nullable=True)  # 'google', 'facebook', etc.
    oauth_id = db.Column(db.String(255), nullable=True, index=True)  # OAuth provider's user ID
    avatar_url = db.Column(db.String(255), nullable=True)  # Profile picture URL
    
    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False)
    
    # Special access field for unlimited access without admin privileges
    has_unlimited_access = db.Column(db.Boolean, default=False)
    
    # Welcome flow field
    is_new_user = db.Column(db.Boolean, default=True)
    

    
    # Specify the foreign key to resolve ambiguity
    patients = db.relationship('Patient', foreign_keys='[Patient.user_id]', backref='practitioner', lazy='dynamic')
    
    patient_record = db.relationship('Patient', backref=db.backref('portal_user_account', uselist=False), foreign_keys='[Patient.portal_user_id]', uselist=False) # Link to a Patient record if this User is a patient portal user
    unmatched_calendly_bookings = db.relationship('UnmatchedCalendlyBooking', backref='user', lazy='dynamic') # Added relationship
    
    # Location management
    locations = db.relationship('Location', backref='user', lazy='dynamic')
    
    # Subscription relationship
    subscriptions = db.relationship('UserSubscription', backref='user', lazy='dynamic', order_by=UserSubscription.created_at.desc())

    data_processing_activities = db.relationship('DataProcessingActivity', backref='user', lazy=True)
    security_logs = db.relationship('SecurityLog', backref='user', lazy=True)

    @property
    def calendly_api_token(self):
        """
        Get the decrypted Calendly API token.
        First tries the new encrypted field, then falls back to the legacy field.
        """
        # Try the new encrypted field first
        if self.calendly_api_token_encrypted:
            decrypted = decrypt_token(self.calendly_api_token_encrypted)
            if decrypted:
                return decrypted
        
        # Fall back to legacy field (for backward compatibility)
        return self.calendly_api_key
    
    @calendly_api_token.setter
    def calendly_api_token(self, value):
        """
        Set the Calendly API token by encrypting it and storing in the new field.
        Also clears the legacy field for security.
        """
        if value:
            encrypted = encrypt_token(value)
            if encrypted:
                self.calendly_api_token_encrypted = encrypted
                # Clear the legacy field for security
                self.calendly_api_key = None
            else:
                # If encryption fails, fall back to legacy field (not recommended)
                self.calendly_api_key = value
                self.calendly_api_token_encrypted = None
        else:
            # Clear both fields
            self.calendly_api_token_encrypted = None
            self.calendly_api_key = None

    @property
    def calendly_configured_and_enabled(self):
        """Check if Calendly is both configured (has credentials) and enabled by user."""
        return (self.calendly_enabled and 
                self.calendly_api_token is not None and 
                self.calendly_user_uri is not None)
    
    @property
    def calendly_configured(self):
        """Check if Calendly has valid credentials (regardless of enabled status)."""
        return (self.calendly_api_token is not None and 
                self.calendly_user_uri is not None)

    @property
    def google_calendar_token(self):
        """Get the decrypted Google Calendar access token."""
        if self.google_calendar_token_encrypted:
            decrypted = decrypt_token(self.google_calendar_token_encrypted)
            if decrypted:
                return decrypted
        return None
    
    @google_calendar_token.setter
    def google_calendar_token(self, value):
        """Set the Google Calendar access token by encrypting it."""
        if value:
            encrypted = encrypt_token(value)
            if encrypted:
                self.google_calendar_token_encrypted = encrypted
            else:
                self.google_calendar_token_encrypted = None
        else:
            self.google_calendar_token_encrypted = None

    @property
    def google_calendar_refresh_token(self):
        """Get the decrypted Google Calendar refresh token."""
        if self.google_calendar_refresh_token_encrypted:
            decrypted = decrypt_token(self.google_calendar_refresh_token_encrypted)
            if decrypted:
                return decrypted
        return None
    
    @google_calendar_refresh_token.setter
    def google_calendar_refresh_token(self, value):
        """Set the Google Calendar refresh token by encrypting it."""
        if value:
            encrypted = encrypt_token(value)
            if encrypted:
                self.google_calendar_refresh_token_encrypted = encrypted
            else:
                self.google_calendar_refresh_token_encrypted = None
        else:
            self.google_calendar_refresh_token_encrypted = None

    @property
    def google_calendar_client_secret(self):
        """Get decrypted Google Calendar client secret."""
        if self.google_calendar_client_secret_encrypted:
            decrypted = decrypt_token(self.google_calendar_client_secret_encrypted)
            if decrypted:
                return decrypted
        return None
    
    @google_calendar_client_secret.setter
    def google_calendar_client_secret(self, value):
        """Set encrypted Google Calendar client secret."""
        if value:
            encrypted = encrypt_token(value)
            if encrypted:
                self.google_calendar_client_secret_encrypted = encrypted
            else:
                self.google_calendar_client_secret_encrypted = None
        else:
            self.google_calendar_client_secret_encrypted = None

    @property
    def google_calendar_app_configured(self):
        """Check if user has configured their own Google Calendar app credentials."""
        return (self.google_calendar_client_id is not None and 
                self.google_calendar_client_secret is not None)

    @property
    def google_calendar_configured(self):
        """Check if Google Calendar is properly configured (app + OAuth tokens)."""
        return (self.google_calendar_enabled and 
                self.google_calendar_app_configured and
                self.google_calendar_token is not None and 
                self.google_calendar_refresh_token is not None)

    @property
    def patient_usage_details(self) -> Tuple[int, Optional[int]]:
        """Returns (current_patient_count, patient_limit_for_plan)."""
        # Ensure Patient model is accessible here, it should be as it's defined in the same file.
        current_patient_count = Patient.query.filter_by(user_id=self.id).count()
        
        # Admin users and users with unlimited access have unlimited access
        if self.is_admin or self.has_unlimited_access:
            return current_patient_count, None
            
        limit = 10  # Default Free Plan limit of 10 patients
        plan = self.active_plan
        if plan:
            limit = plan.patient_limit
        return current_patient_count, limit

    @property
    def current_subscription(self) -> Optional['UserSubscription']: # Forward reference if UserSubscription is defined later
        """Returns the user's current active or trialing subscription."""
        return UserSubscription.query.filter(
            UserSubscription.user_id == self.id,
            UserSubscription.status.in_(['active', 'trialing']),
            UserSubscription.ended_at.is_(None),
        ).order_by(desc(UserSubscription.created_at)).first()

    @property
    def is_subscribed(self) -> bool:
        """Checks if the user has an active or trialing subscription."""
        sub = self.current_subscription
        if not sub:
            return False
        
        if sub.status == 'trialing':
            if sub.trial_ends_at and sub.trial_ends_at < datetime.utcnow():
                return False
        
        return sub.status in ['active', 'trialing']

    @property
    def is_on_trial(self) -> bool:
        """Checks if the user is on an active trial."""
        sub = self.current_subscription
        if sub and sub.status == 'trialing' and sub.trial_ends_at and sub.trial_ends_at >= datetime.utcnow():
            return True
        return False

    @property
    def trial_days_remaining(self) -> int:
        """Returns the number of days remaining in the trial period."""
        if not self.is_on_trial:
            return 0
        
        sub = self.current_subscription
        if sub and sub.trial_ends_at:
            remaining = sub.trial_ends_at - datetime.utcnow()
            return max(0, remaining.days)
        return 0

    @property
    def active_plan(self) -> Optional['Plan']: # Forward reference for Plan
        """Returns the Plan object for the current active subscription."""
        sub = self.current_subscription
        if sub and sub.plan: 
            return sub.plan
        return None

    @property
    def subscription_status(self) -> Optional[str]:
        """Returns the status of the current active subscription."""
        sub = self.current_subscription
        return sub.status if sub else None

    def can_use_feature(self, feature_key: str, default_if_no_sub: bool = False) -> bool:
        """
        Checks if the user's current plan allows a specific feature.
        `feature_key` should correspond to a key in the Plan's `features` JSON.
        `default_if_no_sub` is the value returned if the user has no active subscription.
        """
        if self.is_admin or self.has_unlimited_access:
            return True

        # Trial users get FULL ACCESS to ALL premium features during trial
        if self.is_on_trial:
            # During trial, users get access to all premium features
            # This includes advanced features like AI insights, advanced reporting, etc.
            return True

        plan = self.active_plan
        if not plan:
            return default_if_no_sub

        if not plan.features: 
            return False 
            
        if isinstance(plan.features.get(feature_key), bool):
            return plan.features.get(feature_key, False)

        return feature_key in plan.features

    def has_reached_patient_limit(self) -> bool:
        """Checks if the user has reached their patient limit based on their plan."""
        if self.is_admin or self.has_unlimited_access:
            return False

        plan = self.active_plan
        patient_limit = 10  # Default Free Plan limit of 10 patients
        
        if plan and plan.patient_limit is not None:
            patient_limit = plan.patient_limit
        elif plan and plan.patient_limit is None:
            # Unlimited plan (Premium)
            return False
        
        # Ensure Patient model is accessible here
        current_patient_count = Patient.query.filter_by(user_id=self.id).count()
        return current_patient_count >= patient_limit

    def get_feature_limit(self, feature_limit_key: str) -> Optional[int]:
        """
        Gets a specific numeric limit for a feature from the user's plan.
        Example: `user.get_feature_limit('ai_reports_limit')`
        Returns None if no limit is set or no active plan.
        """
        # Admin users and VIP unlimited users have unlimited access to all features
        if self.is_admin or self.has_unlimited_access:
            return None
        
        # Trial users get UNLIMITED access to all features during trial
        if self.is_on_trial:
            return None
            
        plan = self.active_plan
        if not plan or not plan.features:
            return None
        
        limit = plan.features.get(feature_limit_key)
        if isinstance(limit, int):
            return limit
        return None

    # --- Clinic-related methods ---
    
    @property
    def active_clinic_membership(self) -> Optional['ClinicMembership']:
        """Get the user's active clinic membership"""
        from sqlalchemy import and_
        return db.session.query(ClinicMembership).filter(
            and_(
                ClinicMembership.user_id == self.id,
                ClinicMembership.is_active == True
            )
        ).first()
    
    @property
    def clinic(self) -> Optional['Clinic']:
        """Get the clinic this user belongs to"""
        membership = self.active_clinic_membership
        return membership.clinic if membership else None
    
    @property
    def clinic_role(self) -> Optional[str]:
        """Get the user's role in their clinic"""
        membership = self.active_clinic_membership
        return membership.role if membership else None
    
    @property
    def is_clinic_admin(self) -> bool:
        """Check if user is a clinic admin"""
        membership = self.active_clinic_membership
        return membership.is_admin() if membership else False
    
    @property
    def is_clinic_practitioner(self) -> bool:
        """Check if user is a clinic practitioner (includes admin)"""
        membership = self.active_clinic_membership
        return membership.is_practitioner() if membership else False
    
    @property
    def is_in_clinic(self) -> bool:
        """Check if user is part of a clinic"""
        return self.active_clinic_membership is not None
    
    def can_manage_clinic_patients(self) -> bool:
        """Check if user can manage patients in their clinic"""
        membership = self.active_clinic_membership
        return membership.can_manage_patients if membership else False
    
    def can_manage_clinic_practitioners(self) -> bool:
        """Check if user can manage practitioners in their clinic"""
        membership = self.active_clinic_membership
        return membership.can_manage_practitioners if membership else False
    
    def can_manage_clinic_billing(self) -> bool:
        """Check if user can manage billing in their clinic"""
        membership = self.active_clinic_membership
        return membership.can_manage_billing if membership else False
    
    def can_view_clinic_reports(self) -> bool:
        """Check if user can view clinic reports"""
        membership = self.active_clinic_membership
        return membership.can_view_reports if membership else False
    
    def can_manage_clinic_settings(self) -> bool:
        """Check if user can manage clinic settings"""
        membership = self.active_clinic_membership
        return membership.can_manage_settings if membership else False
    
    def get_accessible_patients(self, include_clinic_patients=False):
        """Get all patients accessible to this user
        
        Args:
            include_clinic_patients (bool): If True, include patients from other clinic members
                                          If False, only return own patients (default for privacy)
        
        SECURITY: Admins follow the same access rules as other users.
        No user should have blanket access to all patient data.
        """
        # SECURITY FIX: Removed admin bypass - admins follow same rules as other users
        if include_clinic_patients and self.is_in_clinic and self.can_manage_clinic_patients():
            # Get all patients from clinic members (only when explicitly requested)
            clinic = self.clinic
            if clinic:
                clinic_user_ids = [m.user_id for m in clinic.active_members]
                return Patient.query.filter(Patient.user_id.in_(clinic_user_ids)).all()
        
        # Default: only own patients (safer for privacy)
        return self.patients.all()
    
    def get_effective_patient_limit(self) -> Optional[int]:
        """Get the effective patient limit (clinic-level if in clinic, otherwise individual)"""
        if self.is_admin or self.has_unlimited_access:
            return None
        
        if self.is_in_clinic:
            clinic = self.clinic
            if clinic and clinic.active_plan:
                return clinic.active_plan.patient_limit
        
        # Individual plan
        plan = self.active_plan
        if plan:
            return plan.patient_limit
        
        return 10  # Default free plan limit
    
    def get_effective_plan(self) -> Optional['Plan']:
        """Get the effective plan (clinic plan if in clinic, otherwise individual plan)"""
        if self.is_in_clinic:
            clinic = self.clinic
            if clinic:
                return clinic.active_plan
        
        return self.active_plan
    
    def has_reached_effective_patient_limit(self) -> bool:
        """Check if effective patient limit has been reached"""
        if self.is_admin or self.has_unlimited_access:
            return False
        
        limit = self.get_effective_patient_limit()
        if limit is None:
            return False
        
        if self.is_in_clinic:
            clinic = self.clinic
            if clinic:
                return clinic.patient_count >= limit
        
        # Individual limit
        current_patient_count = self.patients.count()
        return current_patient_count >= limit
    
    def can_add_patient(self) -> bool:
        """Check if user can add a new patient"""
        # Check if they have permission to manage patients
        if not (self.is_admin or self.can_manage_clinic_patients() or not self.is_in_clinic):
            return False
        
        # Check patient limit
        return not self.has_reached_effective_patient_limit()
    
    def can_use_clinic_feature(self, feature_key: str) -> bool:
        """Check if user can use a feature based on clinic or individual plan"""
        if self.is_admin or self.has_unlimited_access:
            return True
        
        # Trial users get FULL ACCESS to ALL premium features during trial
        if self.is_on_trial:
            return True
        
        plan = self.get_effective_plan()
        if not plan or not plan.features:
            return False
        
        if isinstance(plan.features.get(feature_key), bool):
            return plan.features.get(feature_key, False)
        
        return feature_key in plan.features
    
    # --- End clinic-related methods ---
    
    def get_preferred_dashboard_route(self) -> str:
        """Get the route name for the user's preferred dashboard"""
        # Clinic members always go to clinic dashboard
        if self.is_in_clinic:
            return 'clinic.dashboard'
        
        # Individual users always go to main dashboard
        return 'main.index'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_email_verification_token(self):
        """Generate a unique email verification token"""
        import secrets
        import hashlib
        
        # Generate a secure random token
        token = secrets.token_urlsafe(32)
        # Hash it for additional security
        hashed_token = hashlib.sha256(token.encode()).hexdigest()
        
        self.email_verification_token = hashed_token
        self.email_verification_sent_at = datetime.utcnow()
        
        return token  # Return the original token for the email link
    
    def verify_email_token(self, token):
        """Verify the email verification token and mark email as verified"""
        import hashlib
        
        if not self.email_verification_token:
            return False
            
        # Check if token has expired (24 hours)
        if self.email_verification_sent_at:
            expiry_time = self.email_verification_sent_at + timedelta(hours=24)
            if datetime.utcnow() > expiry_time:
                return False
        
        # Hash the provided token and compare
        hashed_token = hashlib.sha256(token.encode()).hexdigest()
        
        if hashed_token == self.email_verification_token:
            self.email_verified = True
            self.email_verification_token = None  # Clear the token
            self.email_verification_sent_at = None
            return True
            
        return False

    def get_practitioner_color(self) -> str:
        """Get a unique color for this practitioner based on their ID"""
        # Define a set of distinct colors for practitioners
        colors = [
            '#3498db',  # Blue
            '#e74c3c',  # Red
            '#2ecc71',  # Green
            '#f39c12',  # Orange
            '#9b59b6',  # Purple
            '#1abc9c',  # Turquoise
            '#34495e',  # Dark Blue Gray
            '#e67e22',  # Carrot Orange
            '#16a085',  # Dark Turquoise
            '#27ae60',  # Dark Green
            '#8e44ad',  # Dark Purple
            '#2c3e50',  # Dark Blue
            '#f1c40f',  # Yellow
            '#d35400',  # Pumpkin
            '#c0392b',  # Dark Red
        ]
        
        # Use user ID to consistently assign the same color to the same practitioner
        color_index = (self.id - 1) % len(colors)
        return colors[color_index]

    def get_clinic_practitioner_colors(self) -> dict:
        """Get a mapping of practitioner IDs to their colors within the clinic"""
        if not self.is_in_clinic:
            return {}
        
        clinic = self.clinic
        practitioners = clinic.practitioners.all()
        
        color_mapping = {}
        for membership in practitioners:
            if membership.user:
                color_mapping[membership.user.id] = membership.user.get_practitioner_color()
        
        return color_mapping

    @staticmethod
    def create_trial_subscription(user, plan_slug='basic-usd', trial_days=14):
        """
        Create a trial subscription for a user
        
        Args:
            user: User object
            plan_slug: Plan slug to create trial for (default: 'basic-usd')
            trial_days: Number of trial days (default: 14)
            
        Returns:
            UserSubscription object or None if failed
        """
        from datetime import datetime, timedelta
        
        # Get the plan
        plan = Plan.query.filter_by(slug=plan_slug, is_active=True).first()
        if not plan:
            # Fallback to first available plan
            plan = Plan.query.filter_by(is_active=True).first()
            
        if not plan:
            return None
            
        # Check if user already has an active or trialing subscription
        existing_subscription = UserSubscription.query.filter(
            UserSubscription.user_id == user.id,
            UserSubscription.status.in_(['active', 'trialing']),
            UserSubscription.ended_at.is_(None)
        ).first()
        
        if existing_subscription:
            return existing_subscription
            
        # Create trial subscription
        trial_start = datetime.utcnow()
        trial_end = trial_start + timedelta(days=trial_days)
        
        trial_subscription = UserSubscription(
            user_id=user.id,
            plan_id=plan.id,
            status='trialing',
            trial_starts_at=trial_start,
            trial_ends_at=trial_end,
            current_period_starts_at=trial_start,
            current_period_ends_at=trial_end
        )
        
        db.session.add(trial_subscription)
        
        try:
            db.session.commit()
            return trial_subscription
        except Exception:
            db.session.rollback()
            return None

class FixedCost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    description = db.Column(db.String(150), nullable=False)
    monthly_amount = db.Column(db.Float, nullable=False)
    user = db.relationship('User', backref=db.backref('fixed_costs', lazy=True))

class DataProcessingActivity(db.Model):
    __tablename__ = 'data_processing_activity'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # e.g., 'patient_registration', 'treatment_record'
    data_categories = db.Column(db.String(200), nullable=False)  # e.g., 'personal_data,health_data'
    purpose = db.Column(db.String(200), nullable=False)
    retention_period = db.Column(db.Integer, nullable=False)  # in months
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserConsent(db.Model):
    __tablename__ = 'user_consent'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    purpose = db.Column(db.String(50), nullable=False)
    given_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('consents', lazy=True))

class SecurityLog(db.Model):
    __tablename__ = 'security_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    event_type = db.Column(db.String(50), nullable=False)  # e.g., 'login', 'data_access', 'data_modification'
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(200), nullable=True)
    details = db.Column(db.Text, nullable=True)
    success = db.Column(db.Boolean, default=True)  # Added for operation success/failure
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SecurityBreach(db.Model):
    __tablename__ = 'security_breach'
    
    id = db.Column(db.Integer, primary_key=True)
    breach_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    affected_users = db.Column(db.Integer, nullable=False)
    detected_at = db.Column(db.DateTime, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_details = db.Column(db.Text, nullable=True)
    notification_sent = db.Column(db.Boolean, default=False)
    notification_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# --- Clinic Models ---

class Clinic(db.Model):
    """Clinic organization model for multi-practitioner support"""
    __tablename__ = 'clinics'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Contact information
    address = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    website = db.Column(db.String(120), nullable=True)
    
    # Financial settings
    clinic_first_session_fee = db.Column(db.Float, nullable=True)
    clinic_subsequent_session_fee = db.Column(db.Float, nullable=True)
    clinic_percentage_agreement = db.Column(db.Boolean, default=False)
    clinic_percentage_amount = db.Column(db.Float, nullable=True)
    
    # Clinic settings
    timezone = db.Column(db.String(50), default='Europe/Madrid')
    default_language = db.Column(db.String(5), default='en')
    
    # Subscription and billing
    stripe_customer_id = db.Column(db.String(255), nullable=True, unique=True, index=True)
    
    # Status and metadata
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    memberships = db.relationship('ClinicMembership', backref='clinic', lazy='dynamic', cascade='all, delete-orphan')
    subscriptions = db.relationship('ClinicSubscription', backref='clinic', lazy='dynamic', order_by='ClinicSubscription.created_at.desc()')
    
    @property
    def owner(self):
        """Get the clinic owner (admin)"""
        return self.memberships.filter_by(role='admin', is_active=True).first()
    
    @property
    def active_members(self):
        """Get all active clinic members"""
        return self.memberships.filter_by(is_active=True)
    
    @property
    def practitioners(self):
        """Get all active practitioners in the clinic"""
        return self.memberships.filter(ClinicMembership.role.in_(['admin', 'practitioner']), ClinicMembership.is_active == True)
    
    @property
    def patient_count(self):
        """Get total number of patients in the clinic"""
        from sqlalchemy import func
        return db.session.query(func.count(Patient.id)).join(
            User, Patient.user_id == User.id
        ).join(
            ClinicMembership, User.id == ClinicMembership.user_id
        ).filter(
            ClinicMembership.clinic_id == self.id,
            ClinicMembership.is_active == True
        ).scalar() or 0
    
    @property
    def current_subscription(self) -> Optional['ClinicSubscription']:
        """Returns the clinic's current active subscription"""
        return self.subscriptions.filter(
            ClinicSubscription.status.in_(['active', 'trialing']),
            ClinicSubscription.ended_at.is_(None)
        ).first()
    
    @property
    def active_plan(self) -> Optional['Plan']:
        """Returns the Plan object for the current active subscription"""
        sub = self.current_subscription
        return sub.plan if sub else None
    
    def has_reached_patient_limit(self) -> bool:
        """Check if clinic has reached patient limit"""
        plan = self.active_plan
        if not plan or plan.patient_limit is None:
            return False
        return self.patient_count >= plan.patient_limit
    
    def has_reached_practitioner_limit(self) -> bool:
        """Check if clinic has reached practitioner limit"""
        plan = self.active_plan
        if not plan or plan.practitioner_limit is None:
            return False
        return self.practitioners.count() >= plan.practitioner_limit
    
    def can_add_practitioner(self) -> bool:
        """Check if clinic can add another practitioner"""
        return not self.has_reached_practitioner_limit()
    
    def can_add_patient(self) -> bool:
        """Check if clinic can add another patient"""
        return not self.has_reached_patient_limit()
    
    def __repr__(self):
        return f'<Clinic {self.name}>'


class ClinicMembership(db.Model):
    """Association table for users and clinics with roles"""
    __tablename__ = 'clinic_memberships'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinics.id'), nullable=False, index=True)
    
    # Role in the clinic
    role = db.Column(db.String(20), nullable=False, default='practitioner')  # 'admin', 'practitioner', 'assistant'
    
    # Permissions
    can_manage_patients = db.Column(db.Boolean, default=True)
    can_manage_practitioners = db.Column(db.Boolean, default=False)
    can_manage_billing = db.Column(db.Boolean, default=False)
    can_view_reports = db.Column(db.Boolean, default=True)
    can_manage_settings = db.Column(db.Boolean, default=False)
    
    # Status and metadata
    is_active = db.Column(db.Boolean, default=True)
    invited_at = db.Column(db.DateTime, default=datetime.utcnow)
    joined_at = db.Column(db.DateTime, nullable=True)
    left_at = db.Column(db.DateTime, nullable=True)
    
    # Invitation details
    invitation_token = db.Column(db.String(255), nullable=True, unique=True)
    invitation_expires_at = db.Column(db.DateTime, nullable=True)
    invited_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    invited_email = db.Column(db.String(120), nullable=True)  # Store email for invitations to non-users
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='clinic_memberships')
    invited_by = db.relationship('User', foreign_keys=[invited_by_user_id])
    
    # Unique constraint to prevent duplicate memberships (only for active users, not pending invitations)
    __table_args__ = (
        db.Index('idx_user_clinic_active', 'user_id', 'clinic_id', postgresql_where=db.text('user_id IS NOT NULL')),
    )
    
    def set_permissions_by_role(self):
        """Set default permissions based on role"""
        if self.role == 'admin':
            self.can_manage_patients = True
            self.can_manage_practitioners = True
            self.can_manage_billing = True
            self.can_view_reports = True
            self.can_manage_settings = True
        elif self.role == 'practitioner':
            self.can_manage_patients = True
            self.can_manage_practitioners = False
            self.can_manage_billing = False
            self.can_view_reports = False  # Changed: No analytics access by default
            self.can_manage_settings = False
        elif self.role == 'assistant':
            self.can_manage_patients = False
            self.can_manage_practitioners = False
            self.can_manage_billing = False
            self.can_view_reports = False
            self.can_manage_settings = False
    
    def is_admin(self) -> bool:
        """Check if user is clinic admin"""
        return self.role == 'admin' and self.is_active
    
    def is_practitioner(self) -> bool:
        """Check if user is practitioner or admin"""
        return self.role in ['admin', 'practitioner'] and self.is_active
    
    def __repr__(self):
        return f'<ClinicMembership {self.user_id} - {self.clinic_id} ({self.role})>'


class ClinicSubscription(db.Model):
    """Subscription model for clinic-level subscriptions"""
    __tablename__ = 'clinic_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinics.id'), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    
    # Stripe integration
    stripe_subscription_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    status = db.Column(db.String(50), nullable=False, default='pending')  # 'trialing', 'active', 'past_due', 'canceled', 'unpaid', 'pending'
    
    # Subscription periods
    trial_starts_at = db.Column(db.DateTime, nullable=True)
    trial_ends_at = db.Column(db.DateTime, nullable=True)
    current_period_starts_at = db.Column(db.DateTime, nullable=True)
    current_period_ends_at = db.Column(db.DateTime, nullable=True)
    
    # Cancellation
    cancel_at_period_end = db.Column(db.Boolean, default=False, nullable=False)
    canceled_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    plan = db.relationship('Plan', backref='clinic_subscriptions')
    
    def __repr__(self):
        return f'<ClinicSubscription {self.id} - Clinic {self.clinic_id} - Plan {self.plan_id} - Status {self.status}>'

# --- End Clinic Models ---

    def emergency_technical_access_patients(self, reason: str, requesting_system: str = None):
        """
        EMERGENCY TECHNICAL ACCESS ONLY
        
        This method should ONLY be used for legitimate technical emergencies
        such as data corruption, system migration, or critical bug fixes.
        
        ALL ACCESS IS LOGGED AND AUDITABLE.
        
        Args:
            reason (str): Detailed reason for emergency access (required)
            requesting_system (str): System or process requesting access
            
        Returns:
            List of patients if admin, empty list otherwise
            
        Security Notes:
        - Only available to verified system administrators
        - All access is logged with timestamps, user, and reason
        - Should be used sparingly and only for technical purposes
        - Regular patient access should use get_accessible_patients()
        """
        import logging
        from datetime import datetime
        
        # Only actual system administrators can use this
        if not self.is_admin:
            logging.warning(f"Non-admin user {self.email} attempted emergency technical access")
            return []
        
        # Log the emergency access attempt
        log_message = (
            f"EMERGENCY TECHNICAL ACCESS: Admin {self.email} (ID: {self.id}) "
            f"accessed all patients. Reason: {reason}. "
            f"Requesting system: {requesting_system or 'Manual'}. "
            f"Timestamp: {datetime.utcnow().isoformat()}"
        )
        
        # Log to both application log and security log
        logging.critical(log_message)
        
        # Also try to log to security breach system if available
        try:
            from app.models import SecurityLog
            security_log = SecurityLog(
                user_id=self.id,
                action="EMERGENCY_PATIENT_ACCESS",
                details=f"Reason: {reason}. System: {requesting_system or 'Manual'}",
                ip_address=None,  # Would need to be passed from request context
                timestamp=datetime.utcnow()
            )
            from app import db
            db.session.add(security_log)
            db.session.commit()
        except Exception as e:
            logging.error(f"Failed to log emergency access to security log: {e}")
        
        # Print to console for immediate visibility
        print(f"🚨 EMERGENCY TECHNICAL ACCESS ALERT: {log_message}")
        
        # Return all patients - but this should be used very rarely
        return Patient.query.all()