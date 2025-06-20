#!/usr/bin/env python3
"""
Test script for logging and monitoring setup.
Run this script to verify that logging and monitoring are working correctly.
"""

import os
import sys
import logging
from datetime import datetime
import json

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, Patient, Treatment, SecurityLog
from app.utils import log_sensitive_operation, log_api_access, log_error_with_context

def test_basic_logging():
    """Test basic logging functionality."""
    print("🧪 Testing basic logging...")
    
    app = create_app()
    with app.app_context():
        # Test different log levels
        app.logger.debug("This is a debug message")
        app.logger.info("This is an info message")
        app.logger.warning("This is a warning message")
        app.logger.error("This is an error message")
        
        print("✅ Basic logging test completed")

def test_file_logging():
    """Test file logging with rotation."""
    print("🧪 Testing file logging...")
    
    app = create_app()
    with app.app_context():
        # Check if logs directory exists
        if os.path.exists('logs'):
            print(f"✅ Logs directory exists: {os.path.abspath('logs')}")
            
            # Check if log file exists
            log_file = 'logs/physiotracker.log'
            if os.path.exists(log_file):
                print(f"✅ Log file exists: {os.path.abspath(log_file)}")
                
                # Read last few lines of log file
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        print(f"✅ Log file contains {len(lines)} lines")
                        print("📝 Last 3 log entries:")
                        for line in lines[-3:]:
                            print(f"   {line.strip()}")
                    else:
                        print("⚠️  Log file is empty")
            else:
                print("❌ Log file does not exist")
        else:
            print("❌ Logs directory does not exist")

def test_health_endpoint():
    """Test the health check endpoint."""
    print("🧪 Testing health endpoint...")
    
    app = create_app()
    with app.test_client() as client:
        response = client.get('/health')
        if response.status_code == 200:
            data = response.get_json()
            print("✅ Health endpoint working")
            print(f"📊 System status: {data.get('status')}")
            print(f"📊 Database: {data.get('database')}")
            print(f"📊 Total users: {data.get('total_users')}")
            print(f"📊 Total patients: {data.get('total_patients')}")
            print(f"📊 Total treatments: {data.get('total_treatments')}")
        else:
            print(f"❌ Health endpoint failed with status {response.status_code}")

def test_sensitive_operation_logging():
    """Test logging of sensitive operations."""
    print("🧪 Testing sensitive operation logging...")
    
    app = create_app()
    with app.app_context():
        try:
            # Test logging a sensitive operation
            log_sensitive_operation(
                operation_type='test_login',
                user_id=1,
                details={'test': True, 'timestamp': datetime.utcnow().isoformat()},
                success=True
            )
            print("✅ Sensitive operation logging test completed")
        except Exception as e:
            print(f"❌ Sensitive operation logging failed: {e}")

def test_api_access_logging():
    """Test API access logging."""
    print("🧪 Testing API access logging...")
    
    app = create_app()
    with app.app_context():
        try:
            # Test logging API access
            log_api_access(
                endpoint='/api/test',
                user_id=1,
                method='GET',
                status_code=200,
                response_time=0.123
            )
            print("✅ API access logging test completed")
        except Exception as e:
            print(f"❌ API access logging failed: {e}")

def test_error_logging():
    """Test error logging with context."""
    print("🧪 Testing error logging...")
    
    app = create_app()
    with app.app_context():
        try:
            # Test logging an error with context
            test_error = ValueError("This is a test error")
            log_error_with_context(
                error=test_error,
                context={'test': True, 'function': 'test_error_logging'}
            )
            print("✅ Error logging test completed")
        except Exception as e:
            print(f"❌ Error logging failed: {e}")

def test_security_log_table():
    """Test SecurityLog table functionality."""
    print("🧪 Testing SecurityLog table...")
    
    app = create_app()
    with app.app_context():
        try:
            # Check if SecurityLog table exists and can be queried
            count = SecurityLog.query.count()
            print(f"✅ SecurityLog table accessible, contains {count} records")
            
            # Create a test security log entry
            test_log = SecurityLog(
                user_id=1,
                event_type='test_event',
                details=json.dumps({'test': True}),
                success=True,
                ip_address='127.0.0.1',
                user_agent='Test Script',
                created_at=datetime.utcnow()
            )
            db.session.add(test_log)
            db.session.commit()
            print("✅ Test security log entry created successfully")
            
            # Clean up test entry
            db.session.delete(test_log)
            db.session.commit()
            print("✅ Test security log entry cleaned up")
            
        except Exception as e:
            print(f"❌ SecurityLog table test failed: {e}")

def main():
    """Run all tests."""
    print("🚀 Starting logging and monitoring tests...\n")
    
    try:
        test_basic_logging()
        print()
        
        test_file_logging()
        print()
        
        test_health_endpoint()
        print()
        
        test_sensitive_operation_logging()
        print()
        
        test_api_access_logging()
        print()
        
        test_error_logging()
        print()
        
        test_security_log_table()
        print()
        
        print("🎉 All tests completed!")
        print("\n📋 Next steps:")
        print("1. Set up Sentry DSN in your environment variables")
        print("2. Configure monitoring alerts in Sentry")
        print("3. Set up log rotation and archiving")
        print("4. Monitor the /health endpoint for uptime")
        print("5. Review logs regularly for security events")
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 