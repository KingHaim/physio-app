"""
Pathology Guide API Routes
Provides endpoints for Clinical Pathway Guide system
"""

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from app.models_icd10 import PathologyGuide, DiagnosisTemplate
from app import db
import json

pathology_guide_api = Blueprint('pathology_guide_api', __name__)

@pathology_guide_api.route('/api/pathology-guide/<path:template_name>', methods=['GET'])
@login_required
def get_pathology_guide(template_name):
    """
    Get pathology guide by template name
    Returns rich clinical content for the specified diagnosis
    """
    try:
        # Debug: log what we received
        current_app.logger.info(f'Pathology guide request for: "{template_name}" (type: {type(template_name)})')
        print(f'🔍 API received template_name: "{template_name}"')
        # First, try to find the pathology guide by exact template name
        guide = PathologyGuide.query.filter_by(name=template_name).first()
        
        # If not found, try the same mappings as in icd10_api.py
        if not guide:
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
            
            mapped_name = special_mappings.get(template_name)
            if mapped_name:
                guide = PathologyGuide.query.filter_by(name=mapped_name).first()
        
        if not guide:
            return jsonify({
                'error': 'Guide not found',
                'message': f'No pathology guide found for "{template_name}"'
            }), 404
        
        # Get associated diagnosis template for additional info
        template = guide.diagnosis_template
        
        # Parse FAQ data
        faq_list = []
        if guide.faq_data:
            try:
                faq_list = json.loads(guide.faq_data)
            except (json.JSONDecodeError, TypeError):
                current_app.logger.warning(f"Invalid FAQ data for guide {guide.name}")
                faq_list = []
        
        # Prepare response data
        guide_data = {
            'id': guide.id,
            'name': guide.name,
            'description': template.description if template else None,
            'clinical_pearls': guide.clinical_pearls,
            'patient_education': guide.patient_education,
            'red_flags': guide.red_flags,
            'anatomy_overview': guide.anatomy_overview,
            'treatment_phases': guide.treatment_phases,
            'home_exercises': guide.home_exercises,
            'faq_list': faq_list,
            'typical_duration_days': template.typical_duration_days if template else None,
            'common_symptoms': template.common_symptoms if template else None,
            'treatment_guidelines': template.treatment_guidelines if template else None,
            'created_at': guide.created_at.isoformat() if guide.created_at else None,
            'updated_at': guide.updated_at.isoformat() if guide.updated_at else None,
            'template_id': guide.diagnosis_template_id,
            'stats': guide.get_summary_stats()
        }
        
        return jsonify(guide_data)
        
    except Exception as e:
        current_app.logger.error(f"Error fetching pathology guide {template_name}: {str(e)}")
        return jsonify({
            'error': 'Server error',
            'message': 'Failed to fetch pathology guide'
        }), 500

@pathology_guide_api.route('/api/pathology-guides', methods=['GET'])
# @login_required  # Temporarily disabled for testing
def list_pathology_guides():
    """
    List all available pathology guides
    Returns summary information for all guides
    """
    try:
        guides = PathologyGuide.query.join(DiagnosisTemplate).filter(
            DiagnosisTemplate.is_active == True
        ).all()
        
        guides_list = []
        for guide in guides:
            template = guide.diagnosis_template
            guides_list.append({
                'id': guide.id,
                'name': guide.name,
                'description': template.description if template else None,
                'has_clinical_pearls': bool(guide.clinical_pearls),
                'has_patient_education': bool(guide.patient_education),
                'has_red_flags': bool(guide.red_flags),
                'faq_count': len(guide.faq_list),
                'template_id': guide.diagnosis_template_id,
                'updated_at': guide.updated_at.isoformat() if guide.updated_at else None
            })
        
        return jsonify({
            'guides': guides_list,
            'total': len(guides_list)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error listing pathology guides: {str(e)}")
        return jsonify({
            'error': 'Server error',
            'message': 'Failed to fetch pathology guides'
        }), 500

@pathology_guide_api.route('/api/pathology-guide/<int:guide_id>/stats', methods=['GET'])
# @login_required  # Temporarily disabled for testing
def get_guide_stats(guide_id):
    """
    Get detailed statistics for a specific pathology guide
    """
    try:
        guide = PathologyGuide.query.get_or_404(guide_id)
        
        stats = guide.get_summary_stats()
        
        # Add usage statistics if available
        template = guide.diagnosis_template
        if template:
            stats['template_usage_count'] = template.usage_count or 0
            stats['template_name'] = template.name
        
        return jsonify(stats)
        
    except Exception as e:
        current_app.logger.error(f"Error fetching guide stats {guide_id}: {str(e)}")
        return jsonify({
            'error': 'Server error',
            'message': 'Failed to fetch guide statistics'
        }), 500

@pathology_guide_api.route('/api/diagnosis-templates-with-guides', methods=['GET'])
# @login_required  # Temporarily disabled for testing
def list_templates_with_guides():
    """
    List all diagnosis templates and indicate which have pathology guides
    Useful for showing info buttons in the UI
    """
    try:
        templates = DiagnosisTemplate.query.filter_by(is_active=True).all()
        
        templates_list = []
        for template in templates:
            has_guide = template.pathology_guide is not None
            
            template_data = {
                'id': template.id,
                'name': template.name,
                'description': template.description,
                'has_pathology_guide': has_guide,
                'usage_count': template.usage_count or 0
            }
            
            if has_guide:
                guide = template.pathology_guide
                template_data['guide_stats'] = guide.get_summary_stats()
            
            templates_list.append(template_data)
        
        return jsonify({
            'templates': templates_list,
            'total': len(templates_list),
            'with_guides': sum(1 for t in templates_list if t['has_pathology_guide'])
        })
        
    except Exception as e:
        current_app.logger.error(f"Error listing templates with guides: {str(e)}")
        return jsonify({
            'error': 'Server error',
            'message': 'Failed to fetch templates'
        }), 500

@pathology_guide_api.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Not found',
        'message': 'The requested pathology guide was not found'
    }), 404

@pathology_guide_api.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500
