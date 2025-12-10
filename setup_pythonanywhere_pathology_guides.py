#!/usr/bin/env python3
"""
PythonAnywhere Pathology Guide Setup Script
Sets up the complete ICD-10 and pathology guide system
"""

import sys
import os
from datetime import datetime, date

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models_icd10 import PathologyGuide, ICD10Code, PatientDiagnosis, DiagnosisTemplate
from sqlalchemy import inspect

def create_tables():
    """Create missing tables"""
    print("🔧 Creating database tables...")
    try:
        db.create_all()
        print("✅ Tables created successfully")
        return True
    except Exception as e:
        print(f"❌ Error creating tables: {str(e)}")
        return False

def seed_icd10_codes():
    """Seed essential ICD-10 codes"""
    print("📋 Seeding ICD-10 codes...")
    
    essential_codes = [
        # Musculoskeletal conditions with pathology guides
        ("M72.2", "Plantar fasciitis", "Plantar fasciitis"),
        ("M75.0", "Adhesive capsulitis of shoulder", "Frozen shoulder"), 
        ("M54.5", "Low back pain", "Low back pain"),
        ("M54.2", "Cervicalgia", "Neck pain"),
        ("M26.61", "Arthralgia of temporomandibular joint", "Stiff jaw/TMJ"),
        ("M70.03", "Crepitant synovitis (acute) (chronic) of wrist", "Tennis elbow"),
        
        # Additional common codes
        ("M25.50", "Pain in unspecified joint", "Joint pain"),
        ("M79.3", "Panniculitis, unspecified", "Soft tissue pain"),
        ("M62.81", "Muscle weakness (generalized)", "Muscle weakness"),
        ("M25.561", "Pain in right knee", "Knee pain"),
    ]
    
    added_count = 0
    for code, description, short_desc in essential_codes:
        existing = ICD10Code.query.filter_by(code=code).first()
        if not existing:
            icd10_code = ICD10Code(
                code=code,
                description=description,
                short_description=short_desc,
                category="M00-M99",  # Musculoskeletal system
                is_active=True
            )
            db.session.add(icd10_code)
            added_count += 1
            print(f"  ✅ Added: {code} - {short_desc}")
        else:
            print(f"  ⚠️  Exists: {code} - {short_desc}")
    
    if added_count > 0:
        db.session.commit()
        print(f"✅ Added {added_count} ICD-10 codes")
    else:
        print("ℹ️  All ICD-10 codes already exist")
    
    return True

