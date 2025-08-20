#!/usr/bin/env python3
"""
Debug performance issues by timing actual operations and identifying bottlenecks.
"""
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Patient, Treatment, User
from sqlalchemy import text, func


def time_operation(operation_name, func):
    """Time an operation and print results"""
    start = time.time()
    try:
        result = func()
        end = time.time()
        duration = (end - start) * 1000  # Convert to milliseconds
        print(f"  ✅ {operation_name}: {duration:.1f}ms")
        return result, duration
    except Exception as e:
        end = time.time()
        duration = (end - start) * 1000
        print(f"  ❌ {operation_name}: {duration:.1f}ms - ERROR: {str(e)[:50]}...")
        return None, duration


def test_database_connection():
    """Test basic database connectivity and response time"""
    print("🔍 Testing Database Connection...")
    
    def simple_query():
        return db.session.execute(text("SELECT 1")).scalar()
    
    result, duration = time_operation("Simple SELECT 1", simple_query)
    
    if duration > 1000:  # More than 1 second
        print("  ⚠️  Database connection is VERY slow (>1s)")
        print("  💡 This suggests PythonAnywhere database server issues")
    elif duration > 100:
        print("  ⚠️  Database connection is slow (>100ms)")
    else:
        print("  ✅ Database connection is normal")


def test_common_queries():
    """Test the most common queries that users encounter"""
    print("\n🔍 Testing Common Queries...")
    
    # Test patient count query
    def count_patients():
        return Patient.query.count()
    
    result, duration = time_operation("Patient.query.count()", count_patients)
    
    # Test treatment count query  
    def count_treatments():
        return Treatment.query.count()
    
    result, duration = time_operation("Treatment.query.count()", count_treatments)
    
    # Test user lookup
    def get_first_user():
        return User.query.first()
    
    result, duration = time_operation("User.query.first()", get_first_user)
    
    # Test join query (common in dashboard)
    def join_query():
        return db.session.query(Treatment).join(Patient).filter(Patient.user_id == 1).count()
    
    result, duration = time_operation("Treatment JOIN Patient query", join_query)
    
    if duration > 500:
        print("  ⚠️  JOIN queries are very slow - this is likely the main issue")


def test_dashboard_simulation():
    """Simulate the dashboard loading process"""
    print("\n🔍 Simulating Dashboard Load...")
    
    total_start = time.time()
    
    # Get first user for simulation
    user = User.query.first()
    if not user:
        print("  ❌ No users found for testing")
        return
    
    def get_user_patients():
        return user.patients.all()
    
    patients, duration = time_operation(f"Get patients for user {user.id}", get_user_patients)
    
    if patients:
        def get_patient_treatments():
            return Treatment.query.filter_by(patient_id=patients[0].id).all()
        
        treatments, duration = time_operation("Get treatments for first patient", get_patient_treatments)
    
    def get_recent_treatments():
        return Treatment.query.order_by(Treatment.created_at.desc()).limit(10).all()
    
    recent, duration = time_operation("Get 10 recent treatments", get_recent_treatments)
    
    total_end = time.time()
    total_duration = (total_end - total_start) * 1000
    
    print(f"  📊 Total dashboard simulation: {total_duration:.1f}ms")
    
    if total_duration > 3000:
        print("  ❌ Dashboard simulation is VERY slow (>3s)")
        print("  💡 This explains why your app feels slow")
    elif total_duration > 1000:
        print("  ⚠️  Dashboard simulation is slow (>1s)")


def check_server_resources():
    """Check for server resource constraints"""
    print("\n🔍 Checking Server Resources...")
    
    # Test memory usage simulation
    def memory_test():
        large_list = list(range(100000))
        return len(large_list)
    
    result, duration = time_operation("Memory allocation test", memory_test)
    
    # Test multiple concurrent queries
    def concurrent_queries():
        results = []
        for i in range(5):
            results.append(db.session.execute(text("SELECT COUNT(*) FROM patient")).scalar())
        return results
    
    result, duration = time_operation("5 concurrent count queries", concurrent_queries)
    
    if duration > 1000:
        print("  ⚠️  Concurrent queries are slow - possible resource constraints")


def analyze_table_sizes():
    """Check if large tables are causing slowness"""
    print("\n📊 Analyzing Table Sizes...")
    
    tables = ['patient', 'treatment', '"user"', 'trigger_point', 'patient_reports']
    
    for table in tables:
        def count_table():
            return db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        
        count, duration = time_operation(f"Count {table} table", count_table)
        
        if count and count > 1000:
            print(f"    ⚠️  Large table: {table} has {count:,} records")
        
        if duration > 200:
            print(f"    ❌ Slow count on {table}: {duration:.1f}ms")


def test_without_relationships():
    """Test queries without loading relationships"""
    print("\n🔍 Testing Query Efficiency...")
    
    # Test with relationships loaded
    def with_relationships():
        return Patient.query.join(Treatment).limit(10).all()
    
    result, duration = time_operation("Query with relationships", with_relationships)
    
    # Test raw query
    def raw_query():
        return db.session.execute(text("SELECT id, name FROM patient LIMIT 10")).fetchall()
    
    result, duration = time_operation("Raw SQL query", raw_query)
    
    if duration < 50:
        print("  ✅ Raw queries are fast - SQLAlchemy ORM might be the bottleneck")
    else:
        print("  ⚠️  Even raw queries are slow - database server issue")


def main():
    print("🐌 Performance Debugging - Finding the Real Bottleneck")
    print("=" * 60)
    
    os.environ["DISABLE_ENCRYPTION"] = "true"
    app = create_app()
    
    with app.app_context():
        test_database_connection()
        test_common_queries()
        analyze_table_sizes()
        test_without_relationships()
        test_dashboard_simulation()
        check_server_resources()
        
        print("\n" + "=" * 60)
        print("🔍 Diagnosis:")
        print("If most operations are >500ms:")
        print("  💡 PythonAnywhere database server is slow")
        print("  💡 Consider upgrading PythonAnywhere plan")
        print("  💡 Or migrate to faster hosting (DigitalOcean, AWS)")
        print("\nIf only complex queries are slow:")
        print("  💡 Need query optimization and caching")
        print("  💡 Consider Redis for dashboard data")
        print("\nIf everything is fast here but web app is slow:")
        print("  💡 Network latency or template rendering issues")


if __name__ == "__main__":
    main() 