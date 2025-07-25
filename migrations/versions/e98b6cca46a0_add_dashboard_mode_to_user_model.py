"""add dashboard_mode to user model

Revision ID: e98b6cca46a0
Revises: ef95bfd223e1
Create Date: 2025-07-20 18:41:36.615132

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e98b6cca46a0'
down_revision = 'ef95bfd223e1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # Skip dropping temp table if it doesn't exist
    try:
        op.drop_table('_alembic_tmp_patient')
    except:
        pass
    with op.batch_alter_table('clinic_memberships', schema=None) as batch_op:
        batch_op.create_index('idx_user_clinic_active', ['user_id', 'clinic_id'], unique=False, postgresql_where=sa.text('user_id IS NOT NULL'))

    with op.batch_alter_table('patient', schema=None) as batch_op:
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('name',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=500),
               existing_nullable=False)
        batch_op.alter_column('email',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=500),
               existing_nullable=True)
        batch_op.alter_column('phone',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=500),
               existing_nullable=True)
        batch_op.create_unique_constraint(None, ['portal_user_id'])
        batch_op.create_foreign_key('fk_portal_user_id_user', 'user', ['portal_user_id'], ['id'], use_alter=True)
        batch_op.create_foreign_key(None, 'user', ['user_id'], ['id'])

    with op.batch_alter_table('practice_reports', schema=None) as batch_op:
        batch_op.create_foreign_key(None, 'user', ['user_id'], ['id'])

    with op.batch_alter_table('recurring_appointment', schema=None) as batch_op:
        batch_op.create_foreign_key(None, 'location', ['location_id'], ['id'])

    with op.batch_alter_table('security_log', schema=None) as batch_op:
        batch_op.alter_column('id',
               existing_type=sa.INTEGER(),
               nullable=False,
               autoincrement=True)
        batch_op.alter_column('event_type',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)
        batch_op.alter_column('user_agent',
               existing_type=sa.TEXT(),
               type_=sa.String(length=200),
               existing_nullable=True)

    with op.batch_alter_table('treatment', schema=None) as batch_op:
        batch_op.alter_column('movement_restriction',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.String(length=255),
               existing_nullable=True)
        batch_op.drop_index(batch_op.f('ix_treatment_calendly_invitee_uri'))
        batch_op.create_index(batch_op.f('ix_treatment_calendly_invitee_uri'), ['calendly_invitee_uri'], unique=False)
        batch_op.create_foreign_key(None, 'location', ['location_id'], ['id'])

    with op.batch_alter_table('unmatched_calendly_booking', schema=None) as batch_op:
        batch_op.create_foreign_key(None, 'user', ['user_id'], ['id'])

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('password_hash',
               existing_type=sa.VARCHAR(length=256),
               type_=sa.String(length=255),
               existing_nullable=True)
        batch_op.alter_column('email_verified',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('1'))
        batch_op.alter_column('email_verification_token',
               existing_type=sa.VARCHAR(length=256),
               type_=sa.String(length=255),
               existing_nullable=True)
        batch_op.alter_column('sex',
               existing_type=sa.VARCHAR(length=10),
               type_=sa.String(length=16),
               existing_nullable=True)
        batch_op.alter_column('clinic_name',
               existing_type=sa.VARCHAR(length=128),
               type_=sa.String(length=150),
               existing_nullable=True)
        batch_op.alter_column('clinic_address',
               existing_type=sa.TEXT(),
               type_=sa.String(length=200),
               existing_nullable=True)
        batch_op.alter_column('clinic_phone',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=30),
               existing_nullable=True)
        batch_op.alter_column('clinic_website',
               existing_type=sa.VARCHAR(length=256),
               type_=sa.String(length=120),
               existing_nullable=True)
        batch_op.alter_column('clinic_percentage_agreement',
               existing_type=sa.FLOAT(),
               type_=sa.Boolean(),
               existing_nullable=True)
        batch_op.alter_column('tax_brackets',
               existing_type=sa.TEXT(),
               type_=sa.JSON(),
               existing_nullable=True)
        batch_op.alter_column('stripe_customer_id',
               existing_type=sa.VARCHAR(length=256),
               type_=sa.String(length=255),
               existing_nullable=True)
        batch_op.alter_column('calendly_api_key',
               existing_type=sa.VARCHAR(length=256),
               type_=sa.String(length=255),
               existing_nullable=True)
        batch_op.alter_column('calendly_user_uri',
               existing_type=sa.VARCHAR(length=256),
               type_=sa.String(length=255),
               existing_nullable=True)
        batch_op.alter_column('role',
               existing_type=sa.VARCHAR(length=20),
               nullable=True,
               existing_server_default=sa.text("'physio'"))
        batch_op.alter_column('language',
               existing_type=sa.VARCHAR(length=10),
               type_=sa.String(length=5),
               existing_nullable=True,
               existing_server_default=sa.text('("en")'))
        batch_op.alter_column('oauth_provider',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=50),
               existing_nullable=True)
        batch_op.alter_column('oauth_id',
               existing_type=sa.VARCHAR(length=256),
               type_=sa.String(length=255),
               existing_nullable=True)
        batch_op.alter_column('avatar_url',
               existing_type=sa.VARCHAR(length=256),
               type_=sa.String(length=255),
               existing_nullable=True)
        batch_op.drop_index(batch_op.f('ix_user_username'))
        batch_op.create_index(batch_op.f('ix_user_email_verification_token'), ['email_verification_token'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_oauth_id'), ['oauth_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_stripe_customer_id'), ['stripe_customer_id'], unique=True)
        batch_op.drop_constraint(batch_op.f('fk_user_patient_id_patient'), type_='foreignkey')
        batch_op.drop_column('patient_id')

    with op.batch_alter_table('user_subscriptions', schema=None) as batch_op:
        batch_op.alter_column('id',
               existing_type=sa.INTEGER(),
               nullable=False,
               autoincrement=True)
        batch_op.alter_column('plan_id',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.Integer(),
               nullable=False)
        batch_op.alter_column('stripe_subscription_id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=255),
               existing_nullable=True)
        batch_op.alter_column('status',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=50),
               nullable=False)
        batch_op.alter_column('cancel_at_period_end',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('0'))
        batch_op.alter_column('created_at',
               existing_type=sa.DATETIME(),
               nullable=False)
        batch_op.alter_column('updated_at',
               existing_type=sa.DATETIME(),
               nullable=False)
        batch_op.create_index(batch_op.f('ix_user_subscriptions_stripe_subscription_id'), ['stripe_subscription_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_user_subscriptions_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key(None, 'plans', ['plan_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_subscriptions', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_user_subscriptions_user_id'))
        batch_op.drop_index(batch_op.f('ix_user_subscriptions_stripe_subscription_id'))
        batch_op.alter_column('updated_at',
               existing_type=sa.DATETIME(),
               nullable=True)
        batch_op.alter_column('created_at',
               existing_type=sa.DATETIME(),
               nullable=True)
        batch_op.alter_column('cancel_at_period_end',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('0'))
        batch_op.alter_column('status',
               existing_type=sa.String(length=50),
               type_=sa.VARCHAR(length=20),
               nullable=True)
        batch_op.alter_column('stripe_subscription_id',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=100),
               existing_nullable=True)
        batch_op.alter_column('plan_id',
               existing_type=sa.Integer(),
               type_=sa.VARCHAR(length=50),
               nullable=True)
        batch_op.alter_column('id',
               existing_type=sa.INTEGER(),
               nullable=True,
               autoincrement=True)

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('patient_id', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_user_patient_id_patient'), 'patient', ['patient_id'], ['id'])
        batch_op.drop_index(batch_op.f('ix_user_stripe_customer_id'))
        batch_op.drop_index(batch_op.f('ix_user_oauth_id'))
        batch_op.drop_index(batch_op.f('ix_user_email_verification_token'))
        batch_op.create_index(batch_op.f('ix_user_username'), ['username'], unique=1)
        batch_op.alter_column('avatar_url',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=256),
               existing_nullable=True)
        batch_op.alter_column('oauth_id',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=256),
               existing_nullable=True)
        batch_op.alter_column('oauth_provider',
               existing_type=sa.String(length=50),
               type_=sa.VARCHAR(length=20),
               existing_nullable=True)
        batch_op.alter_column('language',
               existing_type=sa.String(length=5),
               type_=sa.VARCHAR(length=10),
               existing_nullable=True,
               existing_server_default=sa.text('("en")'))
        batch_op.alter_column('role',
               existing_type=sa.VARCHAR(length=20),
               nullable=False,
               existing_server_default=sa.text("'physio'"))
        batch_op.alter_column('calendly_user_uri',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=256),
               existing_nullable=True)
        batch_op.alter_column('calendly_api_key',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=256),
               existing_nullable=True)
        batch_op.alter_column('stripe_customer_id',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=256),
               existing_nullable=True)
        batch_op.alter_column('tax_brackets',
               existing_type=sa.JSON(),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('clinic_percentage_agreement',
               existing_type=sa.Boolean(),
               type_=sa.FLOAT(),
               existing_nullable=True)
        batch_op.alter_column('clinic_website',
               existing_type=sa.String(length=120),
               type_=sa.VARCHAR(length=256),
               existing_nullable=True)
        batch_op.alter_column('clinic_phone',
               existing_type=sa.String(length=30),
               type_=sa.VARCHAR(length=20),
               existing_nullable=True)
        batch_op.alter_column('clinic_address',
               existing_type=sa.String(length=200),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('clinic_name',
               existing_type=sa.String(length=150),
               type_=sa.VARCHAR(length=128),
               existing_nullable=True)
        batch_op.alter_column('sex',
               existing_type=sa.String(length=16),
               type_=sa.VARCHAR(length=10),
               existing_nullable=True)
        batch_op.alter_column('email_verification_token',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=256),
               existing_nullable=True)
        batch_op.alter_column('email_verified',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('1'))
        batch_op.alter_column('password_hash',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=256),
               existing_nullable=True)

    with op.batch_alter_table('unmatched_calendly_booking', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')

    with op.batch_alter_table('treatment', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_treatment_calendly_invitee_uri'))
        batch_op.create_index(batch_op.f('ix_treatment_calendly_invitee_uri'), ['calendly_invitee_uri'], unique=1)
        batch_op.alter_column('movement_restriction',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=50),
               existing_nullable=True)

    with op.batch_alter_table('security_log', schema=None) as batch_op:
        batch_op.alter_column('user_agent',
               existing_type=sa.String(length=200),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('event_type',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
        batch_op.alter_column('id',
               existing_type=sa.INTEGER(),
               nullable=True,
               autoincrement=True)

    with op.batch_alter_table('recurring_appointment', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')

    with op.batch_alter_table('practice_reports', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')

    with op.batch_alter_table('patient', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint('fk_portal_user_id_user', type_='foreignkey')
        batch_op.drop_constraint(None, type_='unique')
        batch_op.alter_column('phone',
               existing_type=sa.String(length=500),
               type_=sa.VARCHAR(length=20),
               existing_nullable=True)
        batch_op.alter_column('email',
               existing_type=sa.String(length=500),
               type_=sa.VARCHAR(length=100),
               existing_nullable=True)
        batch_op.alter_column('name',
               existing_type=sa.String(length=500),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=True)

    with op.batch_alter_table('clinic_memberships', schema=None) as batch_op:
        batch_op.drop_index('idx_user_clinic_active', postgresql_where=sa.text('user_id IS NOT NULL'))

    op.create_table('_alembic_tmp_patient',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('name', sa.VARCHAR(length=500), nullable=False),
    sa.Column('date_of_birth', sa.DATE(), nullable=True),
    sa.Column('contact', sa.VARCHAR(length=100), nullable=True),
    sa.Column('diagnosis', sa.VARCHAR(length=200), nullable=True),
    sa.Column('treatment_plan', sa.TEXT(), nullable=True),
    sa.Column('notes', sa.TEXT(), nullable=True),
    sa.Column('status', sa.VARCHAR(length=20), nullable=True),
    sa.Column('created_at', sa.DATETIME(), nullable=True),
    sa.Column('email', sa.VARCHAR(length=500), nullable=True),
    sa.Column('phone', sa.VARCHAR(length=500), nullable=True),
    sa.Column('address_line1', sa.VARCHAR(length=100), nullable=True),
    sa.Column('address_line2', sa.VARCHAR(length=100), nullable=True),
    sa.Column('city', sa.VARCHAR(length=50), nullable=True),
    sa.Column('postcode', sa.VARCHAR(length=20), nullable=True),
    sa.Column('preferred_location', sa.VARCHAR(length=50), nullable=True),
    sa.Column('updated_at', sa.DATETIME(), nullable=True),
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.Column('portal_user_id', sa.INTEGER(), nullable=True),
    sa.Column('anamnesis', sa.TEXT(), nullable=True),
    sa.Column('ai_suggested_tests', sa.TEXT(), nullable=True),
    sa.Column('ai_red_flags', sa.TEXT(), nullable=True),
    sa.Column('ai_yellow_flags', sa.TEXT(), nullable=True),
    sa.Column('ai_clinical_notes', sa.TEXT(), nullable=True),
    sa.Column('ai_analysis_date', sa.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['portal_user_id'], ['user.id'], name=op.f('fk_portal_user_id_user')),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_patient_user_id')),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('portal_user_id', name=op.f('uq_patient_portal_user_id'))
    )
    # ### end Alembic commands ###
