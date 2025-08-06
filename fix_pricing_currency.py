#!/usr/bin/env python3
"""
Fix Pricing and Currency to Match Live Stripe Configuration
===========================================================

This script updates the database to match your actual Stripe pricing:
- Monthly: €10.00/month
- Yearly: €90.00/year
"""

import os
from app import create_app, db
from app.models import Plan

def update_pricing():
    """Update database pricing to match live Stripe configuration"""
    
    # Don't initialize Sentry to avoid configuration issues
    os.environ['SENTRY_DSN'] = ''
    
    app = create_app()
    with app.app_context():
        print("🔄 Updating pricing to match live Stripe configuration...")
        print("=" * 55)
        
        # Update Individual Monthly plan
        monthly_plan = Plan.query.filter_by(slug='individual-monthly').first()
        if monthly_plan:
            monthly_plan.price_cents = 1000  # €10.00
            monthly_plan.currency = 'eur'
            print(f"✅ Updated Monthly plan: €{monthly_plan.price_cents/100:.2f}/{monthly_plan.billing_interval}")
        
        # Update Individual Yearly plan  
        yearly_plan = Plan.query.filter_by(slug='individual-yearly').first()
        if yearly_plan:
            yearly_plan.price_cents = 9000  # €90.00
            yearly_plan.currency = 'eur'
            print(f"✅ Updated Yearly plan: €{yearly_plan.price_cents/100:.2f}/{yearly_plan.billing_interval}")
        
        db.session.commit()
        
        # Display final configuration
        print("\n📊 Final Pricing Configuration:")
        print("-" * 35)
        active_plans = Plan.query.filter_by(is_active=True).order_by(Plan.display_order).all()
        for plan in active_plans:
            currency_symbol = "€" if plan.currency == "eur" else "$"
            print(f"• {plan.name}: {currency_symbol}{plan.price_cents/100:.2f}/{plan.billing_interval}")
            print(f"  Stripe Price ID: {plan.stripe_price_id}")
            print(f"  Currency: {plan.currency.upper()}")
        
        print("\n🎉 Pricing updated to match live Stripe configuration!")
        print("💡 Your app is now ready for production deployment!")

if __name__ == "__main__":
    update_pricing() 