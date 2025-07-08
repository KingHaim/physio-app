# 📧 Email Verification Setup Guide - TRXCKER PhysioApp

## 🎯 Overview

Your TRXCKER PhysioApp now has **complete email verification functionality**! This guide will help you configure and enable it.

## ✅ What's Already Implemented

- ✅ **Database fields** for email verification
- ✅ **Token generation** with 24-hour expiration
- ✅ **Email templates** (verification + welcome emails)
- ✅ **Routes** for verification and resending
- ✅ **Login protection** (unverified users can't log in)
- ✅ **Email change security** (requires re-verification)

## 🚀 Quick Setup (5 minutes)

### Step 1: Configure Email Settings

Add these variables to your `.env` file:

```bash
# Email Configuration with Brevo (Recommended)
MAIL_SERVER=smtp-relay.brevo.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@yourdomain.com
MAIL_PASSWORD=your-brevo-smtp-key-here
MAIL_DEFAULT_SENDER=noreply@yourdomain.com

# Optional: Custom email prefix
MAIL_SUBJECT_PREFIX=[TRXCKER]
```

### Step 2: Get Brevo SMTP Credentials

1. Log into your [Brevo account](https://app.brevo.com/)
2. Go to **Settings** → **SMTP & API**
3. In the SMTP section, copy your SMTP settings
4. Use your **SMTP key** (not login password) in `MAIL_PASSWORD`
5. Use your domain email in `MAIL_USERNAME` and `MAIL_DEFAULT_SENDER`

### Step 3: Test the Setup

```bash
# Start your application
python app.py

# Register a new test user
# Check the console logs for email verification output
```

## 📧 Email Providers

### Brevo (Recommended for Production)

```bash
MAIL_SERVER=smtp-relay.brevo.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@yourdomain.com
MAIL_PASSWORD=your-brevo-smtp-key
MAIL_DEFAULT_SENDER=noreply@yourdomain.com
```

### Gmail (Development)

```bash
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

### SendGrid (Alternative Production)

```bash
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=apikey
MAIL_PASSWORD=your-sendgrid-api-key
```

### Mailgun (Alternative Production)

```bash
MAIL_SERVER=smtp.mailgun.org
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-mailgun-username
MAIL_PASSWORD=your-mailgun-password
```

### Outlook/Hotmail

```bash
MAIL_SERVER=smtp.live.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@outlook.com
MAIL_PASSWORD=your-password
```

## 🔄 How It Works

### Registration Flow

```
User registers → Email marked as unverified → Verification email sent → User clicks link → Email verified → User can log in
```

### Email Change Flow

```
User changes email → Account marked unverified → Verification email sent to new address → User logs out → Must verify to log back in
```

### Login Flow

```
User attempts login → System checks email_verified → If false: deny login + show message → If true: allow login
```

## 🛠️ Available Features

### For Users

1. **Registration**: Automatic verification email
2. **Resend Verification**: Link in login page
3. **Email Change**: Requires re-verification
4. **Security**: Can't access app without verification

### For Developers

#### Check Verification Status

```python
if current_user.email_verified:
    # User is verified
else:
    # User needs verification
```

#### Require Verification for Routes

```python
from app.decorators import email_verified_required

@app.route('/sensitive-feature')
@login_required
@email_verified_required
def sensitive_feature():
    return "Only verified users can access this"
```

#### Manually Send Verification

```python
from app.email_utils import send_verification_email

send_verification_email(user)
```

## 🎨 Email Templates

The system includes beautiful HTML email templates:

### Verification Email

- Professional design with TRXCKER branding
- Clear call-to-action button
- Security information
- Fallback text version

### Welcome Email

- Celebration of successful verification
- Feature highlights
- Direct login link
- Getting started guidance

## 🔧 Customization

### Change Email Templates

Edit `app/email_utils.py`:

- Modify `send_verification_email()` for verification emails
- Modify `send_welcome_email()` for welcome emails

### Change Token Expiration

In `app/models.py`, `verify_email_token()` method:

```python
# Change from 24 hours to your preference
expiry_time = self.email_verification_sent_at + timedelta(hours=24)
```

### Change Email Subject/Sender

In your `.env` file:

```bash
MAIL_DEFAULT_SENDER=custom@yourcompany.com
MAIL_SUBJECT_PREFIX=[YOUR APP]
```

## 🧪 Testing

### Development Mode

Without email configuration, emails are logged to console:

```
========== EMAIL WOULD BE SENT (NO SMTP CONFIG) ==========
To: user@example.com
Subject: [TRXCKER] Verifica tu email
HTML Body: <!DOCTYPE html>...
=========================================================
```

### Test Email Sending

```python
# In Flask shell or test script
from app.email_utils import send_email

result = send_email(
    to_email="test@example.com",
    subject="Test Email",
    html_body="<h1>Test</h1>",
    text_body="Test"
)
print(f"Email sent: {result}")
```

## 🔒 Security Features

### Token Security

- **Secure generation**: Uses `secrets` module
- **Hashed storage**: Tokens are hashed in database
- **Time expiration**: 24-hour automatic expiry
- **Single use**: Tokens cleared after verification

### Email Change Protection

- **Requires re-verification**: New emails must be verified
- **Forced logout**: Users logged out until verification
- **Conflict checking**: Prevents email takeovers

## 🚨 Troubleshooting

### Issue: Emails not sending

**Solution**: Check your email configuration and credentials

### Issue: Gmail "Less secure app" error

**Solution**: Use App Passwords instead of regular password

### Issue: Users not receiving emails

**Solution**: Check spam folders, verify email configuration

### Issue: "Email already verified" message

**Solution**: User is already verified, this is normal

### Issue: Token expired

**Solution**: User can request new verification email

## 📱 Production Deployment

### Use Professional Email Service

- **Brevo**: Excellent deliverability, generous free tier, easy setup
- **SendGrid**: Reliable, good free tier
- **Mailgun**: Feature-rich, good for high volume
- **Amazon SES**: Cost-effective, AWS integration

### Environment Variables

```bash
# Production example with Brevo (Recommended)
MAIL_SERVER=smtp-relay.brevo.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@yourdomain.com
MAIL_PASSWORD=your-brevo-smtp-key-here
MAIL_DEFAULT_SENDER=noreply@yourdomain.com
```

### Monitor Email Delivery

- Set up email delivery monitoring
- Track bounce rates and failures
- Implement retry logic for failed sends

## 🎉 Success!

Your email verification system is now **fully functional**! Features include:

- ✅ **Secure registration** with email verification
- ✅ **Beautiful email templates**
- ✅ **Automatic security** for email changes
- ✅ **User-friendly** resend functionality
- ✅ **Production-ready** with proper error handling

Users will now receive professional verification emails and must verify before accessing the application. The system provides a secure, user-friendly experience that prevents fake registrations and ensures email ownership.

## 📞 Support

If you need help configuring email verification:

1. Check the console logs for detailed error messages
2. Verify your email provider settings
3. Test with a simple email first
4. Consult your email provider's SMTP documentation

Happy emailing! 🚀
