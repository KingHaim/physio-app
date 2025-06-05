# app/routes/webhooks.py
from flask import Blueprint, request, current_app, jsonify, abort
import logging
import stripe # Import the stripe library
from app import csrf # Import the CSRF object
from app.models import User, Plan, UserSubscription # Add these
from app import db # Add this
from datetime import datetime # Add this

# It's good practice to get a specific logger for your module/blueprint
logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')

@webhook_bp.route('/stripe', methods=['POST'])
@csrf.exempt # Exempt this route from CSRF protection
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')

    if not webhook_secret:
        logger.error("Stripe webhook secret is not configured.")
        abort(500) # Internal server error

    if not payload or not sig_header:
        logger.warning("Webhook request missing payload or signature header.")
        abort(400) # Bad request

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        logger.warning(f"Invalid webhook payload: {e}")
        abort(400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.warning(f"Invalid webhook signature: {e}")
        abort(400)
    except Exception as e:
        logger.error(f"Error constructing webhook event: {e}")
        abort(500)

    # At this point, the event is verified and can be processed
    logger.info(f"Stripe webhook received and verified. Event ID: {event.id}, Event Type: {event.type}")

    # Handle the event (add specific handlers later)
    if event.type == 'checkout.session.completed':
        session_from_webhook = event.data.object # This is a Stripe Checkout Session object from the webhook
        checkout_session_id = session_from_webhook.id
        logger.info(f"Processing checkout.session.completed for session ID: {checkout_session_id}")

        try:
            # Retrieve the full session object from Stripe to ensure all necessary data is present
            # This requires your Stripe API key to be configured (usually via STRIPE_SECRET_KEY env var)
            full_checkout_session = stripe.checkout.Session.retrieve(
                checkout_session_id,
                expand=['line_items', 'subscription', 'customer']
            )

            client_reference_id = full_checkout_session.client_reference_id
            stripe_customer_id = full_checkout_session.customer.id if full_checkout_session.customer else None # Stripe Customer ID
            stripe_subscription_obj = full_checkout_session.subscription # This is a Stripe Subscription object if mode was 'subscription'

            if not client_reference_id:
                logger.error(f"Missing client_reference_id in checkout session {checkout_session_id}")
                return jsonify(status="error", reason="Missing client_reference_id"), 400

            user_id = None
            try:
                user_id = int(client_reference_id)
            except ValueError:
                logger.error(f"Invalid client_reference_id (not an int): {client_reference_id} in session {checkout_session_id}")
                return jsonify(status="error", reason="Invalid client_reference_id format"), 400

            user = User.query.get(user_id)
            if not user:
                logger.error(f"User not found for client_reference_id: {user_id} in session {checkout_session_id}")
                # If user is not found, this is a critical issue. Potentially an orphaned payment.
                return jsonify(status="error", reason="User not found"), 400 # Or 500, as it's an inconsistency

            # Save Stripe Customer ID to the user
            if stripe_customer_id and not user.stripe_customer_id:
                user.stripe_customer_id = stripe_customer_id
                # db.session.commit() # Commit will happen later with subscription
                logger.info(f"Associated Stripe Customer ID {stripe_customer_id} with user {user.id}")
            elif stripe_customer_id and user.stripe_customer_id and user.stripe_customer_id != stripe_customer_id:
                # This case might indicate an issue, e.g., a user somehow getting two different Stripe customer IDs.
                logger.warning(f"User {user.id} already has Stripe Customer ID {user.stripe_customer_id}, but webhook provided {stripe_customer_id}. Using the newer one for now.")
                user.stripe_customer_id = stripe_customer_id
            elif not stripe_customer_id:
                logger.warning(f"No Stripe Customer ID (full_checkout_session.customer) found in checkout session {checkout_session_id} for user {user.id}. Portal link might not work.")

            if not full_checkout_session.line_items or not full_checkout_session.line_items.data:
                logger.error(f"No line items found in checkout session {checkout_session_id}")
                return jsonify(status="error", reason="No line items in session"), 400
            
            # Assuming the first line item contains the primary plan
            stripe_price_id = full_checkout_session.line_items.data[0].price.id
            if not stripe_price_id:
                logger.error(f"No Stripe Price ID found in line items for session {checkout_session_id}")
                return jsonify(status="error", reason="Missing Stripe Price ID in line items"), 400

            plan = Plan.query.filter_by(stripe_price_id=stripe_price_id).first()
            if not plan:
                logger.error(f"Plan not found for Stripe Price ID: {stripe_price_id} (from session {checkout_session_id}). Ensure this price ID is in your app's Plan table.")
                return jsonify(status="error", reason="Plan not found for Stripe Price ID"), 400 # Or 500

            if not stripe_subscription_obj:
                logger.error(f"No Stripe subscription object (stripe_subscription_obj) found in checkout session {checkout_session_id}. This webhook currently primarily handles subscription creations. Checkout mode was likely not 'subscription'.")
                # For one-time payments, different logic would be needed.
                # For now, if it's a plan that should be a subscription, this is an issue.
                return jsonify(status="error", reason="Subscription object missing from checkout session"), 400

            # Deactivate any other existing active/trialing subscriptions for this user.
            # This is a simple approach. Stripe's proration/upgrade features might handle this on their end
            # depending on how the new Checkout Session was created.
            # This ensures our DB reflects the latest single active subscription.
            existing_active_subscriptions = UserSubscription.query.filter_by(user_id=user.id).filter(
                UserSubscription.status.in_(['active', 'trialing'])
            ).all()
            for sub_to_deactivate in existing_active_subscriptions:
                if sub_to_deactivate.stripe_subscription_id != stripe_subscription_obj.id: # Don't deactivate the one we are currently processing
                    logger.info(f"Deactivating existing subscription {sub_to_deactivate.id} (Stripe ID: {sub_to_deactivate.stripe_subscription_id}) for user {user.id} as new subscription {stripe_subscription_obj.id} is being activated.")
                    sub_to_deactivate.status = 'canceled' # Or a more specific status like 'superceded'
                    sub_to_deactivate.ended_at = datetime.utcnow()
                    sub_to_deactivate.cancel_at_period_end = False # Ensure it's marked as immediately ended from our perspective.
            
            # Check if this specific subscription already exists to avoid duplicates from webhook retries
            existing_specific_subscription = UserSubscription.query.filter_by(stripe_subscription_id=stripe_subscription_obj.id).first()
            if existing_specific_subscription:
                logger.info(f"Subscription with Stripe ID {stripe_subscription_obj.id} already processed. Current status: {existing_specific_subscription.status}. Updating if needed.")
                # Optionally, update status and period dates if they changed, though Stripe webhooks for subscription.updated should handle that.
                # For checkout.session.completed, idempotency is mainly about not creating duplicates.
                existing_specific_subscription.status = stripe_subscription_obj.status
                existing_specific_subscription.current_period_starts_at=datetime.utcfromtimestamp(stripe_subscription_obj.current_period_start) if stripe_subscription_obj.current_period_start else None
                existing_specific_subscription.current_period_ends_at=datetime.utcfromtimestamp(stripe_subscription_obj.current_period_end) if stripe_subscription_obj.current_period_end else None
                existing_specific_subscription.trial_starts_at=datetime.utcfromtimestamp(stripe_subscription_obj.trial_start) if stripe_subscription_obj.trial_start else None
                existing_specific_subscription.trial_ends_at=datetime.utcfromtimestamp(stripe_subscription_obj.trial_end) if stripe_subscription_obj.trial_end else None
                existing_specific_subscription.cancel_at_period_end=stripe_subscription_obj.cancel_at_period_end
                db.session.commit()
                logger.info(f"Updated existing UserSubscription {existing_specific_subscription.id} for Stripe Sub ID {stripe_subscription_obj.id}. New status: {stripe_subscription_obj.status}")
            else:
                # Create a new UserSubscription record
                new_db_subscription = UserSubscription(
                    user_id=user.id,
                    plan_id=plan.id,
                    stripe_subscription_id=stripe_subscription_obj.id,
                    status=stripe_subscription_obj.status, 
                    current_period_starts_at=datetime.utcfromtimestamp(stripe_subscription_obj.current_period_start) if stripe_subscription_obj.current_period_start else None,
                    current_period_ends_at=datetime.utcfromtimestamp(stripe_subscription_obj.current_period_end) if stripe_subscription_obj.current_period_end else None,
                    trial_starts_at=datetime.utcfromtimestamp(stripe_subscription_obj.trial_start) if stripe_subscription_obj.trial_start else None,
                    trial_ends_at=datetime.utcfromtimestamp(stripe_subscription_obj.trial_end) if stripe_subscription_obj.trial_end else None,
                    cancel_at_period_end=stripe_subscription_obj.cancel_at_period_end,
                )
                db.session.add(new_db_subscription)
                db.session.commit()
                logger.info(f"Successfully created new UserSubscription (ID: {new_db_subscription.id}) for user {user.id} with plan '{plan.name}'. Stripe Sub ID: {stripe_subscription_obj.id}. Status: {stripe_subscription_obj.status}")

        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error while processing session {checkout_session_id}: {str(e)}", exc_info=True)
            # Don't rollback here as the session might not have started or the error is before DB ops
            return jsonify(status="error", reason=f"Stripe API error: {str(e)}"), 500 # Use 500 for Stripe API issues preventing processing
        except Exception as e:
            logger.error(f"Unexpected error processing checkout session {checkout_session_id}: {str(e)}", exc_info=True)
            db.session.rollback() # Rollback in case of DB error during commit or other unexpected issues
            return jsonify(status="error", reason=f"Unexpected internal error: {str(e)}"), 500
        
        # logger.info(f"Checkout session completed: {session_from_webhook.id}") # Covered by more specific logging above
        # TODO: Fulfill the purchase (Done above)
    # Add other event types to handle as needed
    # elif event.type == 'invoice.paid':
    else:
        logger.info(f"Received unhandled event type: {event.type}")

    return jsonify(status="success", event_id=event.id), 200 