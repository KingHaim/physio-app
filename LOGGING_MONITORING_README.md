# Logging & Monitoring Setup

This document describes the logging and monitoring implementation for the PhysioTracker application.

## 🎯 Overview

The application now includes comprehensive logging and monitoring capabilities to help you:

- Track all user activities and system events
- Monitor application health and performance
- Detect and respond to security incidents
- Debug issues quickly with detailed error context
- Ensure compliance with data protection regulations

## 📋 Features Implemented

### 1. Enhanced Logging System

#### File Logging with Rotation

- **Location**: `logs/physiotracker.log`
- **Rotation**: 10KB max file size, keeps 10 backup files
- **Format**: `%(asctime)s [%(levelname)s] in %(module)s: %(message)s`

#### Request Logging

- Logs all incoming requests (excluding static files and health checks)
- Tracks user authentication status
- Special logging for sensitive endpoints (`/auth/`, `/api/`, `/webhooks/`, `/admin/`)
- Includes IP address and User-Agent information

#### Security Event Logging

- Database table: `SecurityLog`
- Tracks sensitive operations (logins, data access, payments)
- Records success/failure status
- Stores IP address and user agent for audit trails

### 2. Error Monitoring with Sentry

#### Setup

1. Install Sentry SDK: `pip install sentry-sdk[flask]`
2. Configure DSN in environment: `SENTRY_DSN=your-sentry-dsn`
3. Automatic error capture with user context
4. Sensitive data filtering before sending to Sentry

#### Features

- Automatic exception tracking
- User context inclusion
- Performance monitoring (20% transaction sampling)
- Environment-based configuration

### 3. Health Monitoring

#### Health Check Endpoint

- **URL**: `/health`
- **Method**: GET
- **Response**: JSON with system status and statistics
- **Use case**: Uptime monitoring, load balancer health checks

#### Monitoring Dashboard

- **URL**: `/monitoring` (admin only)
- **Features**: Real-time system status, log viewing, security events
- **Auto-refresh**: Every 30 seconds

### 4. Utility Functions

#### `log_sensitive_operation()`

```python
from app.utils import log_sensitive_operation

log_sensitive_operation(
    operation_type='login',
    user_id=user.id,
    details={'method': 'password', 'success': True},
    success=True
)
```

#### `log_api_access()`

```python
from app.utils import log_api_access

log_api_access(
    endpoint='/api/patients',
    user_id=user.id,
    method='GET',
    status_code=200,
    response_time=0.123
)
```

#### `log_error_with_context()`

```python
from app.utils import log_error_with_context

try:
    # Your code here
    pass
except Exception as e:
    log_error_with_context(e, {'additional': 'context'})
```

## 🚀 Setup Instructions

### 1. Environment Variables

Add these to your `.env` file:

```bash
# Sentry DSN (get from https://sentry.io)
SENTRY_DSN=https://your-dsn@sentry.io/project-id

# Optional: Set environment
FLASK_ENV=production
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Create Logs Directory

The application will automatically create the `logs/` directory on startup.

### 4. Test the Setup

Run the test script to verify everything is working:

```bash
python test_logging_monitoring.py
```

## 📊 Monitoring Dashboard

### Access

- **URL**: `/monitoring`
- **Access**: Admin users only
- **Features**:
  - Real-time system status
  - Database connectivity
  - User and patient counts
  - Recent system logs
  - Security events

### Health Check Endpoint

```bash
curl http://your-domain/health
```

Response:

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "database": "connected",
  "total_users": 25,
  "total_patients": 150,
  "total_treatments": 1200,
  "version": "1.0.0"
}
```

## 🔒 Security Monitoring

### Sensitive Endpoints

The following endpoints are automatically logged with enhanced detail:

- `/auth/login`, `/auth/register`, `/auth/reset_password`
- `/api/` (all API endpoints)
- `/webhooks/` (all webhook endpoints)
- `/admin/` (all admin endpoints)

### Security Log Table

The `SecurityLog` table stores:

- User ID
- Event type
- Success/failure status
- IP address
- User agent
- Timestamp
- Additional details (JSON)

### Example Queries

```sql
-- Recent failed login attempts
SELECT * FROM security_log
WHERE event_type = 'login' AND success = false
ORDER BY timestamp DESC LIMIT 10;

-- Suspicious IP addresses
SELECT ip_address, COUNT(*) as attempts
FROM security_log
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY ip_address
HAVING COUNT(*) > 10;
```

## 📈 Performance Monitoring

### Database Performance

- Connection pool monitoring
- Query performance tracking (via Sentry)
- Automatic slow query detection

### Application Performance

- Request response times
- Error rates
- User activity patterns

## 🛠️ Maintenance

### Log Rotation

- Automatic rotation when files reach 10KB
- Keeps 10 backup files
- Old logs are automatically deleted

### Log Analysis

```bash
# View recent logs
tail -f logs/physiotracker.log

# Search for errors
grep "ERROR" logs/physiotracker.log

# Search for security events
grep "SENSITIVE" logs/physiotracker.log
```

### Database Cleanup

```sql
-- Clean old security logs (older than 90 days)
DELETE FROM security_log
WHERE timestamp < NOW() - INTERVAL '90 days';
```

## 🔧 Configuration

### Log Levels

- **Development**: DEBUG
- **Production**: INFO
- **Sensitive operations**: WARNING

### Sentry Configuration

- **Sample rate**: 20% of transactions
- **Environment**: Based on FLASK_ENV
- **PII handling**: Enabled with filtering

### File Logging

- **Max file size**: 10KB
- **Backup count**: 10 files
- **Format**: Structured JSON-like format

## 🚨 Alerts and Notifications

### Sentry Alerts

Configure in Sentry dashboard:

- Error rate spikes
- Performance degradation
- New error types
- User impact alerts

### Custom Alerts

You can set up additional alerts for:

- High error rates in logs
- Unusual security events
- Database connectivity issues
- Health check failures

## 📚 Best Practices

### 1. Regular Monitoring

- Check monitoring dashboard daily
- Review security logs weekly
- Monitor error rates continuously

### 2. Log Management

- Archive old logs monthly
- Monitor disk space usage
- Set up log retention policies

### 3. Security

- Review failed login attempts
- Monitor unusual API usage
- Track data access patterns

### 4. Performance

- Monitor response times
- Track database performance
- Watch for memory leaks

## 🔍 Troubleshooting

### Common Issues

#### Logs not being written

- Check file permissions on `logs/` directory
- Verify disk space
- Check application startup logs

#### Sentry not working

- Verify SENTRY_DSN environment variable
- Check network connectivity
- Review Sentry project configuration

#### Health check failing

- Check database connectivity
- Verify all required services are running
- Review application logs for errors

### Debug Commands

```bash
# Check log file permissions
ls -la logs/

# Test database connectivity
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.session.execute('SELECT 1')"

# Test Sentry connection
python -c "import sentry_sdk; print('Sentry configured:', sentry_sdk.Hub.current.client is not None)"
```

## 📞 Support

For issues with logging and monitoring:

1. Check this documentation
2. Review application logs
3. Test with the provided test script
4. Contact system administrator

---

**Last updated**: January 2024
**Version**: 1.0.0
