# app/models.py
from datetime import datetime
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
    _phone = db.Column("phone", db.String(100))
    _notes = db.Column("notes", db.Text)
    
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

    consents = db.relationship('UserConsent', backref='patient', lazy=True)
    
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
    location = db.Column(db.String(100))
    visit_type = db.Column(db.String(50))
    fee_charged = db.Column(db.Float)
    payment_method = db.Column(db.String(50))
    
    # Field for Calendly integration
    calendly_invitee_uri = db.Column(db.String(255), nullable=True, index=True)
    
    trigger_points = db.relationship('TriggerPoint', backref='treatment', lazy=True)

    clinic_share = db.Column(db.Float)
    therapist_share = db.Column(db.Float)
    
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
    location = db.Column(db.String(100), nullable=True)
    provider = db.Column(db.String(100), nullable=True)
    fee_charged = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    payment_method = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = db.relationship('Patient', backref=db.backref('recurring_appointments', lazy=True))

    def __repr__(self):
        return f'<RecurringAppointment {self.id} for Patient {self.patient_id} ({self.recurrence_type})>'

# --- NEW: Model for storing practice-wide AI reports ---
class PracticeReport(db.Model):
    __tablename__ = 'practice_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    user = db.relationship('User', backref=db.backref('practice_reports', lazy=True))

    def __repr__(self):
        return f'<PracticeReport {self.id} generated at {self.generated_at.strftime("%Y-%m-%d %H:%M")}>'
# --- End NEW Model ---

# Subscription Models
class Plan(db.Model):
    __tablename__ = 'plans'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True) # e.g., "Basic", "Pro - Monthly"
    slug = db.Column(db.String(100), nullable=False, unique=True) # e.g., "basic", "pro_monthly"
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
    # Personal fields
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    sex = db.Column(db.String(16), nullable=True)  # 'Masculino', 'Femenino', 'Otro'
    license_number = db.Column(db.String(64), nullable=True)
    
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
    
    role = db.Column(db.String(20), default='physio')  # e.g., 'admin', 'physio'
    language = db.Column(db.String(5), default='en') # Add language preference field
    
    # Consent fields
    consent_given = db.Column(db.Boolean, default=False)
    consent_date = db.Column(db.DateTime, nullable=True)
    
    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False)
    
    # Special access field for unlimited access without admin privileges
    has_unlimited_access = db.Column(db.Boolean, default=False)
    
    # Specify the foreign key to resolve ambiguity
    patients = db.relationship('Patient', foreign_keys='[Patient.user_id]', backref='practitioner', lazy='dynamic')
    
    patient_record = db.relationship('Patient', backref=db.backref('portal_user_account', uselist=False), foreign_keys='[Patient.portal_user_id]', uselist=False) # Link to a Patient record if this User is a patient portal user
    unmatched_calendly_bookings = db.relationship('UnmatchedCalendlyBooking', backref='user', lazy='dynamic') # Added relationship
    
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
        if self.is_admin:
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
        # Admin users have unlimited access to all features
        if self.is_admin:
            return None
            
        plan = self.active_plan
        if not plan or not plan.features:
            return None
        
        limit = plan.features.get(feature_limit_key)
        if isinstance(limit, int):
            return limit
        return None

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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