#!/usr/bin/env python3
"""
Test Live Stripe Configuration
==============================

This script tests your live Stripe setup to ensure everything is working correctly
before deploying to production.
"""

import os
import stripe
from app import create_app, db
from app.models import Plan

def test_stripe_connection():
    """Test connection to Stripe API with live keys"""
    print("🔗 Testing Stripe API connection...")
    
    try:
        # Test API connection by listing products
        products = stripe.Product.list(limit=5)
        print(f"✅ Successfully connected to Stripe API")
        print(f"📦 Found {len(products.data)} products")
        
        # Look for your specific product
        for product in products.data:
            if product.id == "prod_RFrAVB9sQ8sUHk":
                print(f"✅ Found your product: {product.name} (ID: {product.id})")
                return True
        
        print("⚠️  Your product prod_RFrAVB9sQ8sUHk not found in first 5 products")
        print("   This might be normal if you have many products")
        return True
        
    except stripe.error.AuthenticationError:
        print("❌ Authentication failed - check your STRIPE_SECRET_KEY")
        return False
    except Exception as e:
        print(f"❌ Error connecting to Stripe: {e}")
        return False

def test_price_ids():
    """Test that your live price IDs exist in Stripe"""
    print("\n💰 Testing price IDs...")
    
    live_price_ids = [
        "price_1QNLS8P9VzR6WBM9QPDKMInq",  # Monthly
        "price_1RMDzDP9VzR6WBM9re7nv8HK"   # Yearly
    ]
    
    for price_id in live_price_ids:
        try:
            price = stripe.Price.retrieve(price_id)
            amount = price.unit_amount / 100
            currency = price.currency.upper()
            interval = price.recurring.interval if price.recurring else "one-time"
            print(f"✅ {price_id}: {currency} {amount}/{interval}")
        except Exception as e:
            print(f"❌ Error with price {price_id}: {e}")
            return False
    
    return True

def test_database_plans():
    """Test that database plans are correctly configured"""
    print("\n💾 Testing database plans...")
    
    app = create_app()
    with app.app_context():
        try:
            active_plans = Plan.query.filter_by(is_active=True).all()
            print(f"✅ Found {len(active_plans)} active plans in database")
            
            for plan in active_plans:
                print(f"  • {plan.name}: ${plan.price_cents/100:.2f}/{plan.billing_interval}")
                print(f"    Stripe Price ID: {plan.stripe_price_id}")
                
                # Verify price ID exists in Stripe
                try:
                    stripe_price = stripe.Price.retrieve(plan.stripe_price_id)
                    print(f"    ✅ Price ID verified in Stripe")
                except Exception as e:
                    print(f"    ❌ Price ID not found in Stripe: {e}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Database error: {e}")
            return False

def test_webhook_endpoint():
    """Test webhook endpoint configuration"""
    print("\n🎣 Testing webhook configuration...")
    
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    if webhook_secret and webhook_secret.startswith('whsec_'):
        print(f"✅ Webhook secret configured: {webhook_secret[:15]}...")
        return True
    else:
        print("❌ Webhook secret not properly configured")
        return False

def main():
    """Run all tests"""
    print("🧪 TRXCK.TECH Live Stripe Configuration Test")
    print("=" * 50)
    
    # Check environment variables
    required_vars = ['STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY', 'STRIPE_WEBHOOK_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("💡 Make sure to run: source live.env")
        return False
    
    print("✅ All required environment variables are set")
    
    # Initialize Stripe
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    
    # Run tests
    tests = [
        ("Stripe API Connection", test_stripe_connection),
        ("Price IDs", test_price_ids),
        ("Database Plans", test_database_plans),
        ("Webhook Configuration", test_webhook_endpoint)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name} test...")
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Your live Stripe setup is ready!")
        print("\n🚀 Next steps:")
        print("1. Deploy your code to production (PythonAnywhere)")
        print("2. Set the environment variables in production")
        print("3. Test a real transaction carefully")
        print("4. Monitor the first few transactions closely")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues before going live.")
    
    return all_passed

if __name__ == "__main__":
    main() 