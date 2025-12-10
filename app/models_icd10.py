# app/models_icd10.py
# ICD-10 Diagnosis Coding System Models

from datetime import datetime
from . import db
from sqlalchemy import Index

class ICD10Code(db.Model):
    """
    ICD-10 diagnosis codes database
    Focus on musculoskeletal and physiotherapy-relevant conditions
    """
    __tablename__ = 'icd10_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False, index=True)  # e.g., "M54.5"
    description = db.Column(db.String(500), nullable=False)  # Full description
    short_description = db.Column(db.String(200))  # Abbreviated description
    category = db.Column(db.String(100))  # e.g., "Musculoskeletal", "Neurological"
    subcategory = db.Column(db.String(100))  # e.g., "Back pain", "Neck disorders"
    is_active = db.Column(db.Boolean, default=True)
    is_physiotherapy_relevant = db.Column(db.Boolean, default=True)
    
    # Relationships
    patient_diagnoses = db.relationship('PatientDiagnosis', backref='icd10_code', lazy=True)
    
    # Search optimization
    __table_args__ = (
        Index('idx_icd10_search', 'code', 'description'),
        Index('idx_icd10_category', 'category', 'subcategory'),
    )
    
    def __repr__(self):
        return f'<ICD10Code {self.code}: {self.short_description}>'
    
    @classmethod
    def search(cls, query, limit=20):
        """Search ICD-10 codes by code or description"""
        search_term = f"%{query}%"
        return cls.query.filter(
            db.or_(
                cls.code.ilike(search_term),
                cls.description.ilike(search_term),
                cls.short_description.ilike(search_term)
            ),
            cls.is_active == True,
            cls.is_physiotherapy_relevant == True
        ).limit(limit).all()
    
    @classmethod
    def get_by_category(cls, category):
        """Get codes by category"""
        return cls.query.filter(
            cls.category == category,
            cls.is_active == True,
            cls.is_physiotherapy_relevant == True
        ).order_by(cls.code).all()


class PatientDiagnosis(db.Model):
    """
    Patient diagnosis records with ICD-10 coding
    Supports multiple diagnoses per patient with priority/status
    """
    __tablename__ = 'patient_diagnoses'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    icd10_code_id = db.Column(db.Integer, db.ForeignKey('icd10_codes.id'), nullable=False)
    
    # Diagnosis metadata
    diagnosis_type = db.Column(db.String(20), default='primary')  # primary, secondary, differential
    status = db.Column(db.String(20), default='active')  # active, resolved, chronic, ruled_out
    confidence_level = db.Column(db.String(20))  # confirmed, probable, suspected
    
    # Clinical details
    clinical_notes = db.Column(db.Text)  # Additional clinical context
    severity = db.Column(db.String(20))  # mild, moderate, severe
    onset_date = db.Column(db.Date)  # When condition started
    diagnosis_date = db.Column(db.Date, default=datetime.utcnow)  # When diagnosed
    resolved_date = db.Column(db.Date)  # When resolved (if applicable)
    
    # Provider information
    diagnosed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    diagnosed_by = db.relationship('User', backref='diagnoses_made')
    
    def __repr__(self):
        return f'<PatientDiagnosis {self.patient_id}: {self.icd10_code.code}>'
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    @property
    def duration_days(self):
        """Calculate duration of condition"""
        if self.onset_date:
            end_date = self.resolved_date or datetime.utcnow().date()
            return (end_date - self.onset_date).days
        return None


class DiagnosisTemplate(db.Model):
    """
    Pre-defined diagnosis templates for common physiotherapy conditions
    Helps speed up diagnosis entry and ensures consistency
    """
    __tablename__ = 'diagnosis_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)  # e.g., "Lower Back Pain - Acute"
    description = db.Column(db.Text)
    
    # Primary ICD-10 code
    primary_icd10_code_id = db.Column(db.Integer, db.ForeignKey('icd10_codes.id'), nullable=False)
    
    # Template settings
    default_severity = db.Column(db.String(20), default='moderate')
    typical_duration_days = db.Column(db.Integer)  # Expected duration
    common_symptoms = db.Column(db.Text)  # JSON array of common symptoms
    treatment_guidelines = db.Column(db.Text)  # Standard treatment approach
    
    # Usage tracking
    usage_count = db.Column(db.Integer, default=0)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    primary_icd10_code = db.relationship('ICD10Code', backref='templates')
    created_by = db.relationship('User', backref='diagnosis_templates')
    
    def __repr__(self):
        return f'<DiagnosisTemplate {self.name}>'


