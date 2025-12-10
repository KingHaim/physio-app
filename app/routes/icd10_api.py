# app/routes/icd10_api.py
# ICD-10 Diagnosis System API Routes

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from datetime import datetime, date, timedelta
import json

from ..models import db, Patient
from ..models_icd10 import ICD10Code, PatientDiagnosis, DiagnosisTemplate, TreatmentOutcome
from ..decorators import physio_required

icd10_api = Blueprint('icd10_api', __name__)

@icd10_api.route('/api/icd10/search')
@login_required
def search_icd10_codes():
    """Search ICD-10 codes by query string"""
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 20)), 50)  # Max 50 results
    category = request.args.get('category', '')
    
    if len(query) < 2:
        return jsonify({'codes': [], 'message': 'Query too short'})
    
    # Build search query
    search_query = ICD10Code.query.filter(
        ICD10Code.is_active == True,
        ICD10Code.is_physiotherapy_relevant == True
    )
    
    # Add text search
    search_term = f"%{query}%"
    search_query = search_query.filter(
        or_(
            ICD10Code.code.ilike(search_term),
            ICD10Code.description.ilike(search_term),
            ICD10Code.short_description.ilike(search_term)
        )
    )
    
    # Add category filter if specified
    if category:
        search_query = search_query.filter(ICD10Code.category == category)
    
    # Execute search
    codes = search_query.limit(limit).all()
    
    # Format results
    results = []
    for code in codes:
        results.append({
            'id': code.id,
            'code': code.code,
            'description': code.description,
            'short_description': code.short_description,
            'category': code.category,
            'subcategory': code.subcategory
        })
    
    return jsonify({
        'codes': results,
        'count': len(results),
        'query': query
    })

@icd10_api.route('/api/icd10/categories')
@login_required
def get_icd10_categories():
    """Get all available ICD-10 categories"""
    categories = db.session.query(
        ICD10Code.category,
        db.func.count(ICD10Code.id).label('count')
    ).filter(
        ICD10Code.is_active == True,
        ICD10Code.is_physiotherapy_relevant == True
    ).group_by(ICD10Code.category).all()
    
    result = []
    for category, count in categories:
        result.append({
            'name': category,
            'count': count
        })
    
    return jsonify({'categories': result})

@icd10_api.route('/api/icd10/templates')
@login_required
def get_diagnosis_templates():
    """Get available diagnosis templates"""
    templates = DiagnosisTemplate.query.filter(
        DiagnosisTemplate.is_active == True
    ).order_by(DiagnosisTemplate.usage_count.desc()).all()
    
    result = []
    for template in templates:
        result.append({
            'id': template.id,
            'name': template.name,
            'description': template.description,
            'icd10_code': template.primary_icd10_code.code,
            'icd10_description': template.primary_icd10_code.short_description,
            'default_severity': template.default_severity,
            'typical_duration_days': template.typical_duration_days,
            'usage_count': template.usage_count
        })
    
    return jsonify({'templates': result})

