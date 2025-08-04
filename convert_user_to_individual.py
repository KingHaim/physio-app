"""
Script to convert a user from clinic setup to individual setup.

This will:
1. Remove the user from clinic membership
2. Handle other clinic members appropriately
3. Set them up as an individual user
"""

import os
from app import create_app, db
from app.models import User, Clinic, ClinicMembership, ClinicSubscription
from datetime import datetime

def convert_user_to_individual(email, dry_run=True):
    """Convert a user from clinic to individual setup."""
    app = create_app()
    with app.app_context():
        print(f"🔄 Converting {email} to individual user")
        print("=" * 50)
        
        # Find the user
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"❌ User {email} not found")
            return
        
        print(f"👤 User: {user.first_name} {user.last_name} (ID: {user.id})")
        
        # Check current clinic status
        memberships = ClinicMembership.query.filter_by(user_id=user.id, is_active=True).all()
        
        if not memberships:
            print("✅ User is already not in any clinic")
            return
        
        for membership in memberships:
            clinic = Clinic.query.get(membership.clinic_id)
            print(f"\n🏥 Current clinic: {clinic.name} (ID: {clinic.id})")
            print(f"   Role: {membership.role}")
            
            # Check other members in this clinic
            other_members = ClinicMembership.query.filter(
                ClinicMembership.clinic_id == clinic.id,
                ClinicMembership.user_id != user.id,
                ClinicMembership.is_active == True
            ).all()
            
            print(f"   Other members: {len(other_members)}")
            for other_member in other_members:
                other_user = User.query.get(other_member.user_id)
                print(f"     - {other_user.email} ({other_member.role})")
            
            # Check clinic subscriptions
            clinic_subs = ClinicSubscription.query.filter_by(clinic_id=clinic.id).all()
            active_clinic_subs = [s for s in clinic_subs if s.status in ['active', 'trialing']]
            
            print(f"   Active clinic subscriptions: {len(active_clinic_subs)}")
            
            if not dry_run:
                # Remove user from clinic
                print(f"\n🔧 Removing {email} from clinic {clinic.name}...")
                membership.is_active = False
                membership.left_at = datetime.utcnow()
                
                # If this was the only member, we could deactivate the clinic
                if len(other_members) == 0:
                    print("   No other members - marking clinic as inactive")
                    clinic.is_active = False
                    
                    # Cancel any clinic subscriptions
                    for sub in active_clinic_subs:
                        sub.status = 'canceled'
                        sub.canceled_at = datetime.utcnow()
                elif membership.role == 'admin' and len(other_members) > 0:
                    # If removing an admin and there are other members, promote someone
                    print("   User was admin - promoting another member to admin")
                    next_admin = other_members[0]  # Promote the first other member
                    next_admin.role = 'admin'
                    next_admin.can_manage_practitioners = True
                    next_admin.can_manage_settings = True
                    next_admin.can_manage_billing = True
                    other_admin_user = User.query.get(next_admin.user_id)
                    print(f"   Promoted {other_admin_user.email} to admin")
                
                db.session.commit()
                print(f"✅ Successfully removed {email} from clinic")
        
        if not dry_run:
            print(f"\n🎯 {email} is now set up as an individual user")
            print("   They can now:")
            print("   - Subscribe to Individual plans")
            print("   - Use individual pricing at /pricing/individual")
            print("   - Access individual dashboard")
        else:
            print(f"\n📋 DRY RUN: Would convert {email} to individual user")
            print("   Use dry_run=False to apply changes")

def main():
    import sys
    
    email = "jaimeganancia@hotmail.com"
    dry_run = True
    
    if len(sys.argv) > 1 and sys.argv[1] == '--apply':
        dry_run = False
        print("⚠️  APPLYING CHANGES!")
        confirm = input(f"Are you sure you want to convert {email} to individual? (type 'YES'): ")
        if confirm != 'YES':
            print("❌ Cancelled")
            return
    else:
        print("🚧 DRY RUN MODE - Add --apply to make changes")
    
    convert_user_to_individual(email, dry_run)

if __name__ == '__main__':
    main() 