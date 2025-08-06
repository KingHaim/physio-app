#!/usr/bin/env python3
"""
Stripe Live Mode Setup Script for TRXCK.TECH
===========================================

This script helps you transition from Stripe test mode to live mode.
Your product ID: prod_RFrAVB9sQ8sUHk

IMPORTANT: Run this script ONLY after you have:
1. Created live Price IDs in your Stripe Dashboard for product prod_RFrAVB9sQ8sUHk
2. Obtained your live Stripe API keys
3. Set up live webhook endpoints

Usage:
    python setup_stripe_live.py --update-prices
    python setup_stripe_live.py --update-env
    python setup_stripe_live.py --verify-setup
"""

import os
import argparse
import json
from typing import Dict, List

# Live Price IDs for product prod_RFrAVB9sQ8sUHk
# UPDATED WITH YOUR ACTUAL LIVE PRICE IDs
LIVE_PRICE_IDS = {
    "individualmonthly": "price_1QNLS8P9VzR6WBM9QPDKMInq",  # Individual Monthly Plan
    "individualyearly": "price_1RMDzDP9VzR6WBM9re7nv8HK",   # Individual Yearly Plan
}

# Current test price IDs that will be replaced
TEST_PRICE_IDS = {
    "basic": "price_1RTfP7P5aPDx5xda6UyIUt5m",
    "standard": "price_1RTfQVP5aPDx5xdaF9wAvecI", 
    "premium": "price_1RTfR4P5aPDx5xda3UvGfGoz"
}

def update_seed_plans_with_live_prices():
    """Update seed_plans.py with live Stripe price IDs"""
    
    print("🔄 Updating seed_plans.py with live Stripe price IDs...")
    
    # Read current seed_plans.py
    with open('seed_plans.py', 'r') as f:
        content = f.read()
    
    # Create backup
    with open('seed_plans.py.backup', 'w') as f:
        f.write(content)
    print("✅ Created backup: seed_plans.py.backup")
    
    # Replace test price IDs with live ones
    replacements = [
        (TEST_PRICE_IDS["basic"], LIVE_PRICE_IDS["basic"]),
        (TEST_PRICE_IDS["standard"], LIVE_PRICE_IDS["standard"]),
        (TEST_PRICE_IDS["premium"], LIVE_PRICE_IDS["premium"])
    ]
    
    updated_content = content
    for test_id, live_id in replacements:
        if test_id in updated_content:
            updated_content = updated_content.replace(test_id, live_id)
            print(f"✅ Replaced {test_id} with {live_id}")
        else:
            print(f"⚠️  Test price ID {test_id} not found in seed_plans.py")
    
    # Write updated content
    with open('seed_plans.py', 'w') as f:
        f.write(updated_content)
    
    print("✅ Updated seed_plans.py with live price IDs")
    print("🚀 Run 'python seed_plans.py' to update your database")

def create_live_env_template():
    """Create a template for live environment variables"""
    
    print("📄 Creating live environment template...")
    
    live_env_content = """# LIVE STRIPE CONFIGURATION FOR TRXCK.TECH
# ==========================================
# 
# CRITICAL: These are LIVE Stripe keys that will process real payments!
# Only use in production environment.
#
# Replace the placeholder values with your actual live Stripe keys from:
# https://dashboard.stripe.com/apikeys

# Live Stripe Configuration
export STRIPE_SECRET_KEY=sk_live_YOUR_LIVE_SECRET_KEY_HERE
export STRIPE_PUBLISHABLE_KEY=pk_live_YOUR_LIVE_PUBLISHABLE_KEY_HERE
export STRIPE_WEBHOOK_SECRET=whsec_YOUR_LIVE_WEBHOOK_SECRET_HERE

# Production Environment
export FLASK_ENV=production

# Database (Production)
export DATABASE_URL=postgresql://your_db_user:your_db_password@your_db_host:5432/your_db_name

# Email Configuration (Brevo SMTP)
export MAIL_SERVER=smtp-relay.brevo.com
export MAIL_PORT=587
export MAIL_USE_TLS=true
export MAIL_USERNAME=918347001@smtp-brevo.com
export MAIL_PASSWORD=8caQAZJ6CbRBstjk
export MAIL_DEFAULT_SENDER=noreply@trxck.tech

# Security Keys (GENERATE NEW ONES FOR PRODUCTION!)
export SECRET_KEY=your-production-secret-key-here
export FERNET_SECRET_KEY=your-production-fernet-key-here

# Domain Configuration
export SERVER_NAME=trxck.tech
export PREFERRED_URL_SCHEME=https

# AI Analytics (DeepSeek API for Practice Insights)
export DEEPSEEK_API_KEY=your-deepseek-api-key-here
export DEEPSEEK_API_ENDPOINT=https://api.deepseek.com/v1/chat/completions

# Optional: Sentry Error Monitoring
export SENTRY_DSN=your-sentry-dsn

# Instructions:
# 1. Update all placeholder values with your actual credentials
# 2. Source this file in your production environment:
#    source live.env
# 3. Or set these as environment variables in your hosting platform
"""

    with open('live.env', 'w') as f:
        f.write(live_env_content)
    
    print("✅ Created live.env template")
    print("⚠️  IMPORTANT: Update all placeholder values in live.env before using!")

