#!/usr/bin/env python3
"""
Seed Pathology Guides with rich clinical content
Provides clinical pearls, patient education, red flags, and FAQs
"""

import sqlite3
import json
import os

def seed_pathology_guides():
    """
    Seeds rich educational content, FAQs, and Red Flags linked to specific diagnoses.
    This enables the 'Click for Info' feature.
    """
    
    db_path = 'instance/app.db'
    if not os.path.exists(db_path):
        print("❌ Database file not found!")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        guides_data = [
            {
                "name": "Plantar Fasciitis",
                "clinical_pearls": "Look for the 'Windlass Mechanism' sign. Pain is classically worst with the first few steps in the morning. Distinct from nerve entrapment (Baxter's nerve) which usually burns.",
                "patient_education": "The plantar fascia is a thick band of tissue connecting your heel to your toes. Micro-tears have occurred, causing inflammation. It heals overnight in a shortened position, which is why stretching it first thing in the morning hurts.",
                "red_flags": "Unrelenting night pain (calcaneal stress fracture), systemic inflammatory signs (Reiter's syndrome), bilateral presentation in young males (Ankylosing Spondylitis).",
                "anatomy_overview": "The plantar fascia is a thick fibrous band that supports the arch of the foot. It originates from the medial calcaneal tuberosity and inserts into the plantar plates of the metatarsophalangeal joints.",
                "treatment_phases": "Phase 1: Pain control and inflammation reduction (0-2 weeks). Phase 2: Mobility and gentle strengthening (2-6 weeks). Phase 3: Progressive loading and return to activity (6+ weeks).",
                "home_exercises": "1. Calf stretches (gastrocnemius and soleus). 2. Plantar fascia stretch with towel. 3. Toe curls and marble pickups. 4. Calf raises progression.",
                "faq_data": [
                    {"q": "How long does this take to heal?", "a": "It can be stubborn. Typically 3 to 6 months, though 80% improve significantly within 6 weeks of consistent exercise."},
                    {"q": "Should I stop walking/running?", "a": "You don't need to stop completely, but we need to reduce volume. If pain exceeds 3/10 during activity, stop."},
                    {"q": "Do I need an injection?", "a": "Cortisone is usually a last resort as it can weaken the tissue. We prefer loading exercises first."},
                    {"q": "What shoes should I wear?", "a": "Supportive shoes with good arch support. Avoid walking barefoot, especially on hard surfaces."},
                    {"q": "Can I use ice?", "a": "Ice can help with acute pain, but don't rely on it long-term. Movement and exercise are more important for healing."}
                ]
            },
            {
                "name": "Jones Fracture (5th Metatarsal)",
                "clinical_pearls": "Zone 2 fracture. High rate of non-union due to poor blood supply. Aggressive early weight bearing is contraindicated.",
                "patient_education": "You have broken the bone on the outside of your foot. This specific area has poor blood flow, so it takes longer to heal than other foot bones.",
                "red_flags": "Pain not improving after 4 weeks of immobilization. Refracture after return to sport. Signs of non-union on X-ray.",
                "anatomy_overview": "The 5th metatarsal has three zones. Zone 2 (Jones fracture) occurs at the metaphyseal-diaphyseal junction and has the poorest blood supply, making healing challenging.",
                "treatment_phases": "Phase 1: Immobilization and non-weight bearing (0-6 weeks). Phase 2: Progressive weight bearing in boot (6-10 weeks). Phase 3: Return to normal activities (10+ weeks).",
                "home_exercises": "During immobilization: Upper body and core exercises, seated exercises. Post-immobilization: Ankle pumps, toe movements, progressive weight bearing exercises.",
                "faq_data": [
                    {"q": "Why do I need a boot?", "a": "To stop the tendon from pulling the bone fragment apart every time you step."},
                    {"q": "When can I drive?", "a": "If it's your right foot, not until you are out of the boot and can perform an emergency stop without pain (approx 6-8 weeks)."},
                    {"q": "Will I need surgery?", "a": "If the gap doesn't close on X-ray after 6 weeks, a screw fixation is often recommended, especially for athletes."},
                    {"q": "Can I swim?", "a": "Yes, once the boot is off and you can tolerate gentle kicking. Swimming is excellent for maintaining fitness."},
                    {"q": "When can I return to sports?", "a": "Typically 12-16 weeks, but only after X-ray shows complete healing and you've completed a return-to-sport program."}
                ]
            },
            {
                "name": "TMJ Dysfunction",
                "clinical_pearls": "Assess C-Spine (C1-C3) as it often refers pain to the jaw. Check for deviation on opening (C-curve vs S-curve). Night grinding (bruxism) is a major contributing factor.",
                "patient_education": "The joint connecting your jaw to your skull is irritated. This often relates to clenching your teeth at night (bruxism) or neck tension. Stress and poor posture can make it worse.",
                "red_flags": "Locking (unable to open or close mouth), swelling due to dental infection, history of trauma/fracture. Sudden onset with severe pain may indicate disc displacement.",
                "anatomy_overview": "The temporomandibular joint is a synovial joint with an articular disc. It allows both hinge and sliding movements. The joint is closely related to cervical spine mechanics.",
                "treatment_phases": "Phase 1: Pain reduction and muscle relaxation (0-2 weeks). Phase 2: Mobility and postural correction (2-6 weeks). Phase 3: Strengthening and habit modification (6+ weeks).",
                "home_exercises": "1. Gentle jaw opening exercises. 2. Neck stretches and strengthening. 3. Posture correction exercises. 4. Relaxation techniques for stress management.",
                "faq_data": [
                    {"q": "Is it arthritis?", "a": "It can be, but often it is muscular or a disc displacement issue which is very treatable."},
                    {"q": "Do I need a night guard?", "a": "We will assess if you grind your teeth. If so, a splint from your dentist helps protect the joint while you sleep."},
                    {"q": "Should I avoid hard foods?", "a": "Yes, temporarily avoid gum, hard candies, and tough meats. Cut food into smaller pieces."},
                    {"q": "Can stress cause this?", "a": "Absolutely. Stress often leads to jaw clenching and muscle tension. Stress management is part of treatment."},
                    {"q": "Will it go away on its own?", "a": "Some cases resolve naturally, but treatment significantly speeds recovery and prevents recurrence."}
                ]
            },
            {
                "name": "Post-Op ACL Reconstruction",
                "clinical_pearls": "Extension is the priority! A flexed knee scars down quickly. Watch for Cyclops lesion if terminal extension is painful/blocked. The graft is weakest at 6-12 weeks (remodeling phase).",
                "patient_education": "We are rebuilding the stability of your knee. The graft is actually weakest between weeks 6 and 12 (remodeling phase), so do not push ahead of schedule even if it feels good.",
                "red_flags": "Signs of DVT (calf heat/redness), infection (fever/oozing), loss of extension range. Giving way or instability may indicate graft failure.",
                "anatomy_overview": "The ACL prevents forward translation of the tibia on the femur. The reconstruction uses a tendon graft (often hamstring or patellar tendon) to restore this function.",
                "treatment_phases": "Phase 1: Protection and early motion (0-6 weeks). Phase 2: Strengthening and proprioception (6-12 weeks). Phase 3: Advanced strengthening (3-6 months). Phase 4: Return to sport (6+ months).",
                "home_exercises": "Early: Ankle pumps, quad sets, heel slides. Later: Straight leg raises, mini squats, balance exercises. Advanced: Plyometrics and sport-specific drills.",
                "faq_data": [
                    {"q": "When can I run?", "a": "Typically at 12 weeks, provided your quad strength is 80% of the other leg and you have no swelling."},
                    {"q": "Why is my knee still numb?", "a": "The saphenous nerve is often retracted during surgery. A patch of numbness on the outside of the shin is normal and usually permanent."},
                    {"q": "When can I play football/soccer?", "a": "Return to sport is criteria-based, not time-based, but rarely before 9 months."},
                    {"q": "Can I kneel?", "a": "Kneeling may always be uncomfortable due to scar tissue, but it won't damage the reconstruction."},
                    {"q": "Will my knee ever be 100% normal?", "a": "Most people return to full activity, but some notice minor differences in sensation or weather sensitivity."}
                ]
            },
            {
                "name": "BPPV (Vertigo)",
                "clinical_pearls": "Posterior canal BPPV is most common (85%). Dix-Hallpike test is diagnostic. Epley maneuver has 80% success rate in one session. Always check for central causes if atypical presentation.",
                "patient_education": "You have loose crystals in your inner ear that are triggering false signals about movement. This is very treatable with specific head movements that relocate the crystals.",
                "red_flags": "Continuous vertigo (not positional), hearing loss, neurological symptoms, severe headache. These may indicate central vertigo requiring urgent medical attention.",
                "anatomy_overview": "The inner ear contains semicircular canals filled with fluid and crystals (otoconia). When crystals become displaced, they trigger false movement signals.",
                "treatment_phases": "Phase 1: Crystal repositioning (1-2 sessions). Phase 2: Habituation exercises if needed (1-2 weeks). Phase 3: Balance retraining if residual symptoms.",
                "home_exercises": "Brandt-Daroff exercises for habituation. Gaze stabilization exercises. Balance training on various surfaces. Avoid prolonged bed rest.",
                "faq_data": [
                    {"q": "Will it come back?", "a": "About 15% of people have recurrence within one year, but it's easily treated again."},
                    {"q": "Can I drive?", "a": "Not while symptomatic. Wait 24-48 hours after successful treatment before driving."},
                    {"q": "Should I avoid certain movements?", "a": "Initially yes, but gradual return to normal head movements is important to prevent recurrence."},
                    {"q": "Is it dangerous?", "a": "BPPV itself isn't dangerous, but the sudden dizziness can cause falls. Take precautions until treated."},
                    {"q": "Can stress cause this?", "a": "Stress doesn't directly cause BPPV, but it can make symptoms feel worse and delay recovery."}
                ]
            },
            {
                "name": "Total Knee Arthroplasty (TKA)",
                "clinical_pearls": "Early mobilization is key. Watch for signs of infection (increased warmth, redness, drainage). Posterior capsule tightness is common - focus on extension. DVT risk is highest in first 6 weeks.",
                "patient_education": "You have a new knee joint made of metal and plastic. The surrounding muscles and tissues need to adapt to this change. Full recovery takes 3-6 months, but most daily activities resume much sooner.",
                "red_flags": "Signs of infection (fever, increased pain, drainage, red streaking), signs of DVT (calf pain/swelling), loss of previously gained motion, severe persistent pain.",
                "anatomy_overview": "Total knee replacement involves replacing the damaged joint surfaces with metal and plastic components. The surrounding ligaments and muscles provide stability.",
                "treatment_phases": "Phase 1: Early mobilization and pain control (0-6 weeks). Phase 2: Range of motion and basic strengthening (6-12 weeks). Phase 3: Advanced strengthening and return to activities (3+ months).",
                "home_exercises": "Early: Ankle pumps, quad sets, heel slides, gentle walking. Later: Stationary bike, leg presses, balance exercises. Advanced: Stair climbing, recreational activities.",
                "faq_data": [
                    {"q": "How much pain is normal?", "a": "Significant pain is expected for 6-8 weeks, but it should gradually improve. Sudden increases in pain need evaluation."},
                    {"q": "When can I drive?", "a": "Usually 4-6 weeks, when you can safely operate the pedals and have good reaction time."},
                    {"q": "Will I set off metal detectors?", "a": "Possibly. Your surgeon can provide a card explaining your implant."},
                    {"q": "Can I kneel?", "a": "Many people can kneel, but it may always feel different. Use knee pads for comfort."},
                    {"q": "How long will it last?", "a": "Modern implants typically last 15-20 years or more with proper care and activity modification."}
                ]
            },
            {
                "name": "Osgood-Schlatter Disease",
                "clinical_pearls": "Traction apophysitis at tibial tuberosity. Most common in active adolescents during growth spurts. Usually self-limiting but can be very painful. Bilateral in 25% of cases.",
                "patient_education": "This is a growing pain where the tendon pulls on the growth plate below your kneecap. It's very common in active teenagers and will resolve when you finish growing.",
                "red_flags": "Severe constant pain (may indicate avulsion fracture), inability to bear weight, signs of infection. Pain in non-active child may indicate other pathology.",
                "anatomy_overview": "The patellar tendon attaches to the tibial tuberosity (growth plate). During growth spurts, repetitive traction can cause inflammation and pain at this attachment site.",
                "treatment_phases": "Phase 1: Activity modification and pain control (2-4 weeks). Phase 2: Gradual return to activity with strengthening (4-8 weeks). Phase 3: Full activity with maintenance exercises.",
                "home_exercises": "Quadriceps stretching, hamstring stretching, hip flexor stretches. Strengthening: Hip abductors, glutes, eccentric quad exercises (when pain allows).",
                "faq_data": [
                    {"q": "Do I have to stop sports?", "a": "Not necessarily, but you may need to reduce intensity. Pain should guide activity level."},
                    {"q": "Will the bump go away?", "a": "The bony prominence often remains but becomes painless once growth is complete."},
                    {"q": "How long does this last?", "a": "Usually resolves within 12-24 months as growth slows down."},
                    {"q": "Can I make it worse?", "a": "Continuing high-impact activities through severe pain can prolong symptoms."},
                    {"q": "Should I use ice?", "a": "Ice after activity can help with pain and swelling, especially after sports."}
                ]
            }
        ]
        
        print(f"🔄 Seeding {len(guides_data)} Pathology Guides...")
        
        for data in guides_data:
            # Find the linked template first
            cursor.execute("SELECT id FROM diagnosis_templates WHERE name = ?", (data["name"],))
            template_result = cursor.fetchone()
            
            if not template_result:
                print(f"  ⚠️  Skipping Guide: Template '{data['name']}' not found.")
                continue
            
            template_id = template_result[0]
            
            # Check if guide already exists
            cursor.execute("SELECT id FROM pathology_guides WHERE name = ?", (data["name"],))
            existing_guide = cursor.fetchone()
            
            # Convert FAQ data to JSON string
            faq_json = json.dumps(data["faq_data"])
            
            if existing_guide:
                print(f"  🔄 Updating guide for: {data['name']}")
                cursor.execute('''
                    UPDATE pathology_guides 
                    SET clinical_pearls = ?, patient_education = ?, red_flags = ?, 
                        faq_data = ?, anatomy_overview = ?, treatment_phases = ?, 
                        home_exercises = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                ''', (
                    data["clinical_pearls"], data["patient_education"], data["red_flags"],
                    faq_json, data["anatomy_overview"], data["treatment_phases"],
                    data["home_exercises"], data["name"]
                ))
            else:
                print(f"  ✅ Creating new guide for: {data['name']}")
                cursor.execute('''
                    INSERT INTO pathology_guides 
                    (name, clinical_pearls, patient_education, red_flags, faq_data, 
                     anatomy_overview, treatment_phases, home_exercises, diagnosis_template_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data["name"], data["clinical_pearls"], data["patient_education"], 
                    data["red_flags"], faq_json, data["anatomy_overview"], 
                    data["treatment_phases"], data["home_exercises"], template_id
                ))
        
        conn.commit()
        
        # Verify seeding
        cursor.execute("SELECT COUNT(*) FROM pathology_guides")
        total_guides = cursor.fetchone()[0]
        
        print(f"✅ Pathology Guides seeded successfully!")
        print(f"📊 Total guides in database: {total_guides}")
        
        # Show sample of what was created
        cursor.execute("SELECT name, diagnosis_template_id FROM pathology_guides LIMIT 5")
        samples = cursor.fetchall()
        print(f"📋 Sample guides:")
        for name, template_id in samples:
            print(f"  - {name} (Template ID: {template_id})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error seeding pathology guides: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("PATHOLOGY GUIDES SEEDING")
    print("=" * 60)
    
    if seed_pathology_guides():
        print("\n✅ SEEDING COMPLETED!")
        print("Next step: Create UI components for displaying guides")
    else:
        print("\n❌ SEEDING FAILED!")
    
    print("=" * 60)