def seed_diagnosis_templates():
    """Seed diagnosis templates"""
    print("📝 Seeding diagnosis templates...")
    
    templates = [
        {
            "name": "Plantar Fasciitis",
            "description": "Inflammation of the plantar fascia causing heel pain",
            "typical_duration_days": 90,
            "common_symptoms": "Heel pain, morning stiffness, pain after rest",
            "treatment_guidelines": "Rest, stretching, orthotics, physical therapy"
        },
        {
            "name": "Frozen Shoulder", 
            "description": "Adhesive capsulitis causing shoulder stiffness and pain",
            "typical_duration_days": 365,
            "common_symptoms": "Shoulder stiffness, pain, limited range of motion",
            "treatment_guidelines": "Physical therapy, gentle mobilization, pain management"
        },
        {
            "name": "Acute Lower Back Pain",
            "description": "Acute lower back pain and dysfunction", 
            "typical_duration_days": 42,
            "common_symptoms": "Lower back pain, stiffness, muscle spasm",
            "treatment_guidelines": "Activity modification, manual therapy, exercise therapy"
        },
        {
            "name": "Neck Pain/Cervicalgia",
            "description": "Neck pain and cervical dysfunction",
            "typical_duration_days": 28,
            "common_symptoms": "Neck pain, stiffness, headaches, referred pain",
            "treatment_guidelines": "Manual therapy, exercise, posture correction"
        },
        {
            "name": "TMJ Dysfunction", 
            "description": "Temporomandibular joint dysfunction",
            "typical_duration_days": 60,
            "common_symptoms": "Jaw pain, clicking, limited opening, muscle tension",
            "treatment_guidelines": "Manual therapy, exercise, bite guard, stress management"
        },
        {
            "name": "Tennis Elbow",
            "description": "Lateral epicondylitis causing elbow pain",
            "typical_duration_days": 180,
            "common_symptoms": "Lateral elbow pain, grip weakness, pain with lifting",
            "treatment_guidelines": "Activity modification, eccentric exercises, manual therapy"
        }
    ]
    
    added_count = 0
    for template_data in templates:
        existing = DiagnosisTemplate.query.filter_by(name=template_data["name"]).first()
        if not existing:
            # Find matching ICD-10 code
            icd10_code = None
            if "Plantar" in template_data["name"]:
                icd10_code = ICD10Code.query.filter_by(code="M72.2").first()
            elif "Frozen" in template_data["name"]:
                icd10_code = ICD10Code.query.filter_by(code="M75.0").first()
            elif "Back" in template_data["name"]:
                icd10_code = ICD10Code.query.filter_by(code="M54.5").first()
            elif "Neck" in template_data["name"]:
                icd10_code = ICD10Code.query.filter_by(code="M54.2").first()
            elif "TMJ" in template_data["name"]:
                icd10_code = ICD10Code.query.filter_by(code="M26.61").first()
            elif "Tennis" in template_data["name"]:
                icd10_code = ICD10Code.query.filter_by(code="M70.03").first()
            
            template = DiagnosisTemplate(
                name=template_data["name"],
                description=template_data["description"],
                primary_icd10_code_id=icd10_code.id if icd10_code else None,
                typical_duration_days=template_data["typical_duration_days"],
                common_symptoms=template_data["common_symptoms"],
                treatment_guidelines=template_data["treatment_guidelines"],
                is_active=True,
                usage_count=0,
                created_by_id=1  # Assume admin user ID 1
            )
            db.session.add(template)
            added_count += 1
            print(f"  ✅ Added template: {template_data['name']}")
        else:
            print(f"  ⚠️  Template exists: {template_data['name']}")
    
    if added_count > 0:
        db.session.commit()
        print(f"✅ Added {added_count} diagnosis templates")
    else:
        print("ℹ️  All diagnosis templates already exist")
    
    return True

