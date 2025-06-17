"""add clinic pricing fields

Revision ID: 6c7b2db85f00
Revises: 842f604a3735
Create Date: 2025-06-16 22:48:00.923823

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6c7b2db85f00'
down_revision = '842f604a3735'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('clinic_first_session_fee', sa.Float(), nullable=True))
    op.add_column('user', sa.Column('clinic_subsequent_session_fee', sa.Float(), nullable=True))
    op.add_column('user', sa.Column('clinic_percentage_agreement', sa.Boolean(), nullable=True))
    op.add_column('user', sa.Column('clinic_percentage_amount', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('user', 'clinic_percentage_amount')
    op.drop_column('user', 'clinic_percentage_agreement')
    op.drop_column('user', 'clinic_subsequent_session_fee')
    op.drop_column('user', 'clinic_first_session_fee')
