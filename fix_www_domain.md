# 🔧 Fix WWW Domain Issue

## 🎯 **Problem Fixed**

- ✅ Fixed internal error in `add_security_headers`
- ⚠️ Need to update domain configuration

## 📋 **Steps to Fix WWW Domain**

### 1. **Update Environment Variables in PythonAnywhere**

Go to PythonAnywhere Web tab → Environment variables section:

**Change this:**

```
SERVER_NAME=trxck.tech
```

**To this:**

```
SERVER_NAME=www.trxck.tech
```

### 2. **Other Variables to Verify**

Make sure these are also set:

```
FLASK_ENV=production
PREFERRED_URL_SCHEME=https
MAIL_SERVER=smtp-relay.brevo.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_DEFAULT_SENDER=noreply@trxck.tech
```

### 3. **Deploy the Fix**

```bash
# In PythonAnywhere console:
cd /home/yourusername/physio-app
git pull origin main
```

### 4. **Reload Web App**

- Go to PythonAnywhere Web tab
- Click **"Reload"** button
- Wait for reload to complete

### 5. **Test the Fix**

1. **Test login**: `https://www.trxck.tech/auth/login`
2. **Test registration**: `https://www.trxck.tech/auth/register`
3. **Test email verification**: Click link in email (should work now)

## 🎯 **Expected Results**

- ✅ Internal errors should be gone
- ✅ Email verification links should work
- ✅ All pages should load properly with www.trxck.tech

## 🔄 **Domain Redirection (Optional)**

To redirect `trxck.tech` to `www.trxck.tech`, you may need to:

1. Configure DNS in your domain provider
2. Add a redirect rule in PythonAnywhere
3. Or use a .htaccess file

## ✅ **Verification**

After making these changes:

1. Register a new user
2. Check email for verification link
3. Click the link - should work without 404
4. Login should work without internal errors
