# 🔐 Secrets Management Guide

## 📋 **Overview**

This guide explains how to properly manage secrets for your Flask application in both development and production environments.

## 🏠 **1. Local Development (.env file)**

Create a `.env` file in your project root with these actual values:

```bash
# LOCAL DEVELOPMENT ENVIRONMENT VARIABLES
# This file contains actual secrets and should NEVER be committed to git

# Flask Environment
FLASK_ENV=development

# Email Configuration (Brevo SMTP)
MAIL_SERVER=smtp-relay.brevo.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=YOUR_BREVO_USERNAME
MAIL_PASSWORD=YOUR_BREVO_PASSWORD
MAIL_DEFAULT_SENDER=noreply@trxck.tech

# Security Keys
SECRET_KEY=YOUR_SECRET_KEY_HERE
FERNET_SECRET_KEY=YOUR_FERNET_KEY_HERE

# Database (Supabase)
DATABASE_URL=YOUR_DATABASE_URL_HERE

# Deepseek API
DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY
DEEPSEEK_API_ENDPOINT=https://api.deepseek.com/v1/chat/completions

# Stripe Configuration (Test Keys)
STRIPE_WEBHOOK_SECRET=YOUR_STRIPE_WEBHOOK_SECRET
STRIPE_PUBLISHABLE_KEY=YOUR_STRIPE_PUBLISHABLE_KEY
STRIPE_SECRET_KEY=YOUR_STRIPE_SECRET_KEY

# Domain Configuration (for local development)
SERVER_NAME=localhost:5000
PREFERRED_URL_SCHEME=http
```

## 🚀 **2. Production Environment (PythonAnywhere)**

### Option A: Environment Variables (RECOMMENDED)

1. Go to PythonAnywhere Web tab
2. Scroll to "Environment variables" section
3. Add each variable individually:

```
FLASK_ENV=production
MAIL_SERVER=smtp-relay.brevo.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=YOUR_BREVO_USERNAME
MAIL_PASSWORD=YOUR_BREVO_PASSWORD
MAIL_DEFAULT_SENDER=noreply@trxck.tech
SECRET_KEY=YOUR_SECRET_KEY_HERE
FERNET_SECRET_KEY=YOUR_FERNET_KEY_HERE
DATABASE_URL=YOUR_DATABASE_URL_HERE
DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY
DEEPSEEK_API_ENDPOINT=https://api.deepseek.com/v1/chat/completions
STRIPE_WEBHOOK_SECRET=YOUR_STRIPE_WEBHOOK_SECRET
STRIPE_PUBLISHABLE_KEY=YOUR_STRIPE_PUBLISHABLE_KEY
STRIPE_SECRET_KEY=YOUR_STRIPE_SECRET_KEY
SERVER_NAME=trxck.tech
PREFERRED_URL_SCHEME=https
```

### Option B: Upload .env file to PythonAnywhere

1. Create a `.env` file (same as local but with production values)
2. Upload it to your PythonAnywhere project directory
3. Make sure your WSGI file loads it (it already does)

## 🔒 **3. Security Best Practices**

### ✅ **DO:**

- Keep `.env` in `.gitignore` (already done)
- Use different keys for development vs production
- Rotate secrets regularly
- Use environment variables in production
- Store backup of secrets in a secure password manager

### ❌ **DON'T:**

- Commit secrets to git
- Share secrets in plain text
- Use the same secrets across environments
- Leave default/weak secret keys

## 📝 **4. Quick Setup Commands**

```bash
# Create your local .env file
cp .env.example .env  # (if you have the example file)
# Or create it manually with the values above

# Test that your app loads the secrets
python -c "from app import create_app; app = create_app(); print('✅ App created successfully')"

# Test email functionality
python test_email_verification_locally.py
```

## 🚨 **5. Emergency Recovery**

If you lose your secrets:

1. **Database**: Check Supabase dashboard for connection details
2. **Email**: Check Brevo dashboard for SMTP credentials
3. **Stripe**: Check Stripe dashboard for API keys
4. **Generate new SECRET_KEY**: `python -c "import secrets; print(secrets.token_hex(32))"`
5. **Generate new FERNET_KEY**: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## 🎯 **Current Status**

- ✅ Secrets removed from git repository
- ✅ .gitignore properly configured
- ⚠️ Need to create local .env file
- ⚠️ Need to set production environment variables

## 🚀 **Next Steps**

1. Create local `.env` file with values above
2. Set environment variables in PythonAnywhere
3. Test email verification functionality
4. Deploy and test in production
