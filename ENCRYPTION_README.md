# 🔐 Application-Level Encryption System

This document describes the application-level encryption system implemented for sensitive patient and treatment data in the physio application.

## 📋 Encrypted Fields

### Patient Model (`app/models.py`)

The following sensitive fields are encrypted at the database level:

| Field   | Database Column | Description             | Encryption Status |
| ------- | --------------- | ----------------------- | ----------------- |
| `name`  | `_name`         | Patient's full name     | ✅ Encrypted      |
| `email` | `_email`        | Patient's email address | ✅ Encrypted      |
| `phone` | `_phone`        | Patient's phone number  | ✅ Encrypted      |
| `notes` | `_notes`        | Patient's medical notes | ✅ Encrypted      |

### Treatment Model (`app/models.py`)

| Field   | Database Column | Description             | Encryption Status |
| ------- | --------------- | ----------------------- | ----------------- |
| `notes` | `_notes`        | Treatment session notes | ✅ Encrypted      |

## 🔧 How It Works

### Database Storage

- **Encrypted data is stored in database columns with underscore prefixes** (e.g., `_name`, `_email`)
- **Plain text is never stored in the database** for sensitive fields
- **Encryption uses Fernet (AES-128-CBC) with base64 encoding**

### Application Access

- **Transparent encryption/decryption** via Python properties
- **No code changes needed** in application logic
- **Automatic encryption** when setting values
- **Automatic decryption** when reading values

### Example Usage

```python
# Setting encrypted data
patient = Patient()
patient.name = "John Doe"  # Automatically encrypted to _name
patient.email = "john@example.com"  # Automatically encrypted to _email
db.session.commit()

# Reading decrypted data
print(patient.name)  # Returns "John Doe" (automatically decrypted)
print(patient._name)  # Returns encrypted base64 string
```

## 🔑 FERNET_SECRET_KEY Management

### ⚠️ CRITICAL: Key Security

The `FERNET_SECRET_KEY` is **essential for data access**:

- **Never lose this key** - encrypted data becomes unrecoverable
- **Keep it consistent** across all environments (dev, staging, production)
- **Back it up securely** in multiple locations
- **Never commit it to version control**

### Environment Setup

```bash
# Generate a new key (if needed)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set in environment
export FERNET_SECRET_KEY="your-generated-key-here"

# Or add to .env file
echo "FERNET_SECRET_KEY=your-generated-key-here" >> .env
```

### Key Rotation (Advanced)

If you need to rotate the encryption key:

1. **Backup your current key**
2. **Generate new key**
3. **Re-encrypt all data** using migration scripts
4. **Update environment variables**
5. **Test thoroughly**

## 🚀 Data Migration

### Initial Setup

For new installations, encryption is automatic. For existing data:

```bash
# 1. Set your FERNET_SECRET_KEY
export FERNET_SECRET_KEY="your-key"

# 2. Run the migration script
python3 migrate_encryption.py

# 3. Verify the migration
python3 test_encryption.py
```

### Adding New Encrypted Fields

When adding new sensitive fields to existing models:

#### 1. Update the Model

```python
class Patient(db.Model):
    # Add encrypted column with underscore prefix
    _new_sensitive_field = db.Column("new_sensitive_field", db.String(255))

    # Add property getter/setter
    @property
    def new_sensitive_field(self):
        """Get decrypted new_sensitive_field"""
        if self._new_sensitive_field:
            return decrypt_text(self._new_sensitive_field)
        return None

    @new_sensitive_field.setter
    def new_sensitive_field(self, value):
        """Set encrypted new_sensitive_field"""
        if value:
            self._new_sensitive_field = encrypt_text(value)
        else:
            self._new_sensitive_field = None
```

#### 2. Create Database Migration

```bash
# Create Alembic migration
flask db migrate -m "Add encrypted new_sensitive_field"

# Apply migration
flask db upgrade
```

#### 3. Create Data Migration Script

