#!/usr/bin/env python3
"""
Simple Stripe Live Configuration Test
====================================

This script tests your live Stripe configuration without initializing the full Flask app.
"""

import os
import stripe

def test_stripe_api():
    """Test basic Stripe API connection"""
    print("🔗 Testing Stripe API connection...")
    
    # Get API key from environment
    api_key = os.getenv('STRIPE_SECRET_KEY')
    if not api_key:
        print("❌ STRIPE_SECRET_KEY not found in environment")
        return False
    
    if not api_key.startswith('sk_live_'):
        print("⚠️  Warning: Not using live API key (should start with sk_live_)")
        print(f"   Current key starts with: {api_key[:15]}...")
    else:
        print("✅ Using live Stripe API key")
    
    # Initialize Stripe
    stripe.api_key = api_key
    
    try:
        # Test API connection
        account = stripe.Account.retrieve()
        print(f"✅ Connected to Stripe account: {account.id}")
        print(f"   Business profile: {account.business_profile.name if account.business_profile else 'N/A'}")
        return True
    except stripe.error.AuthenticationError:
        print("❌ Authentication failed - invalid API key")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_product():
    """Test your specific product"""
    print("\n📦 Testing your product...")
    
    try:
        product = stripe.Product.retrieve("prod_RFrAVB9sQ8sUHk")
        print(f"✅ Found product: {product.name}")
        print(f"   ID: {product.id}")
        print(f"   Active: {product.active}")
        return True
    except stripe.error.InvalidRequestError:
        print("❌ Product prod_RFrAVB9sQ8sUHk not found")
        return False
    except Exception as e:
        print(f"❌ Error retrieving product: {e}")
        return False

def test_price_ids():
    """Test your price IDs"""
    print("\n💰 Testing price IDs...")
    
    price_ids = {
        "Monthly": "price_1QNLS8P9VzR6WBM9QPDKMInq",
        "Yearly": "price_1RMDzDP9VzR6WBM9re7nv8HK"
    }
    
    all_good = True
    for name, price_id in price_ids.items():
        try:
            price = stripe.Price.retrieve(price_id)
            amount = price.unit_amount / 100
            currency = price.currency.upper()
            interval = price.recurring.interval if price.recurring else "one-time"
            print(f"✅ {name}: {currency} {amount}/{interval} (ID: {price_id})")
        except Exception as e:
            print(f"❌ Error with {name} price {price_id}: {e}")
            all_good = False
    
    return all_good

def test_webhook_secret():
    """Test webhook secret"""
    print("\n🎣 Testing webhook secret...")
    
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    if not webhook_secret:
        print("❌ STRIPE_WEBHOOK_SECRET not found in environment")
        return False
    
    if webhook_secret.startswith('whsec_'):
        print(f"✅ Webhook secret configured: {webhook_secret[:15]}...")
        return True
    else:
        print("❌ Webhook secret doesn't start with 'whsec_'")
        return False

def main():
    """Run all tests"""
    print("🧪 Simple Live Stripe Configuration Test")
    print("=" * 45)
    
    # Check environment variables
    required_vars = ['STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY', 'STRIPE_WEBHOOK_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("💡 Make sure to run: source live.env")
        return False
    
    print("✅ All required environment variables found")
    
    # Run tests
    tests = [
        ("Stripe API Connection", test_stripe_api),
        ("Product Verification", test_product),
        ("Price IDs", test_price_ids),
        ("Webhook Secret", test_webhook_secret)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}:")
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    print("\n" + "=" * 45)
    print("📊 TEST SUMMARY")
    print("=" * 45)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n✅ Your live Stripe configuration is ready!")
        print("\n🚀 You can now:")
        print("1. Deploy to production")
        print("2. Set environment variables in production")
        print("3. Test with real payments")
    else:
        print("\n⚠️  Some tests failed. Please fix before going live.")
    
    return all_passed

if __name__ == "__main__":
    main() 