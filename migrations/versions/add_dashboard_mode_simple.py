"""Add dashboard_mode column to user table - simplified

Revision ID: add_dashboard_mode_simple
Revises: add_dashboard_mode_column
Create Date: 2025-07-20 18:56:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_dashboard_mode_simple'
down_revision = 'add_dashboard_mode_column'
branch_labels = None
depends_on = None


def upgrade():
    # Add dashboard_mode column directly
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dashboard_mode', sa.String(length=20), nullable=False, server_default='individual'))


def downgrade():
    # Remove the column
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('dashboard_mode') 