import os
from app import create_app, db
from app.models import User, UserSubscription, Plan

# --- Configuration ---
USERNAME_TO_CHECK = 'haim'
# -------------------

def check_subscription():
    app = create_app()
    with app.app_context():
        print(f"Attempting to find user: '{USERNAME_TO_CHECK}'")
        user = User.query.filter_by(username=USERNAME_TO_CHECK).first()

        if not user:
            print(f"User '{USERNAME_TO_CHECK}' not found in the database.")
            return

        print(f"Checking subscriptions for user: {user.username} (ID: {user.id})")

        # Find all subscriptions for this user
        all_subs = UserSubscription.query.filter_by(user_id=user.id).all()

        if not all_subs:
            print("No UserSubscription records found for this user.")
        else:
            print(f"Found {len(all_subs)} subscription record(s):")
            for sub in all_subs:
                # Fetch plan name safely
                plan = Plan.query.get(sub.plan_id)
                plan_name = plan.name if plan else "Unknown Plan (ID not found)"
                print(f"  - Sub ID: {sub.id}, Plan ID: {sub.plan_id} ({plan_name}), Status: '{sub.status}', Created: {sub.created_at}")

        # Explicitly check the result of the properties for this specific user object
        try:
            active_sub_check = user.active_subscription
            plan_name_check = user.active_subscription_plan_name
            print(f"\nResult of user.active_subscription property: {active_sub_check}")
            print(f"Result of user.active_subscription_plan_name property: {plan_name_check}")
        except Exception as e:
            print(f"\nError accessing user subscription properties: {e}")

if __name__ == "__main__":
    # Add dotenv loading if needed for your app config
    # from dotenv import load_dotenv
    # load_dotenv()
    check_subscription() 