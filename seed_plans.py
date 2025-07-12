import os
from app import create_app, db
from app.models import Plan

# Define the plans to be created, aligned with the new Plan model and pricing strategy
PLANS_DATA = [
    # Removed Solo Free plan - now offering 14-day trials for all paid plans instead
    {
        "name": "Basic", # Changed from "Basic Monthly"
        "slug": "basic-usd", # New slug to ensure it's treated as a new plan if "basic-monthly" existed
        "price_cents": 1500, # $15.00 USD
        "billing_interval": "month",
        "currency": "usd", # Changed from eur
        "patient_limit": 50, # Increased from 10
        "practitioner_limit": 1, # Added
        "features": {
            "description": "For solo practitioners needing essential tools and more capacity.",
            "patient_management": "core",
            "scheduling": "standard",
            "clinical_notes": "standard",
            "billing": "basic",
            "reporting": "basic",
            "calendly_integration": True,
            "support": "email"
        },
        "stripe_price_id": "price_1RTfP7P5aPDx5xda6UyIUt5m", # <<< UPDATED
        "is_active": True,
        "display_order": 1
    },
    {
        "name": "Standard", # New Plan
        "slug": "standard-usd", # New slug
        "price_cents": 3000, # $30.00 USD
        "billing_interval": "month",
        "currency": "usd",
        "patient_limit": 250, 
        "practitioner_limit": 5,
        "features": {
            "description": "For small clinics needing collaboration, patient engagement, and telehealth.",
            "patient_management": "core",
            "scheduling": "advanced",
            "clinical_notes": "standard",
            "billing": "standard",
            "reporting": "standard",
            "calendly_integration": True,
            "patient_portal": True,
            "telehealth": "basic",
            "analytics": "standard",
            "multi_practitioner_calendars": True,
            "support": "priority_email"
        },
        "stripe_price_id": "price_1RTfQVP5aPDx5xdaF9wAvecI", # <<< UPDATED
        "is_active": True,
        "display_order": 2
    },
    {
        "name": "Premium", # Changed from "Pro Monthly"
        "slug": "premium-usd", # New slug
        "price_cents": 6000, # $60.00 USD (was 4900 EUR for Pro)
        "billing_interval": "month",
        "currency": "usd", # Changed from eur
        "patient_limit": None, # Unlimited
        "practitioner_limit": None, # For 6+ practitioners
        "features": {
            "description": "For larger clinics wanting advanced insights, integrations, and full scalability.",
            "patient_management": "core",
            "scheduling": "advanced",
            "clinical_notes": "advanced",
            "billing": "advanced",
            "reporting": "advanced_ai", # Includes AI
            "calendly_integration": True,
            "patient_portal": True,
            "telehealth": "advanced",
            "analytics": "advanced",
            "multi_practitioner_calendars": True,
            "ai_driven_insights": True,
            "wearable_integration": True,
            "multi_location_support": True,
            "api_access": True,
            "custom_branding": True,
            "support": "dedicated"
        },
        "stripe_price_id": "price_1RTfR4P5aPDx5xda3UvGfGoz", # <<< UPDATED
        "is_active": True,
        "display_order": 3
    }
    # The "Clinic Monthly" plan has been removed as per the new 3-tier (plus free) structure.
]

def seed_plans():
    app = create_app()
    with app.app_context():
        # Deactivate all existing plans first
        print("Deactivating all existing plans...")
        all_db_plans = Plan.query.all()
        for db_plan in all_db_plans:
            db_plan.is_active = False
        db.session.commit()
        print(f"{len(all_db_plans)} plans marked as inactive.")

        # Now, update or create plans from PLANS_DATA
        for plan_data in PLANS_DATA:
            existing_plan = Plan.query.filter_by(slug=plan_data["slug"]).first()

            if existing_plan:
                # Update existing plan
                print(f"Plan with slug '{plan_data['slug']}' found. Updating and activating...")
                existing_plan.name = plan_data["name"]
                existing_plan.price_cents = plan_data["price_cents"]
                existing_plan.billing_interval = plan_data["billing_interval"]
                existing_plan.currency = plan_data["currency"]
                existing_plan.patient_limit = plan_data["patient_limit"]
                existing_plan.practitioner_limit = plan_data.get("practitioner_limit")
                existing_plan.features = plan_data["features"]
                existing_plan.stripe_price_id = plan_data["stripe_price_id"]
                existing_plan.is_active = plan_data.get("is_active", True) # Ensure it's set to active from PLANS_DATA
                existing_plan.display_order = plan_data.get("display_order", 0)
                print(f"Plan '{existing_plan.name}' (slug: {existing_plan.slug}) updated and set to active: {existing_plan.is_active}.")
            else:
                # Add new plan
                print(f"Adding new plan with slug '{plan_data['slug']}'...")
                new_plan = Plan(
                    name=plan_data["name"],
                    slug=plan_data["slug"],
                    price_cents=plan_data["price_cents"],
                    billing_interval=plan_data["billing_interval"],
                    currency=plan_data["currency"],
                    patient_limit=plan_data["patient_limit"],
                    practitioner_limit=plan_data.get("practitioner_limit"),
                    features=plan_data["features"],
                    stripe_price_id=plan_data["stripe_price_id"],
                    is_active=plan_data.get("is_active", True),
                    display_order=plan_data.get("display_order", 0)
                )
                db.session.add(new_plan)
                print(f"Plan '{new_plan.name}' (slug: {new_plan.slug}) added with active status: {new_plan.is_active}.")
            
        db.session.commit()
        print("Finished seeding/updating plans based on new USD pricing strategy. Only plans in PLANS_DATA should be active.")

if __name__ == "__main__":
    # Ensure environment variables are loaded if your app factory needs them
    # Example: 
    # from dotenv import load_dotenv
    # load_dotenv()
    
    seed_plans() 