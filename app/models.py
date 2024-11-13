# app/models.py
from datetime import datetime
from . import db

class Patient(db.Model):
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

class Treatment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    description = db.Column(db.Text, nullable=False)
    progress_notes = db.Column(db.Text)
    next_appointment = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='Scheduled')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # New fields
    pain_level = db.Column(db.Integer)
    movement_restriction = db.Column(db.String(50))
    evaluation_data = db.Column(db.JSON)
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