@icd10_api.route('/api/patient/<int:patient_id>/diagnoses', methods=['GET'])
@login_required
@physio_required
def get_patient_diagnoses(patient_id):
    """Get all diagnoses for a patient"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Check access permissions
    accessible_patients = current_user.get_accessible_patients()
    if patient not in accessible_patients:
        return jsonify({'error': 'Access denied'}), 403
    
    diagnoses = PatientDiagnosis.query.filter_by(
        patient_id=patient_id
    ).order_by(PatientDiagnosis.diagnosis_date.desc()).all()
    
    result = []
    for diagnosis in diagnoses:
        # Check if there's a pathology guide for this diagnosis
        from app.models_icd10 import PathologyGuide, DiagnosisTemplate
        
        # First, try to find a diagnosis template that matches this ICD-10 code
        template = DiagnosisTemplate.query.filter_by(primary_icd10_code_id=diagnosis.icd10_code_id).first()
        
        has_pathology_guide = False
        template_name = diagnosis.icd10_code.short_description
        
        if template:
            # Check if there's a pathology guide for this template
            pathology_guide = PathologyGuide.query.filter_by(name=template.name).first()
            if pathology_guide:
                has_pathology_guide = True
                template_name = template.name
        
        if not has_pathology_guide:
            # Fallback: try direct matching with ICD-10 description variations
            variations = [
                diagnosis.icd10_code.short_description,
                diagnosis.icd10_code.short_description.title(),  # Capitalize first letters
                diagnosis.icd10_code.description,
            ]
            
            # Special case mappings for common mismatches
            special_mappings = {
                'Low back pain': 'Acute Lower Back Pain',
                'Frozen shoulder': 'Frozen Shoulder',
                'Tennis elbow': 'Tennis Elbow',
                'Plantar fasciitis': 'Plantar Fasciitis',
                'Neck pain': 'Neck Pain/Cervicalgia',
                'Stiff jaw/TMJ': 'TMJ Dysfunction',
                'TMJ Dysfunction': 'TMJ Dysfunction',
            }
            
            # Add special mappings to variations
            for original, mapped in special_mappings.items():
                if diagnosis.icd10_code.short_description == original:
                    variations.insert(0, mapped)  # Try mapped version first
            
            for variation in variations:
                pathology_guide = PathologyGuide.query.filter_by(name=variation).first()
                if pathology_guide:
                    has_pathology_guide = True
                    template_name = variation
                    break
        
        result.append({
            'id': diagnosis.id,
            'icd10_code': diagnosis.icd10_code.code,
            'description': diagnosis.icd10_code.short_description,
            'full_description': diagnosis.icd10_code.description,
            'diagnosis_type': diagnosis.diagnosis_type,
            'status': diagnosis.status,
            'confidence_level': diagnosis.confidence_level,
            'severity': diagnosis.severity,
            'onset_date': diagnosis.onset_date.isoformat() if diagnosis.onset_date else None,
            'diagnosis_date': diagnosis.diagnosis_date.isoformat() if diagnosis.diagnosis_date else None,
            'resolved_date': diagnosis.resolved_date.isoformat() if diagnosis.resolved_date else None,
            'clinical_notes': diagnosis.clinical_notes,
            'duration_days': diagnosis.duration_days,
            'is_active': diagnosis.is_active,
            'has_pathology_guide': has_pathology_guide,
            'template_name': template_name
        })
    
    return jsonify({
        'diagnoses': result,
        'patient_id': patient_id,
        'patient_name': patient.name
    })

@icd10_api.route('/api/patient/<int:patient_id>/diagnoses/<int:diagnosis_id>', methods=['GET'])
@login_required
def get_patient_diagnosis(patient_id, diagnosis_id):
    """Get a specific diagnosis for a patient"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Check access permissions
    accessible_patients = current_user.get_accessible_patients()
    if patient not in accessible_patients:
        return jsonify({'error': 'Access denied'}), 403
    
    diagnosis = PatientDiagnosis.query.filter_by(
        id=diagnosis_id,
        patient_id=patient_id
    ).first_or_404()
    
    return jsonify({
        'id': diagnosis.id,
        'icd10_code': diagnosis.icd10_code.code,
        'icd10_code_id': diagnosis.icd10_code_id,
        'description': diagnosis.icd10_code.short_description,
        'full_description': diagnosis.icd10_code.description,
        'diagnosis_type': diagnosis.diagnosis_type,
        'status': diagnosis.status,
        'confidence_level': diagnosis.confidence_level,
        'severity': diagnosis.severity,
        'onset_date': diagnosis.onset_date.isoformat() if diagnosis.onset_date else None,
        'diagnosis_date': diagnosis.diagnosis_date.isoformat() if diagnosis.diagnosis_date else None,
        'resolved_date': diagnosis.resolved_date.isoformat() if diagnosis.resolved_date else None,
        'clinical_notes': diagnosis.clinical_notes,
        'duration_days': diagnosis.duration_days,
        'is_active': diagnosis.is_active
    })

