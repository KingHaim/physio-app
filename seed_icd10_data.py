#!/usr/bin/env python3
"""
ICD-10 Data Seeding Script for Physiotherapy Application

This script populates the ICD-10 codes database with musculoskeletal and 
physiotherapy-relevant conditions.

Focus areas:
- M00-M99: Diseases of the musculoskeletal system and connective tissue
- S00-T88: Injury, poisoning and certain other consequences of external causes
- G00-G99: Diseases of the nervous system (relevant conditions)
- R00-R99: Symptoms, signs and abnormal clinical and laboratory findings

Usage:
    python seed_icd10_data.py
"""

from app import create_app, db
from app.models_icd10 import ICD10Code, DiagnosisTemplate

def seed_icd10_codes():
    """Seed the database with physiotherapy-relevant ICD-10 codes"""
    
    # Musculoskeletal System Codes (M00-M99)
    musculoskeletal_codes = [
        # Back Pain and Spine Disorders (M40-M54)
        ("M54.5", "Low back pain", "Low back pain", "Musculoskeletal", "Back pain"),
        ("M54.2", "Cervicalgia", "Neck pain", "Musculoskeletal", "Neck disorders"),
        ("M54.6", "Pain in thoracic spine", "Mid-back pain", "Musculoskeletal", "Back pain"),
        ("M54.3", "Sciatica", "Sciatica", "Musculoskeletal", "Back pain"),
        ("M54.4", "Lumbago with sciatica", "Lower back pain with sciatica", "Musculoskeletal", "Back pain"),
        ("M54.1", "Radiculopathy", "Nerve root pain", "Musculoskeletal", "Nerve disorders"),
        ("M43.6", "Torticollis", "Wry neck", "Musculoskeletal", "Neck disorders"),
        ("M50.2", "Other cervical disc displacement", "Cervical disc herniation", "Musculoskeletal", "Disc disorders"),
        ("M51.2", "Other specified intervertebral disc displacement", "Lumbar disc herniation", "Musculoskeletal", "Disc disorders"),
        ("M47.2", "Other spondylosis with radiculopathy", "Spinal arthritis with nerve pain", "Musculoskeletal", "Degenerative spine"),
        
        # Joint Disorders (M00-M25)
        ("M25.5", "Pain in joint", "Joint pain", "Musculoskeletal", "Joint disorders"),
        ("M23.9", "Internal derangement of knee, unspecified", "Knee internal derangement", "Musculoskeletal", "Knee disorders"),
        ("M75.3", "Calcific tendinitis of shoulder", "Calcific shoulder tendinitis", "Musculoskeletal", "Shoulder disorders"),
        ("M75.1", "Rotator cuff tear or rupture, not specified as traumatic", "Rotator cuff tear", "Musculoskeletal", "Shoulder disorders"),
        ("M75.0", "Adhesive capsulitis of shoulder", "Frozen shoulder", "Musculoskeletal", "Shoulder disorders"),
        ("M70.4", "Prepatellar bursitis", "Knee bursitis", "Musculoskeletal", "Knee disorders"),
        ("M17.9", "Osteoarthritis of knee, unspecified", "Knee osteoarthritis", "Musculoskeletal", "Degenerative joint"),
        ("M16.9", "Osteoarthritis of hip, unspecified", "Hip osteoarthritis", "Musculoskeletal", "Degenerative joint"),
        ("M19.9", "Osteoarthritis, unspecified site", "Osteoarthritis", "Musculoskeletal", "Degenerative joint"),
        
        # Muscle and Tendon Disorders (M60-M79)
        ("M79.3", "Panniculitis, unspecified", "Muscle inflammation", "Musculoskeletal", "Muscle disorders"),
        ("M62.8", "Other specified disorders of muscle", "Muscle strain", "Musculoskeletal", "Muscle disorders"),
        ("M77.9", "Enthesopathy, unspecified", "Tendon attachment pain", "Musculoskeletal", "Tendon disorders"),
        ("M76.6", "Achilles tendinitis", "Achilles tendinitis", "Musculoskeletal", "Tendon disorders"),
        ("M77.1", "Lateral epicondylitis", "Tennis elbow", "Musculoskeletal", "Elbow disorders"),
        ("M77.0", "Medial epicondylitis", "Golfer's elbow", "Musculoskeletal", "Elbow disorders"),
        ("M65.9", "Synovitis and tenosynovitis, unspecified", "Tendon sheath inflammation", "Musculoskeletal", "Tendon disorders"),
        ("M70.0", "Crepitant synovitis (acute) (chronic) of hand and wrist", "Wrist tendinitis", "Musculoskeletal", "Wrist disorders"),
        
        # Fibromyalgia and Myofascial Pain
        ("M79.7", "Fibromyalgia", "Fibromyalgia", "Musculoskeletal", "Chronic pain"),
        ("M79.1", "Myalgia", "Muscle pain", "Musculoskeletal", "Muscle disorders"),
        ("M79.0", "Rheumatism, unspecified", "General musculoskeletal pain", "Musculoskeletal", "General pain"),
        
        # Postural and Mechanical Disorders
        ("M40.2", "Other and unspecified kyphosis", "Rounded back posture", "Musculoskeletal", "Postural disorders"),
        ("M41.9", "Scoliosis, unspecified", "Spinal curvature", "Musculoskeletal", "Postural disorders"),
        ("M43.8", "Other specified deforming dorsopathies", "Postural dysfunction", "Musculoskeletal", "Postural disorders"),
    ]
    
    # Injury and Trauma Codes (S00-T88)
    injury_codes = [
        # Sprains and Strains
        ("S93.4", "Sprain and strain of ankle", "Ankle sprain", "Injury", "Ankle injuries"),
        ("S83.5", "Sprain and strain of cruciate ligament of knee", "Knee ligament sprain", "Injury", "Knee injuries"),
        ("S63.6", "Sprain and strain of finger(s)", "Finger sprain", "Injury", "Hand injuries"),
        ("S43.4", "Sprain and strain of shoulder joint", "Shoulder sprain", "Injury", "Shoulder injuries"),
        ("S13.4", "Sprain and strain of cervical spine", "Neck strain/whiplash", "Injury", "Neck injuries"),
        ("S33.5", "Sprain and strain of lumbar spine", "Lower back strain", "Injury", "Back injuries"),
        
        # Fractures (common ones requiring physiotherapy)
        ("S72.0", "Fracture of neck of femur", "Hip fracture", "Injury", "Hip injuries"),
        ("S52.5", "Fracture of lower end of radius", "Wrist fracture (Colles)", "Injury", "Wrist injuries"),
        ("S82.6", "Fracture of lateral malleolus", "Ankle fracture", "Injury", "Ankle injuries"),
        
        # Post-surgical conditions
        ("Z98.1", "Arthrodesis status", "Post spinal fusion", "Post-surgical", "Post-operative"),
        ("Z98.8", "Other specified postprocedural states", "Post-operative status", "Post-surgical", "Post-operative"),
    ]
    
    # Neurological Conditions (G00-G99)
    neurological_codes = [
        ("G56.0", "Carpal tunnel syndrome", "Carpal tunnel syndrome", "Neurological", "Nerve entrapment"),
        ("G57.6", "Lesion of plantar nerve", "Plantar fasciitis/nerve", "Neurological", "Foot disorders"),
        ("G44.2", "Tension-type headache", "Tension headache", "Neurological", "Headaches"),
        ("G93.3", "Postviral fatigue syndrome", "Chronic fatigue syndrome", "Neurological", "Chronic conditions"),
    ]
    
    # Symptoms and Signs (R00-R99)
    symptom_codes = [
        ("R52", "Pain, unspecified", "General pain", "Symptoms", "Pain"),
        ("R25.2", "Cramp and spasm", "Muscle cramps", "Symptoms", "Muscle symptoms"),
        ("R26.2", "Difficulty in walking, not elsewhere classified", "Walking difficulty", "Symptoms", "Mobility issues"),
        ("R29.3", "Abnormal posture", "Poor posture", "Symptoms", "Postural issues"),
    ]
    
    # Combine all codes
    all_codes = musculoskeletal_codes + injury_codes + neurological_codes + symptom_codes
    
    print(f"Seeding {len(all_codes)} ICD-10 codes...")
    
    for code, description, short_desc, category, subcategory in all_codes:
        # Check if code already exists
        existing = ICD10Code.query.filter_by(code=code).first()
        if existing:
            print(f"  Updating existing code: {code}")
            existing.description = description
            existing.short_description = short_desc
            existing.category = category
            existing.subcategory = subcategory
        else:
            print(f"  Adding new code: {code} - {short_desc}")
            icd_code = ICD10Code(
                code=code,
                description=description,
                short_description=short_desc,
                category=category,
                subcategory=subcategory,
                is_active=True,
                is_physiotherapy_relevant=True
            )
            db.session.add(icd_code)
    
    db.session.commit()
    print("ICD-10 codes seeded successfully!")