def verify_stripe_setup():
    """Verify current Stripe configuration"""
    
    print("🔍 Verifying current Stripe setup...")
    
    # Check environment variables
    stripe_secret = os.getenv('STRIPE_SECRET_KEY', 'Not set')
    stripe_public = os.getenv('STRIPE_PUBLISHABLE_KEY', 'Not set')
    stripe_webhook = os.getenv('STRIPE_WEBHOOK_SECRET', 'Not set')
    
    print("\n📊 Current Stripe Configuration:")
    print(f"Secret Key: {'✅ Set' if stripe_secret != 'Not set' else '❌ Not set'}")
    print(f"Publishable Key: {'✅ Set' if stripe_public != 'Not set' else '❌ Not set'}")
    print(f"Webhook Secret: {'✅ Set' if stripe_webhook != 'Not set' else '❌ Not set'}")
    
    # Determine if using test or live keys
    if stripe_secret != 'Not set':
        if stripe_secret.startswith('sk_test_'):
            print("🧪 Currently using TEST Stripe keys")
        elif stripe_secret.startswith('sk_live_'):
            print("🚀 Currently using LIVE Stripe keys")
        else:
            print("❓ Unknown Stripe key format")
    
    # Check current price IDs in seed_plans.py
    print("\n📋 Current Price IDs in seed_plans.py:")
    try:
        with open('seed_plans.py', 'r') as f:
            content = f.read()
            
        for plan, price_id in TEST_PRICE_IDS.items():
            if price_id in content:
                print(f"🧪 {plan.title()}: {price_id} (TEST)")
        
        for plan, price_id in LIVE_PRICE_IDS.items():
            if price_id in content and not price_id.endswith('_REPLACE_ME'):
                print(f"🚀 {plan.title()}: {price_id} (LIVE)")
                
    except FileNotFoundError:
        print("❌ seed_plans.py not found")