@icd10_api.route('/api/patient/<int:patient_id>/diagnoses', methods=['POST'])
@login_required
@physio_required
def add_patient_diagnosis(patient_id):
    """Add a new diagnosis to a patient"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Check access permissions
    accessible_patients = current_user.get_accessible_patients()
    if patient not in accessible_patients:
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    
    # Validate required fields
    if not data.get('icd10_code_id'):
        return jsonify({'error': 'ICD-10 code is required'}), 400
    
    # Verify ICD-10 code exists
    icd10_code = ICD10Code.query.get(data['icd10_code_id'])
    if not icd10_code:
        return jsonify({'error': 'Invalid ICD-10 code'}), 400
    
    # Handle primary diagnosis logic
    diagnosis_type = data.get('diagnosis_type', 'primary')
    if diagnosis_type == 'primary':
        # Mark existing primary diagnoses as secondary
        existing_primary = PatientDiagnosis.query.filter_by(
            patient_id=patient_id,
            diagnosis_type='primary',
            status='active'
        ).first()
        if existing_primary:
            existing_primary.diagnosis_type = 'secondary'
    
    # Create new diagnosis
    diagnosis = PatientDiagnosis(
        patient_id=patient_id,
        icd10_code_id=data['icd10_code_id'],
        diagnosis_type=diagnosis_type,
        status=data.get('status', 'active'),
        confidence_level=data.get('confidence_level', 'confirmed'),
        severity=data.get('severity', 'moderate'),
        clinical_notes=data.get('clinical_notes', ''),
        onset_date=datetime.strptime(data['onset_date'], '%Y-%m-%d').date() if data.get('onset_date') else None,
        diagnosis_date=datetime.strptime(data['diagnosis_date'], '%Y-%m-%d').date() if data.get('diagnosis_date') else date.today(),
        diagnosed_by_user_id=current_user.id
    )
    
    db.session.add(diagnosis)
    
    # Update legacy diagnosis field for backward compatibility
    if diagnosis_type == 'primary':
        patient.diagnosis = f"{icd10_code.code}: {icd10_code.short_description}"
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'diagnosis_id': diagnosis.id,
        'message': 'Diagnosis added successfully'
    })

@icd10_api.route('/api/patient/<int:patient_id>/diagnoses/<int:diagnosis_id>', methods=['PUT'])
@login_required
@physio_required
def update_patient_diagnosis(patient_id, diagnosis_id):
    """Update an existing patient diagnosis"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Check access permissions
    accessible_patients = current_user.get_accessible_patients()
    if patient not in accessible_patients:
        return jsonify({'error': 'Access denied'}), 403
    
    diagnosis = PatientDiagnosis.query.filter_by(
        id=diagnosis_id,
        patient_id=patient_id
    ).first_or_404()
    
    data = request.get_json()
    
    # Update fields
    if 'status' in data:
        diagnosis.status = data['status']
        if data['status'] == 'resolved' and not diagnosis.resolved_date:
            diagnosis.resolved_date = date.today()
    
    if 'severity' in data:
        diagnosis.severity = data['severity']
    
    if 'clinical_notes' in data:
        diagnosis.clinical_notes = data['clinical_notes']
    
    if 'confidence_level' in data:
        diagnosis.confidence_level = data['confidence_level']
    
    diagnosis.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Diagnosis updated successfully'
    })

