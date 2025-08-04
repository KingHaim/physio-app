"""
Migration script to move existing users to separated Individual and Clinic plans.

This script:
1. Identifies existing user subscriptions
2. Determines if they should be on individual or clinic plans
3. Migrates them to the appropriate new plan structure
"""

import os
from app import create_app, db
from app.models import User, Plan, UserSubscription, ClinicSubscription, Clinic
from datetime import datetime

def analyze_existing_subscriptions():
    """Analyze existing subscriptions to understand current state."""
    app = create_app()
    with app.app_context():
        print("=== ANALYZING EXISTING SUBSCRIPTIONS ===\n")
        
        # Get all active subscriptions
        active_user_subscriptions = UserSubscription.query.filter(
            UserSubscription.status.in_(['active', 'trialing'])
        ).all()
        
        active_clinic_subscriptions = ClinicSubscription.query.filter(
            ClinicSubscription.status.in_(['active', 'trialing'])
        ).all()
        
        print(f"Active User Subscriptions: {len(active_user_subscriptions)}")
        print(f"Active Clinic Subscriptions: {len(active_clinic_subscriptions)}")
        
        # Analyze user subscriptions
        individual_users = []
        clinic_users = []
        
        for subscription in active_user_subscriptions:
            user = subscription.user
            if user.is_in_clinic:
                clinic_users.append({
                    'user': user,
                    'subscription': subscription,
                    'clinic': user.clinic
                })
            else:
                individual_users.append({
                    'user': user,
                    'subscription': subscription
                })
        
        print(f"\nUsers who should be on Individual plans: {len(individual_users)}")
        print(f"Users who should be on Clinic plans: {len(clinic_users)}")
        
        # Show current plans
        current_plans = Plan.query.filter_by(is_active=True).all()
        print(f"\nCurrent active plans: {len(current_plans)}")
        for plan in current_plans:
            print(f"  - {plan.name} ({plan.slug}) - Type: {plan.plan_type}")
        
        return {
            'individual_users': individual_users,
            'clinic_users': clinic_users,
            'active_user_subscriptions': active_user_subscriptions,
            'active_clinic_subscriptions': active_clinic_subscriptions
        }

def map_old_plans_to_new():
    """Map old plan names to new plan slugs."""
    app = create_app()
    with app.app_context():
        old_to_new_mapping = {
            # Old plan slugs to new plan slugs
            'basic-usd': 'individual-basic-usd',
            'standard-usd': 'individual-pro-usd',  # Standard becomes Individual Pro
            'premium-usd': 'clinic-starter-usd',   # Premium becomes Clinic Starter
            'pro-monthly': 'individual-pro-usd',
            'basic-monthly': 'individual-basic-usd',
            'clinic-monthly': 'clinic-starter-usd'
        }
        
        return old_to_new_mapping

def migrate_individual_subscriptions(individual_users, dry_run=True):
    """Migrate individual users to Individual plans."""
    print(f"\n=== MIGRATING {len(individual_users)} INDIVIDUAL SUBSCRIPTIONS ===")
    
    mapping = map_old_plans_to_new()
    migrated = 0
    
    for user_data in individual_users:
        user = user_data['user']
        old_subscription = user_data['subscription']
        old_plan = old_subscription.plan
        
        # Determine new plan
        new_plan_slug = mapping.get(old_plan.slug)
        if not new_plan_slug:
            # Default mapping based on patient limits
            if old_plan.patient_limit and old_plan.patient_limit <= 50:
                new_plan_slug = 'individual-basic-usd'
            else:
                new_plan_slug = 'individual-pro-usd'
        
        new_plan = Plan.query.filter_by(slug=new_plan_slug, plan_type='individual').first()
        
        if not new_plan:
            print(f"  ❌ No new plan found for user {user.id} (old: {old_plan.slug})")
            continue
        
        print(f"  👤 User {user.id} ({user.email}): {old_plan.slug} → {new_plan.slug}")
        
        if not dry_run:
            # Update the subscription to use the new plan
            old_subscription.plan_id = new_plan.id
            db.session.commit()
            migrated += 1
    
    if dry_run:
        print(f"\n  📋 DRY RUN: Would migrate {len(individual_users)} individual subscriptions")
    else:
        print(f"\n  ✅ Successfully migrated {migrated} individual subscriptions")

