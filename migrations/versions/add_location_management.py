"""Add location management system

Revision ID: add_location_management
Revises: add_fiscal_fields_only
Create Date: 2025-06-23 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'add_location_management'
down_revision = 'add_fiscal_fields_only'
branch_labels = None
depends_on = None


def upgrade():
    # Create location table
    op.create_table('location',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('address', sa.String(length=200), nullable=True),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('first_session_fee', sa.Float(), nullable=True),
        sa.Column('subsequent_session_fee', sa.Float(), nullable=True),
        sa.Column('fee_percentage', sa.Float(), nullable=True),
        sa.Column('location_type', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add location_id to treatment table
    with op.batch_alter_table('treatment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_treatment_location', 'location', ['location_id'], ['id'])
    
    # Add location_id to recurring_appointment table
    with op.batch_alter_table('recurring_appointment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_recurring_appointment_location', 'location', ['location_id'], ['id'])


def downgrade():
    # Remove foreign keys and columns
    with op.batch_alter_table('recurring_appointment', schema=None) as batch_op:
        batch_op.drop_constraint('fk_recurring_appointment_location', type_='foreignkey')
        batch_op.drop_column('location_id')
    
    with op.batch_alter_table('treatment', schema=None) as batch_op:
        batch_op.drop_constraint('fk_treatment_location', type_='foreignkey')
        batch_op.drop_column('location_id')
    
    # Drop location table
    op.drop_table('location') 