def seed_pathology_guides():
    """Seed pathology guide content"""
    print("📚 Seeding pathology guide content...")
    
    guides_data = [
        {
            "name": "Plantar Fasciitis",
            "clinical_pearls": """
• Most common cause of heel pain in adults
• Peak incidence in 40-60 year olds
• Often bilateral (up to 30% of cases)
• Pain typically worst with first steps in morning
• Associated with tight calf muscles and limited ankle dorsiflexion
• May be related to biomechanical factors (overpronation, high arches)
            """.strip(),
            "patient_education": """
**What is Plantar Fasciitis?**
Plantar fasciitis is inflammation of the thick band of tissue (plantar fascia) that runs across the bottom of your foot and connects your heel bone to your toes.

**What causes it?**
- Overuse or repetitive stress
- Tight calf muscles
- Poor foot mechanics
- Sudden increase in activity
- Inappropriate footwear

**Recovery Timeline:**
Most people recover within 6-12 months with proper treatment.
            """.strip(),
            "red_flags": """
🚨 **Seek immediate medical attention if:**
• Severe, sudden onset heel pain after trauma
• Signs of infection (fever, warmth, redness)
• Numbness or tingling in the foot
• Complete inability to bear weight
• Pain that worsens despite treatment after 6 weeks

⚠️ **Monitor closely:**
• Night pain that disrupts sleep
• Progressive weakness in the foot
• Changes in foot color or temperature
            """.strip(),
            "faq_data": """[
                {
                    "question": "How long does plantar fasciitis take to heal?",
                    "answer": "Most cases resolve within 6-12 months with proper treatment. Early intervention typically leads to faster recovery."
                },
                {
                    "question": "Can I continue exercising with plantar fasciitis?",
                    "answer": "Low-impact activities like swimming or cycling are usually fine. Avoid high-impact activities that worsen symptoms."
                },
                {
                    "question": "What shoes should I wear?",
                    "answer": "Supportive shoes with good arch support and cushioning. Avoid flat shoes, flip-flops, and walking barefoot."
                },
                {
                    "question": "Will I need surgery?",
                    "answer": "Surgery is rarely needed. Less than 5% of cases require surgical intervention, usually after 6-12 months of conservative treatment."
                }
            ]"""
        },
        {
            "name": "Frozen Shoulder",
            "clinical_pearls": """
• Three distinct phases: freezing (2-9 months), frozen (4-12 months), thawing (12-42 months)
• More common in women aged 40-60
• Strong association with diabetes (up to 20% of diabetics affected)
• May be triggered by trauma, surgery, or prolonged immobilization
• Typically affects non-dominant shoulder more frequently
• Night pain is characteristic, especially lying on affected side
            """.strip(),
            "patient_education": """
**What is Frozen Shoulder?**
Frozen shoulder (adhesive capsulitis) is a condition where the shoulder capsule becomes thick and tight, causing pain and severe limitation of movement.

**The Three Stages:**
1. **Freezing Stage (2-9 months):** Gradual onset of pain and stiffness
2. **Frozen Stage (4-12 months):** Pain may decrease but stiffness remains severe
3. **Thawing Stage (12-42 months):** Gradual return of movement

**What to Expect:**
Recovery is typically slow but most people regain 90% of their shoulder function within 2-3 years.
            """.strip(),
            "red_flags": """
🚨 **Seek immediate medical attention if:**
• Sudden severe shoulder pain after trauma
• Signs of infection (fever, severe swelling, warmth)
• Complete loss of arm function
• Severe pain with minimal movement

⚠️ **Monitor closely:**
• Rapidly worsening stiffness over days (not weeks)
• Severe night pain preventing all sleep
• Signs of nerve involvement (numbness, weakness in hand)
            """.strip(),
            "faq_data": """[
                {
                    "question": "Will my shoulder ever be normal again?",
                    "answer": "Most people recover 90% of their shoulder function, though it may take 2-3 years. Some mild stiffness may persist."
                },
                {
                    "question": "Should I push through the pain?",
                    "answer": "Gentle movement is important, but avoid aggressive stretching that causes severe pain as this can worsen inflammation."
                },
                {
                    "question": "Can frozen shoulder affect both shoulders?",
                    "answer": "Yes, though it's uncommon. About 5-10% of people develop it in both shoulders, usually not at the same time."
                },
                {
                    "question": "Is there anything I can do to speed recovery?",
                    "answer": "Consistent gentle exercises, managing diabetes if present, and working with a physiotherapist can help optimize recovery."
                }
            ]"""
        },
        {
            "name": "Acute Lower Back Pain",
            "clinical_pearls": """
• 80% of adults experience lower back pain at some point
• Most acute episodes resolve within 6 weeks without specific treatment
• Red flags are rare but important to identify
• Early return to normal activities promotes faster recovery
• Bed rest beyond 2-3 days may delay recovery
• Psychosocial factors strongly influence chronicity
            """.strip(),
            "patient_education": """
**What is Acute Lower Back Pain?**
Acute lower back pain is pain in the lower back that has been present for less than 6 weeks. It's very common and usually resolves on its own.

**Common Causes:**
- Muscle strain or sprain
- Poor posture or movement patterns
- Sudden movements or lifting
- Stress and tension

**What Helps:**
- Stay active within your pain limits
- Apply heat or cold (whichever feels better)
- Take appropriate pain medication as advised
- Gentle movement and stretching
            """.strip(),
            "red_flags": """
🚨 **Seek immediate medical attention if:**
• Loss of bowel or bladder control
• Severe leg weakness or numbness
• Severe pain after significant trauma
• Fever with back pain
• Progressive neurological symptoms

⚠️ **See your doctor if:**
• Pain radiating below the knee
• Numbness or tingling in legs
• Pain worse at night or at rest
• No improvement after 6 weeks
            """.strip(),
            "faq_data": """[
                {
                    "question": "Should I rest in bed?",
                    "answer": "Brief rest (1-2 days) may help initially, but staying active and gradually returning to normal activities promotes faster recovery."
                },
                {
                    "question": "Will I need an MRI or X-ray?",
                    "answer": "Usually not for acute back pain without red flags. Imaging is typically only needed if symptoms persist beyond 6 weeks."
                },
                {
                    "question": "When can I return to work?",
                    "answer": "This depends on your job and symptoms. Many people can return to desk work within a few days, while physical jobs may require longer."
                },
                {
                    "question": "How can I prevent future episodes?",
                    "answer": "Regular exercise, proper lifting techniques, good posture, and stress management can help prevent recurrence."
                }
            ]"""
        },
        {
            "name": "Neck Pain/Cervicalgia",
            "clinical_pearls": """
• Very common - affects up to 70% of people at some point
• Often related to posture, especially with computer work
• May be associated with headaches and referred pain to shoulders/arms
• Whiplash mechanism can cause delayed onset symptoms
• Stress and sleep quality significantly impact symptoms
• Most episodes resolve within 2-4 weeks with appropriate management
            """.strip(),
            "patient_education": """
**What is Neck Pain?**
Neck pain (cervicalgia) is pain in the cervical spine area. It can range from mild stiffness to severe pain that limits movement.

**Common Causes:**
- Poor posture (especially computer work)
- Sleeping in awkward positions
- Sudden movements or whiplash
- Stress and muscle tension
- Arthritis or disc problems

**Self-Care Tips:**
- Apply heat or cold therapy
- Gentle neck movements and stretches
- Improve workstation ergonomics
- Manage stress levels
- Ensure proper pillow support while sleeping
            """.strip(),
            "red_flags": """
🚨 **Seek immediate medical attention if:**
• Severe headache with neck stiffness and fever
• Neck pain after significant trauma
• Severe arm weakness or numbness
• Difficulty swallowing or speaking
• Severe pain that doesn't respond to position changes

⚠️ **See your doctor if:**
• Persistent numbness or tingling in arms/hands
• Headaches that are getting worse
• Pain radiating down both arms
• No improvement after 2 weeks of self-care
            """.strip(),
            "faq_data": """[
                {
                    "question": "Is it safe to crack my neck?",
                    "answer": "Gentle self-mobilization is usually safe, but avoid forceful manipulation. If you feel the need to crack your neck frequently, see a professional."
                },
                {
                    "question": "What's the best sleeping position for neck pain?",
                    "answer": "Sleep on your back or side with proper pillow support. Avoid sleeping on your stomach as this can strain the neck."
                },
                {
                    "question": "How can I improve my computer workstation?",
                    "answer": "Monitor at eye level, keyboard and mouse at elbow height, feet flat on floor, and take regular breaks every 30-60 minutes."
                },
                {
                    "question": "When should I be concerned about headaches with neck pain?",
                    "answer": "Seek medical attention if headaches are severe, sudden onset, or accompanied by fever, vision changes, or neurological symptoms."
                }
            ]"""
        },
        {
            "name": "TMJ Dysfunction",
            "clinical_pearls": """
• Affects 5-12% of the population, more common in women
• Often multifactorial: stress, bruxism, trauma, arthritis
• Symptoms may fluctuate and can be episodic
• Strong association with stress and anxiety
• May be related to cervical spine dysfunction
• Conservative treatment is successful in 80-90% of cases
            """.strip(),
            "patient_education": """
**What is TMJ Dysfunction?**
TMJ (temporomandibular joint) dysfunction affects the jaw joint and surrounding muscles, causing pain and limited jaw movement.

**Common Symptoms:**
- Jaw pain or tenderness
- Clicking or popping sounds
- Limited jaw opening
- Muscle tension in jaw, neck, or face
- Headaches or earaches

**Self-Management:**
- Eat soft foods and avoid excessive chewing
- Apply heat or cold to the jaw area
- Practice stress management techniques
- Avoid clenching or grinding teeth
- Gentle jaw exercises as advised
            """.strip(),
            "red_flags": """
🚨 **Seek immediate medical attention if:**
• Jaw locked in open or closed position
• Severe pain after trauma to the face/jaw
• Signs of infection (fever, swelling, pus)
• Sudden severe headache with jaw pain

⚠️ **See your dentist or doctor if:**
• Persistent jaw locking or catching
• Severe limitation in jaw opening
• Chronic grinding or clenching
• Symptoms interfering with eating or speaking
• No improvement after 2-3 weeks of self-care
            """.strip(),
            "faq_data": """[
                {
                    "question": "Will I need surgery for TMJ problems?",
                    "answer": "Surgery is rarely needed. Most TMJ problems respond well to conservative treatment including physiotherapy, stress management, and sometimes a bite guard."
                },
                {
                    "question": "Should I wear a mouth guard?",
                    "answer": "A properly fitted bite guard can help if you grind or clench your teeth, especially at night. Consult your dentist for a custom-fitted guard."
                },
                {
                    "question": "What foods should I avoid?",
                    "answer": "Avoid hard, chewy, or large foods that require wide jaw opening. Stick to soft foods during flare-ups and cut food into smaller pieces."
                },
                {
                    "question": "Is TMJ dysfunction related to stress?",
                    "answer": "Yes, stress often contributes to TMJ problems through increased muscle tension and teeth clenching. Stress management is an important part of treatment."
                }
            ]"""
        },
        {
            "name": "Tennis Elbow",
            "clinical_pearls": """
• Lateral epicondylitis affects 1-3% of the population
• Peak incidence in 40-50 year olds
• Only 5% of cases are actually related to tennis
• Often caused by repetitive wrist/forearm activities
• Eccentric strengthening exercises are highly effective
• Symptoms may persist 6-24 months if untreated
            """.strip(),
            "patient_education": """
**What is Tennis Elbow?**
Tennis elbow (lateral epicondylitis) is pain and inflammation of the tendons that attach to the outside of the elbow, caused by overuse of forearm muscles.

**Common Causes:**
- Repetitive wrist and arm motions
- Computer work and typing
- Manual labor or sports activities
- Poor technique in racquet sports
- Sudden increase in activity level

**Recovery Tips:**
- Rest from aggravating activities
- Apply ice after activities
- Gentle stretching and strengthening exercises
- Modify activities and technique
- Use proper equipment and ergonomics
            """.strip(),
            "red_flags": """
🚨 **Seek immediate medical attention if:**
• Severe elbow pain after trauma
• Signs of infection (fever, warmth, redness, swelling)
• Complete inability to move the elbow
• Severe weakness in the hand or wrist

⚠️ **See your doctor if:**
• Persistent numbness or tingling in the hand
• Severe pain that doesn't respond to rest and medication
• Symptoms interfering significantly with daily activities
• No improvement after 6-8 weeks of conservative treatment
            """.strip(),
            "faq_data": """[
                {
                    "question": "How long does tennis elbow take to heal?",
                    "answer": "Most cases resolve within 6-12 months with proper treatment. Early intervention and activity modification can speed recovery."
                },
                {
                    "question": "Can I continue working with tennis elbow?",
                    "answer": "You may need to modify activities that aggravate symptoms. Ergonomic improvements and frequent breaks can help you continue working."
                },
                {
                    "question": "Should I wear an elbow brace?",
                    "answer": "A forearm strap or brace may help reduce symptoms during activities, but it's not a cure. Focus on addressing the underlying causes."
                },
                {
                    "question": "Will I need a cortisone injection?",
                    "answer": "Injections may provide short-term relief but don't address the underlying problem. Exercise therapy is more effective for long-term recovery."
                }
            ]"""
        }
    ]
    
    added_count = 0
    for guide_data in guides_data:
        existing = PathologyGuide.query.filter_by(name=guide_data["name"]).first()
        if not existing:
            # Find matching diagnosis template
            template = DiagnosisTemplate.query.filter_by(name=guide_data["name"]).first()
            
            guide = PathologyGuide(
                name=guide_data["name"],
                clinical_pearls=guide_data["clinical_pearls"],
                patient_education=guide_data["patient_education"],
                red_flags=guide_data["red_flags"],
                faq_data=guide_data["faq_data"],
                diagnosis_template_id=template.id if template else None
            )
            db.session.add(guide)
            added_count += 1
            print(f"  ✅ Added guide: {guide_data['name']}")
        else:
            print(f"  ⚠️  Guide exists: {guide_data['name']}")
    
    if added_count > 0:
        db.session.commit()
        print(f"✅ Added {added_count} pathology guides")
    else:
        print("ℹ️  All pathology guides already exist")
    
    return True

