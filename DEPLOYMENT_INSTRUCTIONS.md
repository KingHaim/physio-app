# 🚀 DEPLOYMENT INSTRUCTIONS for PythonAnywhere

## 📋 **Current Status**

- ✅ Code works locally
- ✅ Route fix applied (`/verify_email/<token>`)
- ✅ Import error fixed
- ❌ Changes not deployed to production

## 🔧 **Step-by-Step Deployment**

### 1. **Update PythonAnywhere Code**

```bash
# In PythonAnywhere Bash console:
cd /home/yourusername/physio-app
git pull origin main
```

### 2. **Set Environment Variables**

Go to PythonAnywhere Web tab → Environment variables section:

**Add these variables (use your actual values from .env file):**

```
FLASK_ENV=production
MAIL_SERVER=smtp-relay.brevo.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=YOUR_BREVO_USERNAME
MAIL_PASSWORD=YOUR_BREVO_PASSWORD
MAIL_DEFAULT_SENDER=noreply@trxck.tech
SECRET_KEY=YOUR_SECRET_KEY
FERNET_SECRET_KEY=YOUR_FERNET_KEY
DATABASE_URL=YOUR_DATABASE_URL
DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY
DEEPSEEK_API_ENDPOINT=https://api.deepseek.com/v1/chat/completions
STRIPE_WEBHOOK_SECRET=YOUR_STRIPE_WEBHOOK_SECRET
STRIPE_PUBLISHABLE_KEY=YOUR_STRIPE_PUBLISHABLE_KEY
STRIPE_SECRET_KEY=YOUR_STRIPE_SECRET_KEY
SERVER_NAME=trxck.tech
PREFERRED_URL_SCHEME=https
```

### 3. **Reload Web App**

- Go to PythonAnywhere Web tab
- Click **"Reload yourusername.pythonanywhere.com"**
- Wait for reload to complete

### 4. **Test the Fix**

Try these URLs:

- ✅ `https://trxck.tech/auth/login`
- ✅ `https://trxck.tech/auth/register`
- ✅ `https://trxck.tech/auth/verify_email/test-token`

### 5. **Check Error Logs**

If still having issues:

- Go to PythonAnywhere Web tab
- Click "Error log" to see any issues
- Check for import errors or missing variables

## 🎯 **Expected Results After Deployment**

- Auth routes should return 200 (not 404)
- Email verification links should work
- New user registrations should send emails with correct links

## 🚨 **Troubleshooting**

If routes still return 404:

1. Check that git pull actually updated the code
2. Verify environment variables are set correctly
3. Check error logs for Python import errors
4. Ensure WSGI file is pointing to correct app

## ✅ **Verification Steps**

1. Register a new user
2. Check email for verification link
3. Click verification link
4. Should see success message (not 404)

---

**Note**: The route is now `/verify_email/<token>` (with underscore), not `/verify-email/<token>` (with dash)