def seed_diagnosis_templates():
    """Create common diagnosis templates for quick selection"""
    
    templates = [
        {
            "name": "Acute Lower Back Pain",
            "description": "Common acute lower back pain presentation",
            "primary_code": "M54.5",
            "default_severity": "moderate",
            "typical_duration_days": 14,
            "common_symptoms": '["Lower back pain", "Muscle spasm", "Limited mobility", "Pain with movement"]',
            "treatment_guidelines": "Manual therapy, exercise therapy, pain management, ergonomic advice"
        },
        {
            "name": "Neck Pain/Cervicalgia",
            "description": "General neck pain condition",
            "primary_code": "M54.2",
            "default_severity": "moderate",
            "typical_duration_days": 10,
            "common_symptoms": '["Neck pain", "Stiffness", "Headaches", "Muscle tension"]',
            "treatment_guidelines": "Manual therapy, neck exercises, posture correction, ergonomic assessment"
        },
        {
            "name": "Frozen Shoulder",
            "description": "Adhesive capsulitis of shoulder",
            "primary_code": "M75.0",
            "default_severity": "severe",
            "typical_duration_days": 180,
            "common_symptoms": '["Shoulder pain", "Severe stiffness", "Night pain", "Limited range of motion"]',
            "treatment_guidelines": "Gentle mobilization, pain management, progressive exercises, patient education"
        },
        {
            "name": "Tennis Elbow",
            "description": "Lateral epicondylitis",
            "primary_code": "M77.1",
            "default_severity": "moderate",
            "typical_duration_days": 42,
            "common_symptoms": '["Lateral elbow pain", "Grip weakness", "Pain with lifting", "Tenderness"]',
            "treatment_guidelines": "Activity modification, eccentric exercises, manual therapy, ergonomic advice"
        },
        {
            "name": "Ankle Sprain",
            "description": "Acute ankle ligament injury",
            "primary_code": "S93.4",
            "default_severity": "moderate",
            "typical_duration_days": 21,
            "common_symptoms": '["Ankle pain", "Swelling", "Instability", "Limited weight bearing"]',
            "treatment_guidelines": "RICE protocol, progressive loading, balance training, return to activity"
        }
    ]
    
    print(f"Creating {len(templates)} diagnosis templates...")
    
    for template_data in templates:
        # Find the ICD-10 code
        icd_code = ICD10Code.query.filter_by(code=template_data["primary_code"]).first()
        if not icd_code:
            print(f"  Warning: ICD-10 code {template_data['primary_code']} not found for template {template_data['name']}")
            continue
        
        # Check if template already exists
        existing = DiagnosisTemplate.query.filter_by(name=template_data["name"]).first()
        if existing:
            print(f"  Updating existing template: {template_data['name']}")
            existing.description = template_data["description"]
            existing.primary_icd10_code_id = icd_code.id
            existing.default_severity = template_data["default_severity"]
            existing.typical_duration_days = template_data["typical_duration_days"]
            existing.common_symptoms = template_data["common_symptoms"]
            existing.treatment_guidelines = template_data["treatment_guidelines"]
        else:
            print(f"  Creating new template: {template_data['name']}")
            template = DiagnosisTemplate(
                name=template_data["name"],
                description=template_data["description"],
                primary_icd10_code_id=icd_code.id,
                default_severity=template_data["default_severity"],
                typical_duration_days=template_data["typical_duration_days"],
                common_symptoms=template_data["common_symptoms"],
                treatment_guidelines=template_data["treatment_guidelines"]
            )
            db.session.add(template)
    
    db.session.commit()
    print("Diagnosis templates created successfully!")

def main():
    """Main seeding function"""
    app = create_app()
    
    with app.app_context():
        print("Starting ICD-10 data seeding...")
        
        # Create tables if they don't exist
        db.create_all()
        
        # Seed ICD-10 codes
        seed_icd10_codes()
        
        # Seed diagnosis templates
        seed_diagnosis_templates()
        
        print("\nICD-10 data seeding completed successfully!")
        print("\nNext steps:")
        print("1. Update your database migration files")
        print("2. Implement the ICD-10 UI components")
        print("3. Update patient forms to use ICD-10 diagnosis selection")
        print("4. Implement analytics and reporting features")

if __name__ == "__main__":
    main()