def add_test_diagnoses():
    """Add test diagnoses to patient for testing"""
    print("👤 Adding test diagnoses...")
    
    # Find a patient to add diagnoses to (try patient 1 first, then any patient)
    from app.models import Patient
    
    test_patient = Patient.query.first()
    if not test_patient:
        print("❌ No patients found in database")
        return False
    
    patient_id = test_patient.id
    print(f"  Using patient ID: {patient_id}")
    
    # Get ICD-10 codes for pathology guides
    test_codes = ["M72.2", "M75.0", "M54.5", "M54.2", "M26.61"]
    
    added_count = 0
    for code in test_codes:
        icd10_code = ICD10Code.query.filter_by(code=code).first()
        if icd10_code:
            # Check if diagnosis already exists
            existing = PatientDiagnosis.query.filter_by(
                patient_id=patient_id,
                icd10_code_id=icd10_code.id
            ).first()
            
            if not existing:
                diagnosis = PatientDiagnosis(
                    patient_id=patient_id,
                    icd10_code_id=icd10_code.id,
                    diagnosis_type='primary',
                    status='active',
                    confidence_level='confirmed',
                    severity='moderate',
                    diagnosis_date=date.today(),
                    clinical_notes=f'Test diagnosis for pathology guide: {icd10_code.short_description}'
                )
                db.session.add(diagnosis)
                added_count += 1
                print(f"  ✅ Added: {icd10_code.short_description} ({code})")
            else:
                print(f"  ⚠️  Exists: {icd10_code.short_description} ({code})")
    
    if added_count > 0:
        db.session.commit()
        print(f"✅ Added {added_count} test diagnoses to patient {patient_id}")
    else:
        print("ℹ️  All test diagnoses already exist")
    
    return True

