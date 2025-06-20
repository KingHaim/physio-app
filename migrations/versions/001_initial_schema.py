"""Initial database schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-01-20 23:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create user table
    op.create_table('user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('is_admin', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('first_name', sa.String(length=64), nullable=True),
        sa.Column('last_name', sa.String(length=64), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('sex', sa.String(length=16), nullable=True),
        sa.Column('license_number', sa.String(length=64), nullable=True),
        sa.Column('clinic_name', sa.String(length=150), nullable=True),
        sa.Column('clinic_address', sa.String(length=200), nullable=True),
        sa.Column('clinic_phone', sa.String(length=30), nullable=True),
        sa.Column('clinic_email', sa.String(length=120), nullable=True),
        sa.Column('clinic_website', sa.String(length=120), nullable=True),
        sa.Column('clinic_description', sa.Text(), nullable=True),
        sa.Column('contribution_base', sa.Float(), nullable=True),
        sa.Column('clinic_first_session_fee', sa.Float(), nullable=True),
        sa.Column('clinic_subsequent_session_fee', sa.Float(), nullable=True),
        sa.Column('clinic_percentage_agreement', sa.Boolean(), nullable=True),
        sa.Column('clinic_percentage_amount', sa.Float(), nullable=True),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('calendly_api_key', sa.String(length=255), nullable=True),
        sa.Column('calendly_user_uri', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=True),
        sa.Column('language', sa.String(length=5), nullable=True),
        sa.Column('consent_given', sa.Boolean(), nullable=True),
        sa.Column('consent_date', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    op.create_index(op.f('ix_user_stripe_customer_id'), 'user', ['stripe_customer_id'], unique=True)
    op.create_index(op.f('ix_user_username'), 'user', ['username'], unique=True)

    # Create patient table
    op.create_table('patient',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('portal_user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('contact', sa.String(length=100), nullable=True),
        sa.Column('diagnosis', sa.String(length=200), nullable=True),
        sa.Column('treatment_plan', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('address_line1', sa.String(length=100), nullable=True),
        sa.Column('address_line2', sa.String(length=100), nullable=True),
        sa.Column('city', sa.String(length=50), nullable=True),
        sa.Column('postcode', sa.String(length=20), nullable=True),
        sa.Column('preferred_location', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['portal_user_id'], ['user.id'], name='fk_portal_user_id_user'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('portal_user_id')
    )

    # Create treatment table
    op.create_table('treatment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('treatment_type', sa.String(length=100), nullable=False),
        sa.Column('assessment', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('provider', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('body_chart_url', sa.String(length=255), nullable=True),
        sa.Column('pain_level', sa.Integer(), nullable=True),
        sa.Column('movement_restriction', sa.String(length=50), nullable=True),
        sa.Column('evaluation_data', sa.JSON(), nullable=True),
        sa.Column('location', sa.String(length=100), nullable=True),
        sa.Column('visit_type', sa.String(length=50), nullable=True),
        sa.Column('fee_charged', sa.Float(), nullable=True),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('calendly_invitee_uri', sa.String(length=255), nullable=True),
        sa.Column('clinic_share', sa.Float(), nullable=True),
        sa.Column('therapist_share', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_treatment_calendly_invitee_uri'), 'treatment', ['calendly_invitee_uri'], unique=True)

    # Create trigger_point table
    op.create_table('trigger_point',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('treatment_id', sa.Integer(), nullable=False),
        sa.Column('location_x', sa.Float(), nullable=False),
        sa.Column('location_y', sa.Float(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=True),
        sa.Column('muscle', sa.String(length=100), nullable=True),
        sa.Column('intensity', sa.Integer(), nullable=True),
        sa.Column('symptoms', sa.Text(), nullable=True),
        sa.Column('referral_pattern', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['treatment_id'], ['treatment.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create unmatched_calendly_booking table
    op.create_table('unmatched_calendly_booking',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('calendly_invitee_id', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('matched_patient_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['matched_patient_id'], ['patient.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create patient_reports table
    op.create_table('patient_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('generated_date', sa.DateTime(), nullable=True),
        sa.Column('report_type', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create recurring_appointment table
    op.create_table('recurring_appointment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('recurrence_type', sa.String(length=50), nullable=False),
        sa.Column('time_of_day', sa.Time(), nullable=False),
        sa.Column('treatment_type', sa.String(length=150), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('location', sa.String(length=100), nullable=True),
        sa.Column('provider', sa.String(length=100), nullable=True),
        sa.Column('fee_charged', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create practice_reports table
    op.create_table('practice_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create plans table
    op.create_table('plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('price_cents', sa.Integer(), nullable=False),
        sa.Column('billing_interval', sa.String(length=50), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('patient_limit', sa.Integer(), nullable=True),
        sa.Column('practitioner_limit', sa.Integer(), nullable=True),
        sa.Column('features', sa.JSON(), nullable=True),
        sa.Column('stripe_price_id', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plans_slug'), 'plans', ['slug'], unique=True)
    op.create_index(op.f('ix_plans_stripe_price_id'), 'plans', ['stripe_price_id'], unique=True)

    # Create user_subscriptions table
    op.create_table('user_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('trial_starts_at', sa.DateTime(), nullable=True),
        sa.Column('trial_ends_at', sa.DateTime(), nullable=True),
        sa.Column('current_period_starts_at', sa.DateTime(), nullable=True),
        sa.Column('current_period_ends_at', sa.DateTime(), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False),
        sa.Column('canceled_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_subscriptions_stripe_subscription_id'), 'user_subscriptions', ['stripe_subscription_id'], unique=True)
    op.create_index(op.f('ix_user_subscriptions_user_id'), 'user_subscriptions', ['user_id'], unique=False)

    # Create fixed_cost table
    op.create_table('fixed_cost',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(length=150), nullable=False),
        sa.Column('monthly_amount', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create data_processing_activity table
    op.create_table('data_processing_activity',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('activity_type', sa.String(length=50), nullable=False),
        sa.Column('data_categories', sa.String(length=200), nullable=False),
        sa.Column('purpose', sa.String(length=200), nullable=False),
        sa.Column('retention_period', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create user_consent table
    op.create_table('user_consent',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('purpose', sa.String(length=50), nullable=False),
        sa.Column('given_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create security_log table
    op.create_table('security_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=200), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create security_breach table
    op.create_table('security_breach',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('breach_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('affected_users', sa.Integer(), nullable=False),
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_details', sa.Text(), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), nullable=True),
        sa.Column('notification_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    # Drop tables in reverse order
    op.drop_table('security_breach')
    op.drop_table('security_log')
    op.drop_table('user_consent')
    op.drop_table('data_processing_activity')
    op.drop_table('fixed_cost')
    op.drop_index(op.f('ix_user_subscriptions_user_id'), table_name='user_subscriptions')
    op.drop_index(op.f('ix_user_subscriptions_stripe_subscription_id'), table_name='user_subscriptions')
    op.drop_table('user_subscriptions')
    op.drop_index(op.f('ix_plans_stripe_price_id'), table_name='plans')
    op.drop_index(op.f('ix_plans_slug'), table_name='plans')
    op.drop_table('plans')
    op.drop_table('practice_reports')
    op.drop_table('recurring_appointment')
    op.drop_table('patient_reports')
    op.drop_table('unmatched_calendly_booking')
    op.drop_table('trigger_point')
    op.drop_index(op.f('ix_treatment_calendly_invitee_uri'), table_name='treatment')
    op.drop_table('treatment')
    op.drop_table('patient')
    op.drop_index(op.f('ix_user_username'), table_name='user')
    op.drop_index(op.f('ix_user_stripe_customer_id'), table_name='user')
    op.drop_index(op.f('ix_user_email'), table_name='user')
    op.drop_table('user') 