def migrate_clinic_subscriptions(clinic_users, dry_run=True):
    """Migrate clinic users to Clinic plans."""
    print(f"\n=== MIGRATING {len(clinic_users)} CLINIC SUBSCRIPTIONS ===")
    
    # Group by clinic
    clinics_to_migrate = {}
    for user_data in clinic_users:
        clinic = user_data['clinic']
        if clinic.id not in clinics_to_migrate:
            clinics_to_migrate[clinic.id] = {
                'clinic': clinic,
                'users': [],
                'admin_subscription': None
            }
        
        clinics_to_migrate[clinic.id]['users'].append(user_data)
        
        # Find the admin's subscription (we'll convert this to clinic subscription)
        if user_data['user'].is_clinic_admin:
            clinics_to_migrate[clinic.id]['admin_subscription'] = user_data['subscription']
    
    migrated_clinics = 0
    
    for clinic_id, clinic_data in clinics_to_migrate.items():
        clinic = clinic_data['clinic']
        admin_subscription = clinic_data['admin_subscription']
        users = clinic_data['users']
        
        if not admin_subscription:
            print(f"  ❌ No admin subscription found for clinic {clinic.id} ({clinic.name})")
            continue
        
        # Determine appropriate clinic plan
        total_users = len(users)
        old_plan = admin_subscription.plan
        
        if total_users <= 5:
            new_plan_slug = 'clinic-starter-usd'
        else:
            new_plan_slug = 'clinic-enterprise-usd'
        
        new_plan = Plan.query.filter_by(slug=new_plan_slug, plan_type='clinic').first()
        
        if not new_plan:
            print(f"  ❌ No new clinic plan found: {new_plan_slug}")
            continue
        
        print(f"  🏥 Clinic {clinic.id} ({clinic.name}): {total_users} users")
        print(f"      {old_plan.slug} → {new_plan.slug}")
        
        if not dry_run:
            # Create new clinic subscription
            new_clinic_subscription = ClinicSubscription(
                clinic_id=clinic.id,
                plan_id=new_plan.id,
                stripe_subscription_id=admin_subscription.stripe_subscription_id,
                status=admin_subscription.status,
                trial_starts_at=admin_subscription.trial_starts_at,
                trial_ends_at=admin_subscription.trial_ends_at,
                current_period_starts_at=admin_subscription.current_period_starts_at,
                current_period_ends_at=admin_subscription.current_period_ends_at,
                cancel_at_period_end=admin_subscription.cancel_at_period_end,
                canceled_at=admin_subscription.canceled_at,
                ended_at=admin_subscription.ended_at,
                created_at=admin_subscription.created_at
            )
            db.session.add(new_clinic_subscription)
            
            # Cancel all individual subscriptions for this clinic's users
            for user_data in users:
                user_subscription = user_data['subscription']
                user_subscription.status = 'canceled'
            
            db.session.commit()
            migrated_clinics += 1
    
    if dry_run:
        print(f"\n  📋 DRY RUN: Would migrate {len(clinics_to_migrate)} clinics")
    else:
        print(f"\n  ✅ Successfully migrated {migrated_clinics} clinic subscriptions")

def run_migration(dry_run=True):
    """Run the complete migration process."""
    print("🔄 STARTING PLAN SEPARATION MIGRATION")
    print("=====================================")
    
    if dry_run:
        print("🚧 RUNNING IN DRY RUN MODE - No changes will be made")
    else:
        print("⚠️  RUNNING IN LIVE MODE - Changes will be applied!")
        confirm = input("Are you sure you want to proceed? (type 'YES' to confirm): ")
        if confirm != 'YES':
            print("❌ Migration cancelled")
            return
    
    print()
    
    # Analyze current state
    analysis = analyze_existing_subscriptions()
    
    # Migrate individual subscriptions
    migrate_individual_subscriptions(analysis['individual_users'], dry_run)
    
    # Migrate clinic subscriptions
    migrate_clinic_subscriptions(analysis['clinic_users'], dry_run)
    
    print("\n" + "="*50)
    if dry_run:
        print("📋 DRY RUN COMPLETED")
        print("Run with dry_run=False to apply changes")
    else:
        print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
    print("="*50)

if __name__ == '__main__':
    import sys
    
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == '--apply':
        dry_run = False
    
    run_migration(dry_run=dry_run) 