```python
# new_field_migration.py
from app import create_app, db
from app.models import Patient
from app.crypto_utils import encrypt_text

def migrate_new_field():
    app = create_app()
    with app.app_context():
        patients = Patient.query.all()

        for patient in patients:
            # Get existing unencrypted value (if any)
            old_value = getattr(patient, 'new_sensitive_field', None)

            if old_value and not patient._new_sensitive_field:
                # Encrypt existing data
                patient.new_sensitive_field = old_value

        db.session.commit()
        print("Migration completed!")

if __name__ == '__main__':
    migrate_new_field()
```

#### 4. Run the Migration

```bash
python3 new_field_migration.py
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. "FERNET_SECRET_KEY not found"

```bash
# Solution: Set the environment variable
export FERNET_SECRET_KEY="your-key"
```

#### 2. "Invalid base64-encoded string" errors

This indicates mixed encrypted/unencrypted data:

```bash
# Run diagnostic
python3 diagnose_encryption.py

# Fix data issues
python3 fix_data_issues.py
```

#### 3. "ORDER BY expression expected" errors

This means you're using `Patient.name` in database queries instead of `Patient._name`:

```python
# ❌ Wrong
Patient.query.order_by(Patient.name).all()

# ✅ Correct
Patient.query.order_by(Patient._name).all()
```

### Debugging Tools

#### Diagnostic Script

```bash
python3 diagnose_encryption.py
```

Shows current data state and encryption status.

#### Data Fix Script

```bash
python3 fix_data_issues.py
```

Identifies and fixes mixed encrypted/unencrypted data.

#### Test Script

```bash
python3 test_encryption.py
```

Verifies encryption system is working correctly.

## 📊 Performance Considerations

### Database Queries

- **Ordering by encrypted fields** works but orders by encrypted values
- **Searching encrypted fields** requires full table scan (consider search indexes)
- **Filtering by encrypted fields** is not possible without decryption

### Recommendations

- **Keep non-sensitive fields unencrypted** for efficient querying
- **Use search indexes** on non-sensitive fields for better performance
- **Consider client-side sorting** for encrypted fields when needed

## 🔒 Security Best Practices

### Key Management

- ✅ **Store keys securely** (environment variables, secret managers)
- ✅ **Rotate keys regularly** (quarterly recommended)
- ✅ **Backup keys** in multiple secure locations
- ❌ **Never hardcode keys** in source code
- ❌ **Never commit keys** to version control

### Data Handling

- ✅ **Encrypt sensitive data** at rest
- ✅ **Use HTTPS** for data in transit
- ✅ **Log access** to sensitive data
- ✅ **Implement access controls** (already done via user roles)

### Compliance

This encryption system helps with:

- **GDPR compliance** (data protection by design)
- **HIPAA compliance** (if applicable)
- **General data protection** best practices

## 📝 Maintenance

### Regular Tasks

- **Monitor encryption logs** for errors
- **Backup encryption keys** regularly
- **Test encryption/decryption** after deployments
- **Review access logs** for suspicious activity

### Monitoring

Check application logs for:

- `"Error in decrypt_text"` - indicates data issues
- `"FERNET_SECRET_KEY not found"` - indicates configuration issues
- `"Base64 decode failed"` - indicates mixed data (normal during migration)

---

## 🎯 Quick Reference

### Essential Commands

```bash
# Set encryption key
export FERNET_SECRET_KEY="your-key"

# Test encryption
python3 test_encryption.py

# Diagnose issues
python3 diagnose_encryption.py

# Fix data issues
python3 fix_data_issues.py

# Migrate existing data
python3 migrate_encryption.py
```

### Encrypted Fields Summary

- **Patient**: `name`, `email`, `phone`, `notes`
- **Treatment**: `notes`
- **Database columns**: `_name`, `_email`, `_phone`, `_notes`

### Key Files

- `app/crypto_utils.py` - Encryption utilities
- `app/models.py` - Model definitions with encryption
- `migrate_encryption.py` - Data migration script
- `fix_data_issues.py` - Data issue resolution
- `diagnose_encryption.py` - Diagnostic tools

---

**Last Updated**: June 2025  
**Version**: 1.0  
**Maintainer**: Development Team
