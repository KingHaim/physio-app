import os
from app import create_app, db
from app.models import Plan

# Define the NEW individual plans for live mode
INDIVIDUAL_PLANS_DATA = [
    {
        "name": "Individual Monthly",
        "slug": "individual-monthly",
        "plan_type": "individual",
        "price_cents": 1500,  # $15.00 USD - adjust as needed
        "billing_interval": "month",
        "currency": "usd",
        "patient_limit": 50,
        "practitioner_limit": 1,
        "features": {
            "description": "Perfect for solo practitioners - monthly billing",
            "patient_management": "core",
            "scheduling": "standard",
            "clinical_notes": "standard",
            "billing": "basic",
            "reporting": "basic",
            "calendly_integration": True,
            "support": "email"
        },
        "stripe_price_id": "price_1QNLS8P9VzR6WBM9QPDKMInq",  # Your live monthly price ID
        "is_active": True,
        "display_order": 1
    },
    {
        "name": "Individual Yearly",
        "slug": "individual-yearly", 
        "plan_type": "individual",
        "price_cents": 15000,  # $150.00 USD (10 months pricing) - adjust as needed
        "billing_interval": "year",
        "currency": "usd",
        "patient_limit": 50,
        "practitioner_limit": 1,
        "features": {
            "description": "Perfect for solo practitioners - yearly billing with savings",
            "patient_management": "core",
            "scheduling": "standard", 
            "clinical_notes": "standard",
            "billing": "basic",
            "reporting": "basic",
            "calendly_integration": True,
            "support": "email"
        },
        "stripe_price_id": "price_1RMDzDP9VzR6WBM9re7nv8HK",  # Your live yearly price ID
        "is_active": True,
        "display_order": 2
    }
]

def seed_individual_plans():
    """Seed individual plans for live mode"""
    app = create_app()
    with app.app_context():
        print("🚀 Setting up Individual Plans for Live Mode")
        print("=" * 50)
        
        # Deactivate all existing plans first
        print("🔄 Deactivating all existing plans...")
        all_db_plans = Plan.query.all()
        for db_plan in all_db_plans:
            db_plan.is_active = False
        db.session.commit()
        print(f"✅ {len(all_db_plans)} existing plans marked as inactive.")

        # Create or update individual plans
        for plan_data in INDIVIDUAL_PLANS_DATA:
            existing_plan = Plan.query.filter_by(slug=plan_data["slug"]).first()

            if existing_plan:
                # Update existing plan
                print(f"🔄 Updating existing plan: {plan_data['name']}")
                existing_plan.name = plan_data["name"]
                existing_plan.plan_type = plan_data["plan_type"]
                existing_plan.price_cents = plan_data["price_cents"]
                existing_plan.billing_interval = plan_data["billing_interval"]
                existing_plan.currency = plan_data["currency"]
                existing_plan.patient_limit = plan_data["patient_limit"]
                existing_plan.practitioner_limit = plan_data["practitioner_limit"]
                existing_plan.features = plan_data["features"]
                existing_plan.stripe_price_id = plan_data["stripe_price_id"]
                existing_plan.is_active = plan_data["is_active"]
                existing_plan.display_order = plan_data["display_order"]
                print(f"✅ Updated: {existing_plan.name} - ${existing_plan.price_cents/100:.2f}/{existing_plan.billing_interval}")
            else:
                # Create new plan
                print(f"➕ Creating new plan: {plan_data['name']}")
                new_plan = Plan(
                    name=plan_data["name"],
                    slug=plan_data["slug"],
                    plan_type=plan_data["plan_type"],
                    price_cents=plan_data["price_cents"],
                    billing_interval=plan_data["billing_interval"],
                    currency=plan_data["currency"],
                    patient_limit=plan_data["patient_limit"],
                    practitioner_limit=plan_data["practitioner_limit"],
                    features=plan_data["features"],
                    stripe_price_id=plan_data["stripe_price_id"],
                    is_active=plan_data["is_active"],
                    display_order=plan_data["display_order"]
                )
                db.session.add(new_plan)
                print(f"✅ Created: {new_plan.name} - ${new_plan.price_cents/100:.2f}/{new_plan.billing_interval}")
            
        db.session.commit()
        
        # Display summary
        print("\n📊 Active Plans Summary:")
        print("-" * 30)
        active_plans = Plan.query.filter_by(is_active=True).order_by(Plan.display_order).all()
        for plan in active_plans:
            print(f"• {plan.name}: ${plan.price_cents/100:.2f}/{plan.billing_interval}")
            print(f"  Stripe Price ID: {plan.stripe_price_id}")
            print(f"  Patient Limit: {plan.patient_limit}")
            print()
        
        print("🎉 Individual plans setup completed for LIVE MODE!")
        print("💡 Note: Clinic plans will be available later as planned.")

if __name__ == "__main__":
    seed_individual_plans() 