@icd10_api.route('/api/patient/<int:patient_id>/diagnoses/<int:diagnosis_id>', methods=['DELETE'])
@login_required
@physio_required
def delete_patient_diagnosis(patient_id, diagnosis_id):
    """Delete a patient diagnosis"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Check access permissions
    accessible_patients = current_user.get_accessible_patients()
    if patient not in accessible_patients:
        return jsonify({'error': 'Access denied'}), 403
    
    diagnosis = PatientDiagnosis.query.filter_by(
        id=diagnosis_id,
        patient_id=patient_id
    ).first_or_404()
    
    db.session.delete(diagnosis)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Diagnosis deleted successfully'
    })

@icd10_api.route('/api/template/<int:template_id>/apply/<int:patient_id>', methods=['POST'])
@login_required
@physio_required
def apply_diagnosis_template(template_id, patient_id):
    """Apply a diagnosis template to a patient"""
    # Debug CSRF token issue
    current_app.logger.info(f'Template application request headers: {dict(request.headers)}')
    csrf_token = request.headers.get('X-CSRFToken')
    current_app.logger.info(f'CSRF token in headers: {csrf_token[:10] + "..." if csrf_token else "None"}')
    
    patient = Patient.query.get_or_404(patient_id)
    template = DiagnosisTemplate.query.get_or_404(template_id)
    
    # Check access permissions
    accessible_patients = current_user.get_accessible_patients()
    if patient not in accessible_patients:
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json() or {}
    
    # Create diagnosis from template
    diagnosis = PatientDiagnosis(
        patient_id=patient_id,
        icd10_code_id=template.primary_icd10_code_id,
        diagnosis_type='primary',
        status='active',
        confidence_level=data.get('confidence_level', 'confirmed'),
        severity=data.get('severity', template.default_severity),
        clinical_notes=data.get('clinical_notes', ''),
        onset_date=datetime.strptime(data['onset_date'], '%Y-%m-%d').date() if data.get('onset_date') else None,
        diagnosis_date=date.today(),
        diagnosed_by_user_id=current_user.id
    )
    
    # Handle existing primary diagnosis
    existing_primary = PatientDiagnosis.query.filter_by(
        patient_id=patient_id,
        diagnosis_type='primary',
        status='active'
    ).first()
    if existing_primary:
        existing_primary.diagnosis_type = 'secondary'
    
    db.session.add(diagnosis)
    
    # Update template usage count
    template.usage_count += 1
    
    # Update legacy diagnosis field
    patient.diagnosis = f"{template.primary_icd10_code.code}: {template.primary_icd10_code.short_description}"
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'diagnosis_id': diagnosis.id,
        'template_name': template.name,
        'message': f'Template "{template.name}" applied successfully'
    })

@icd10_api.route('/api/analytics/diagnoses')
@login_required
@physio_required
def get_diagnosis_analytics():
    """Get diagnosis analytics for the current user's patients"""
    accessible_patients = current_user.get_accessible_patients()
    patient_ids = [p.id for p in accessible_patients]
    
    if not patient_ids:
        return jsonify({'error': 'No accessible patients'}), 403
    
    # Most common diagnoses
    common_diagnoses = db.session.query(
        ICD10Code.code,
        ICD10Code.short_description,
        ICD10Code.category,
        db.func.count(PatientDiagnosis.id).label('count')
    ).join(PatientDiagnosis).filter(
        PatientDiagnosis.patient_id.in_(patient_ids),
        PatientDiagnosis.status == 'active'
    ).group_by(
        ICD10Code.code,
        ICD10Code.short_description,
        ICD10Code.category
    ).order_by(db.func.count(PatientDiagnosis.id).desc()).limit(10).all()
    
    # Diagnoses by category
    category_stats = db.session.query(
        ICD10Code.category,
        db.func.count(PatientDiagnosis.id).label('count')
    ).join(PatientDiagnosis).filter(
        PatientDiagnosis.patient_id.in_(patient_ids),
        PatientDiagnosis.status == 'active'
    ).group_by(ICD10Code.category).all()
    
    # Recent diagnoses (last 30 days)
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    recent_diagnoses = db.session.query(
        db.func.count(PatientDiagnosis.id)
    ).filter(
        PatientDiagnosis.patient_id.in_(patient_ids),
        PatientDiagnosis.diagnosis_date >= thirty_days_ago
    ).scalar()
    
    return jsonify({
        'common_diagnoses': [
            {
                'code': code,
                'description': desc,
                'category': cat,
                'count': count
            }
            for code, desc, cat, count in common_diagnoses
        ],
        'category_stats': [
            {
                'category': cat,
                'count': count
            }
            for cat, count in category_stats
        ],
        'recent_diagnoses_count': recent_diagnoses,
        'total_active_diagnoses': sum(count for _, count in category_stats)
    })

# Template management routes (for admin users)
@icd10_api.route('/api/admin/templates', methods=['POST'])
@login_required
@physio_required
def create_diagnosis_template():
    """Create a new diagnosis template (admin only)"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['name', 'primary_icd10_code_id']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    # Verify ICD-10 code exists
    icd10_code = ICD10Code.query.get(data['primary_icd10_code_id'])
    if not icd10_code:
        return jsonify({'error': 'Invalid ICD-10 code'}), 400
    
    template = DiagnosisTemplate(
        name=data['name'],
        description=data.get('description', ''),
        primary_icd10_code_id=data['primary_icd10_code_id'],
        default_severity=data.get('default_severity', 'moderate'),
        typical_duration_days=data.get('typical_duration_days'),
        common_symptoms=json.dumps(data.get('common_symptoms', [])),
        treatment_guidelines=data.get('treatment_guidelines', ''),
        created_by_user_id=current_user.id
    )
    
    db.session.add(template)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'template_id': template.id,
        'message': 'Template created successfully'
    })