def main():
    """Main setup function"""
    print("🚀 PythonAnywhere Pathology Guide Setup")
    print("=" * 50)
    
    app = create_app()
    
    with app.app_context():
        try:
            # Step 1: Create tables
            if not create_tables():
                print("❌ Failed to create tables")
                return False
            
            # Step 2: Seed ICD-10 codes
            if not seed_icd10_codes():
                print("❌ Failed to seed ICD-10 codes")
                return False
            
            # Step 3: Seed diagnosis templates
            if not seed_diagnosis_templates():
                print("❌ Failed to seed diagnosis templates")
                return False
            
            # Step 4: Seed pathology guides
            if not seed_pathology_guides():
                print("❌ Failed to seed pathology guides")
                return False
            
            # Step 5: Add test diagnoses
            if not add_test_diagnoses():
                print("❌ Failed to add test diagnoses")
                return False
            
            print("\n🎉 Setup completed successfully!")
            print("\n📋 Summary:")
            print(f"  ICD-10 codes: {ICD10Code.query.count()}")
            print(f"  Diagnosis templates: {DiagnosisTemplate.query.count()}")
            print(f"  Pathology guides: {PathologyGuide.query.count()}")
            print(f"  Patient diagnoses: {PatientDiagnosis.query.count()}")
            
            print("\n🎯 Next steps:")
            print("  1. Visit your website")
            print("  2. Go to a patient with diagnoses")
            print("  3. Look for 'Info' buttons next to diagnoses")
            print("  4. Click 'Info' to see pathology guides!")
            
            return True
            
        except Exception as e:
            print(f"❌ Setup failed: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