class TreatmentOutcome(db.Model):
    """
    Track treatment outcomes by diagnosis for analytics
    Links treatments to specific diagnoses for outcome analysis
    """
    __tablename__ = 'treatment_outcomes'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_diagnosis_id = db.Column(db.Integer, db.ForeignKey('patient_diagnoses.id'), nullable=False)
    treatment_id = db.Column(db.Integer, db.ForeignKey('treatment.id'), nullable=False)
    
    # Outcome metrics
    pain_level_before = db.Column(db.Integer)  # 0-10 scale
    pain_level_after = db.Column(db.Integer)   # 0-10 scale
    functional_improvement = db.Column(db.String(20))  # significant, moderate, minimal, none
    patient_satisfaction = db.Column(db.Integer)  # 1-5 scale
    
    # Clinical assessment
    objective_improvement = db.Column(db.Text)  # Clinical notes on improvement
    treatment_effectiveness = db.Column(db.String(20))  # excellent, good, fair, poor
    
    # Follow-up
    follow_up_required = db.Column(db.Boolean, default=False)
    discharge_status = db.Column(db.String(50))  # completed, ongoing, referred, discontinued
    
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    recorded_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    patient_diagnosis = db.relationship('PatientDiagnosis', backref='treatment_outcomes')
    treatment = db.relationship('Treatment', backref='diagnosis_outcomes')
    recorded_by = db.relationship('User', backref='outcome_records')
    
    def __repr__(self):
        return f'<TreatmentOutcome {self.patient_diagnosis_id}:{self.treatment_id}>'
    
    @property
    def pain_improvement(self):
        """Calculate pain level improvement"""
        if self.pain_level_before is not None and self.pain_level_after is not None:
            return self.pain_level_before - self.pain_level_after
        return None
    
    @property
    def pain_improvement_percentage(self):
        """Calculate percentage pain improvement"""
        improvement = self.pain_improvement
        if improvement is not None and self.pain_level_before > 0:
            return (improvement / self.pain_level_before) * 100
        return None


class PathologyGuide(db.Model):
    """
    Clinical Pathway Guide - Rich educational content for diagnoses
    Provides clinical pearls, patient education, red flags, and FAQs
    """
    __tablename__ = 'pathology_guides'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    # Clinical content for healthcare providers
    clinical_pearls = db.Column(db.Text)  # Quick tips for the physio
    patient_education = db.Column(db.Text)  # Simple language explanation for patients
    red_flags = db.Column(db.Text)  # When to refer back to doctor/urgent care
    
    # FAQs stored as JSON: [{"q": "Question?", "a": "Answer"}]
    # Using Text for SQLite compatibility, will store JSON strings
    faq_data = db.Column(db.Text)  # JSON string of FAQ array
    
    # Additional clinical information
    anatomy_overview = db.Column(db.Text)  # Basic anatomy explanation
    treatment_phases = db.Column(db.Text)  # Treatment progression phases
    home_exercises = db.Column(db.Text)  # Key exercises for patients
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Link to the Diagnosis Template (One-to-One relationship)
    diagnosis_template_id = db.Column(db.Integer, db.ForeignKey('diagnosis_templates.id'), unique=True)
    diagnosis_template = db.relationship('DiagnosisTemplate', backref=db.backref('pathology_guide', uselist=False))
    
    def __repr__(self):
        return f'<PathologyGuide {self.name}>'
    
    @property
    def faq_list(self):
        """Get FAQ data as a Python list"""
        if self.faq_data:
            try:
                import json
                return json.loads(self.faq_data)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    @faq_list.setter
    def faq_list(self, value):
        """Set FAQ data from a Python list"""
        if value:
            import json
            self.faq_data = json.dumps(value)
        else:
            self.faq_data = None
    
    def get_summary_stats(self):
        """Get summary statistics for this guide"""
        return {
            'has_clinical_pearls': bool(self.clinical_pearls),
            'has_patient_education': bool(self.patient_education),
            'has_red_flags': bool(self.red_flags),
            'faq_count': len(self.faq_list),
            'has_anatomy': bool(self.anatomy_overview),
            'has_exercises': bool(self.home_exercises)
        }
