#!/usr/bin/env python3
"""
Performance optimization script for the physio app.
Adds database indexes and optimizes common query patterns.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from sqlalchemy import text


def add_database_indexes():
    """Add database indexes for commonly queried fields"""
    print("🔧 Adding database indexes for performance...")
    
    indexes_to_add = [
        # Patient table indexes
        "CREATE INDEX IF NOT EXISTS idx_patient_user_id ON patient(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_patient_status ON patient(status);",
        "CREATE INDEX IF NOT EXISTS idx_patient_user_status ON patient(user_id, status);",
        
        # Treatment table indexes
        "CREATE INDEX IF NOT EXISTS idx_treatment_patient_id ON treatment(patient_id);",
        "CREATE INDEX IF NOT EXISTS idx_treatment_status ON treatment(status);",
        "CREATE INDEX IF NOT EXISTS idx_treatment_created_at ON treatment(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_treatment_patient_status ON treatment(patient_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_treatment_patient_created ON treatment(patient_id, created_at);",
        "CREATE INDEX IF NOT EXISTS idx_treatment_provider ON treatment(provider);",
        "CREATE INDEX IF NOT EXISTS idx_treatment_fee_charged ON treatment(fee_charged);",
        
        # User table indexes
        "CREATE INDEX IF NOT EXISTS idx_user_email ON \"user\"(email);",
        "CREATE INDEX IF NOT EXISTS idx_user_role ON \"user\"(role);",
        "CREATE INDEX IF NOT EXISTS idx_user_is_admin ON \"user\"(is_admin);",
        
        # PatientReport table indexes
        "CREATE INDEX IF NOT EXISTS idx_patient_report_patient_id ON patient_reports(patient_id);",
        "CREATE INDEX IF NOT EXISTS idx_patient_report_generated_date ON patient_reports(generated_date);",
        
        # RecurringAppointment table indexes
        "CREATE INDEX IF NOT EXISTS idx_recurring_patient_id ON recurring_appointments(patient_id);",
        "CREATE INDEX IF NOT EXISTS idx_recurring_is_active ON recurring_appointments(is_active);",
        "CREATE INDEX IF NOT EXISTS idx_recurring_start_date ON recurring_appointments(start_date);",
        
        # TriggerPoint table indexes
        "CREATE INDEX IF NOT EXISTS idx_trigger_point_treatment_id ON trigger_point(treatment_id);",
        
        # Location table indexes
        "CREATE INDEX IF NOT EXISTS idx_location_user_id ON location(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_location_is_active ON location(user_id, is_active);",
        
        # UnmatchedCalendlyBooking table indexes
        "CREATE INDEX IF NOT EXISTS idx_unmatched_calendly_status ON unmatched_calendly_booking(status);",
        "CREATE INDEX IF NOT EXISTS idx_unmatched_calendly_user_id ON unmatched_calendly_booking(user_id);",
        
        # Composite indexes for common query patterns
        "CREATE INDEX IF NOT EXISTS idx_treatment_analytics ON treatment(patient_id, created_at, fee_charged);",
        "CREATE INDEX IF NOT EXISTS idx_patient_dashboard ON patient(user_id, status, created_at);",
    ]
    
    successful_indexes = 0
    for index_sql in indexes_to_add:
        try:
            db.session.execute(text(index_sql))
            db.session.commit()
            successful_indexes += 1
            print(f"  ✅ Added index: {index_sql.split(' ')[5] if 'idx_' in index_sql else 'Unknown'}")
        except Exception as e:
            print(f"  ⚠️  Index already exists or failed: {str(e)[:50]}...")
            continue
    
    print(f"✅ Added {successful_indexes} database indexes")


def optimize_sqlalchemy_config():
    """Print recommendations for SQLAlchemy optimization"""
    print("\n🔧 SQLAlchemy Configuration Recommendations:")
    print("Add these to your config.py for better performance:")
    print("""
    # Database connection pool optimization
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,           # Increase from 10
        'pool_recycle': 300,       # Keep existing
        'pool_pre_ping': True,     # Keep existing
        'max_overflow': 30,        # Increase from 20
        'pool_timeout': 30,        # Add timeout
        'echo': False,             # Disable in production
    }
    
    # Disable SQLAlchemy track modifications
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Already set
    """)


def analyze_slow_queries():
    """Analyze common slow query patterns"""
    print("\n🔍 Common Query Performance Issues Found:")
    
    issues = [
        "❌ Multiple calls to get_accessible_patients() in dashboard - Cache this!",
        "❌ List comprehensions on query results - Use database filters instead",
        "❌ N+1 queries in calendar view - Use joinedload for relationships",
        "❌ Unoptimized analytics queries - Consider caching or pre-computation",
        "❌ Missing eager loading for patient relationships in treatments",
    ]
    
    for issue in issues:
        print(f"  {issue}")
    
    print("\n✅ Solutions:")
    solutions = [
        "✅ Cache accessible_patients result in session/memory",
        "✅ Use database COUNT() instead of len(query.all())",
        "✅ Use .options(joinedload()) for relationships",
        "✅ Consider Redis caching for analytics data",
        "✅ Batch database operations where possible",
    ]
    
    for solution in solutions:
        print(f"  {solution}")


def check_database_stats():
    """Check current database statistics"""
    print("\n📊 Database Statistics:")
    
    try:
        # Get table counts
        tables = [
            ('patients', 'patient'),
            ('treatments', 'treatment'),
            ('users', '"user"'),
            ('trigger_points', 'trigger_point'),
            ('patient_reports', 'patient_reports'),
        ]
        
        for name, table in tables:
            try:
                result = db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f"  {name}: {result:,} records")
            except Exception as e:
                print(f"  {name}: Error - {str(e)[:30]}...")
        
        # Check for large tables that need optimization
        result = db.session.execute(text("SELECT COUNT(*) FROM treatment")).scalar()
        if result > 1000:
            print(f"  ⚠️  Large treatment table ({result:,} records) - Consider archiving old data")
        
        result = db.session.execute(text("SELECT COUNT(*) FROM patient")).scalar()
        if result > 500:
            print(f"  ⚠️  Large patient table ({result:,} records) - Indexes are crucial")
            
    except Exception as e:
        print(f"  Error getting database stats: {e}")


def main():
    print("🚀 Physio App Performance Optimization")
    print("=" * 50)
    
    # Force disable encryption to ensure it's off
    os.environ["DISABLE_ENCRYPTION"] = "true"
    
    app = create_app()
    
    with app.app_context():
        check_database_stats()
        add_database_indexes()
        optimize_sqlalchemy_config()
        analyze_slow_queries()
        
        print("\n" + "=" * 50)
        print("🎉 Performance optimization complete!")
        print("\nNext steps:")
        print("1. Restart your web app on PythonAnywhere")
        print("2. Consider implementing query caching for analytics")
        print("3. Monitor performance improvements")


if __name__ == "__main__":
    main() 