def create_stripe_setup_guide():
    """Create a comprehensive setup guide"""
    
    guide_content = f"""# Stripe Live Mode Setup Guide for TRXCK.TECH

## 🎯 Your Product Information
- **Product ID**: `prod_RFrAVB9sQ8sUHk`
- **Current Status**: Test Mode → Transitioning to Live Mode

## 📋 Step-by-Step Setup

### 1. Create Live Price IDs in Stripe Dashboard

Go to your [Stripe Dashboard](https://dashboard.stripe.com/products) and:

1. Navigate to **Products** section
2. Find your product: `prod_RFrAVB9sQ8sUHk`
3. Create **three Price IDs** for your plans:

   - **Basic Plan**: $15.00 USD/month
   - **Standard Plan**: $30.00 USD/month  
   - **Premium Plan**: $60.00 USD/month

4. Copy the live price IDs (they start with `price_live_...`)

### 2. Update Price IDs in Code

Edit the `LIVE_PRICE_IDS` dictionary in `setup_stripe_live.py`:

```python
LIVE_PRICE_IDS = {{
    "basic": "price_YOUR_BASIC_LIVE_PRICE_ID",
    "standard": "price_YOUR_STANDARD_LIVE_PRICE_ID", 
    "premium": "price_YOUR_PREMIUM_LIVE_PRICE_ID"
}}
```

Then run:
```bash
python setup_stripe_live.py --update-prices
python seed_plans.py  # Update database with new price IDs
```

### 3. Set Up Live Webhook Endpoint

1. In Stripe Dashboard, go to **Webhooks**
2. Create a new webhook endpoint:
   - **URL**: `https://trxck.tech/webhooks/stripe`
   - **Events**: Select `checkout.session.completed`
3. Copy the webhook signing secret (starts with `whsec_`)

### 4. Update Environment Variables

For **PythonAnywhere** (or your hosting platform):

1. Go to Web tab → Environment variables
2. Set these variables:

```
STRIPE_SECRET_KEY=sk_live_YOUR_LIVE_SECRET_KEY
STRIPE_PUBLISHABLE_KEY=pk_live_YOUR_LIVE_PUBLISHABLE_KEY
STRIPE_WEBHOOK_SECRET=whsec_YOUR_LIVE_WEBHOOK_SECRET
FLASK_ENV=production
```

### 5. Verify Setup

Run the verification:
```bash
python setup_stripe_live.py --verify-setup
```

## ⚠️ Important Security Notes

1. **Never commit live keys to Git**
2. **Test thoroughly in test mode first**
3. **Keep backups of your test configuration**
4. **Monitor transactions closely after going live**

## 🧪 Testing Checklist

Before going live, test:
- [ ] Checkout flow works with test cards
- [ ] Webhooks are received and processed
- [ ] User subscriptions are created correctly
- [ ] Email notifications work
- [ ] Subscription management works

## 🚀 Going Live Checklist

- [ ] Live price IDs created and updated in code
- [ ] Live API keys set in production environment
- [ ] Live webhook endpoint configured
- [ ] SSL certificate valid for domain
- [ ] Database backup created
- [ ] Monitoring and logging enabled

## 📞 Support

If you encounter issues:
1. Check Stripe Dashboard logs
2. Check application logs
3. Verify all environment variables are set
4. Contact Stripe support if payment processing fails

---
Generated by setup_stripe_live.py
"""

    with open('STRIPE_LIVE_SETUP_GUIDE.md', 'w') as f:
        f.write(guide_content)
    
    print("✅ Created comprehensive setup guide: STRIPE_LIVE_SETUP_GUIDE.md")

def main():
    parser = argparse.ArgumentParser(description='Setup Stripe Live Mode for TRXCK.TECH')
    parser.add_argument('--update-prices', action='store_true', 
                       help='Update seed_plans.py with live price IDs')
    parser.add_argument('--update-env', action='store_true',
                       help='Create live environment template')
    parser.add_argument('--verify-setup', action='store_true',
                       help='Verify current Stripe configuration')
    parser.add_argument('--create-guide', action='store_true',
                       help='Create setup guide')
    parser.add_argument('--all', action='store_true',
                       help='Run all setup steps')
    
    args = parser.parse_args()
    
    if not any(vars(args).values()):
        parser.print_help()
        return
    
    print("🚀 TRXCK.TECH Stripe Live Mode Setup")
    print("=" * 40)
    print(f"Product ID: prod_RFrAVB9sQ8sUHk")
    print()
    
    if args.update_prices or args.all:
        # Check if live price IDs are still placeholders
        if any(price_id.endswith('_REPLACE_ME') for price_id in LIVE_PRICE_IDS.values()):
            print("❌ Please update LIVE_PRICE_IDS in this script with your actual price IDs first!")
            print("   Edit setup_stripe_live.py and replace the placeholder values.")
            return
        update_seed_plans_with_live_prices()
        print()
    
    if args.update_env or args.all:
        create_live_env_template()
        print()
    
    if args.verify_setup or args.all:
        verify_stripe_setup()
        print()
    
    if args.create_guide or args.all:
        create_stripe_setup_guide()
        print()
    
    print("✅ Setup steps completed!")
    print("\n📖 Next steps:")
    print("1. Read STRIPE_LIVE_SETUP_GUIDE.md for detailed instructions")
    print("2. Create live price IDs in Stripe Dashboard") 
    print("3. Update LIVE_PRICE_IDS in this script")
    print("4. Run with --update-prices flag")
    print("5. Set live environment variables")
    print("6. Test thoroughly before going live!")

if __name__ == "__main__":
    main() 