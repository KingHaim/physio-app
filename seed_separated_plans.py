import os
from app import create_app, db
from app.models import Plan

# Define the separated plan structures
INDIVIDUAL_PLANS = [
    {
        "name": "Individual",
        "slug": "individual-usd",
        "plan_type": "individual",
        "price_cents": 1000, # $10.00 USD
        "billing_interval": "month",
        "currency": "usd",
        "patient_limit": 100,  # Generous limit for individual practitioners
        "practitioner_limit": 1,
        "features": {
            "description": "Perfect for solo practitioners",
            "patient_management": "core",
            "scheduling": "advanced",
            "clinical_notes": "advanced",
            "billing": "advanced",
            "reporting": "advanced",
            "calendly_integration": True,
            "patient_portal": True,
            "telehealth": "basic",
            "analytics": "standard",
            "ai_insights": True,
            "support": "email"
        },
        "stripe_price_id": "price_individual_usd_10", # NEW - To be created in Stripe
        "is_active": True,
        "display_order": 1
    }
]

CLINIC_PLANS = [
    {
        "name": "Clinic",
        "slug": "clinic-usd",
        "plan_type": "clinic",
        "price_cents": 4000, # $40.00 USD
        "billing_interval": "month",
        "currency": "usd",
        "patient_limit": None, # Unlimited patients
        "practitioner_limit": None, # Unlimited practitioners
        "features": {
            "description": "Perfect for multi-practitioner clinics",
            "patient_management": "core",
            "scheduling": "advanced",
            "clinical_notes": "advanced",
            "billing": "advanced",
            "reporting": "advanced",
            "calendly_integration": True,
            "patient_portal": True,
            "telehealth": "advanced",
            "multi_practitioner_calendars": True,
            "clinic_management": True,
            "practitioner_permissions": True,
            "multi_location_support": True,
            "ai_driven_insights": True,
            "wearable_integration": True,
            "api_access": True,
            "custom_branding": True,
            "analytics": "advanced",
            "support": "priority_email"
        },
        "stripe_price_id": "price_clinic_usd_40", # NEW - To be created in Stripe
        "is_active": True,
        "display_order": 1
    }
]

def seed_separated_plans():
    """Seed the database with separated Individual and Clinic plans"""
    app = create_app()
    with app.app_context():
        print("Starting to seed separated plans...")
        
        # Deactivate all existing plans first
        print("Deactivating all existing plans...")
        existing_plans = Plan.query.all()
        for plan in existing_plans:
            plan.is_active = False
        db.session.commit()
        print(f"{len(existing_plans)} existing plans marked as inactive.")

        # Create Individual plans
        print("\nCreating Individual plans...")
        for plan_data in INDIVIDUAL_PLANS:
            existing_plan = Plan.query.filter_by(slug=plan_data["slug"]).first()
            
            if existing_plan:
                print(f"Updating existing Individual plan: {plan_data['name']}")
                for key, value in plan_data.items():
                    setattr(existing_plan, key, value)
            else:
                print(f"Creating new Individual plan: {plan_data['name']}")
                new_plan = Plan(**plan_data)
                db.session.add(new_plan)
        
        # Create Clinic plans
        print("\nCreating Clinic plans...")
        for plan_data in CLINIC_PLANS:
            existing_plan = Plan.query.filter_by(slug=plan_data["slug"]).first()
            
            if existing_plan:
                print(f"Updating existing Clinic plan: {plan_data['name']}")
                for key, value in plan_data.items():
                    setattr(existing_plan, key, value)
            else:
                print(f"Creating new Clinic plan: {plan_data['name']}")
                new_plan = Plan(**plan_data)
                db.session.add(new_plan)

        db.session.commit()
        print("\n✅ Successfully seeded separated plans!")
        
        # Print summary
        individual_plans = Plan.query.filter_by(plan_type='individual', is_active=True).all()
        clinic_plans = Plan.query.filter_by(plan_type='clinic', is_active=True).all()
        
        print(f"\n📊 Summary:")
        print(f"Individual Plans: {len(individual_plans)}")
        for plan in individual_plans:
            print(f"  - {plan.name}: ${plan.price_cents/100:.2f}/{plan.billing_interval}")
        
        print(f"Clinic Plans: {len(clinic_plans)}")
        for plan in clinic_plans:
            print(f"  - {plan.name}: ${plan.price_cents/100:.2f}/{plan.billing_interval}")

if __name__ == '__main__':
    seed_separated_plans() 