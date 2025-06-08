from app import create_app, db
from app.models import Plan

def check_plans():
    app = create_app()
    with app.app_context():
        plans = Plan.query.filter_by(is_active=True).all()
        
        print(f"Found {len(plans)} active plans in the database:")
        print("-" * 50)
        
        if not plans:
            print("❌ No active plans found!")
            print("You need to run: python seed_plans.py")
        else:
            for plan in plans:
                print(f"✅ {plan.name}")
                print(f"   - Price: ${plan.price_cents/100:.2f}/{plan.billing_interval}")
                print(f"   - Slug: {plan.slug}")
                print(f"   - Patient Limit: {plan.patient_limit or 'Unlimited'}")
                print(f"   - Stripe Price ID: {plan.stripe_price_id or 'None'}")
                print()

if __name__ == "__main__":
    check_plans() 