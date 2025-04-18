# app/models.py
from datetime import datetime
from . import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Patient(db.Model):
    __tablename__ = 'patient'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date)
    contact = db.Column(db.String(100))
    diagnosis = db.Column(db.String(200))
    treatment_plan = db.Column(db.Text)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    treatments = db.relationship('Treatment', backref='patient', lazy=True)
    user = db.relationship('User', backref=db.backref('patient', uselist=False), lazy=True)

class Treatment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    treatment_type = db.Column(db.String(100), nullable=False)
    assessment = db.Column(db.Text)
    notes = db.Column(db.Text)
    status = db.Column(db.String(50), default='Scheduled')
    provider = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    body_chart_url = db.Column(db.String(255))
    #next_appointment = db.Column(db.Date)
    
    # New fields
    pain_level = db.Column(db.Integer)
    movement_restriction = db.Column(db.String(50))
    evaluation_data = db.Column(db.JSON)
    
    # Fields for analytics and form
    location = db.Column(db.String(100))
    visit_type = db.Column(db.String(50))
    fee_charged = db.Column(db.Float)
    payment_method = db.Column(db.String(50))
    
    trigger_points = db.relationship('TriggerPoint', backref='treatment', lazy=True)

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

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # --- Re-applying fields for Patient Portal ---
    role = db.Column(db.String(20), nullable=False, default='physio')
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=True)
    # --- End re-applied fields ---
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)