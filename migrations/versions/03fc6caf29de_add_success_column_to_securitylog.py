"""Add success column to SecurityLog

Revision ID: 03fc6caf29de
Revises: update_password_hash_length
Create Date: 2025-06-20 11:21:08.493925

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '03fc6caf29de'
down_revision = 'update_password_hash_length'
branch_labels = None
depends_on = None


def upgrade():
    # No-op: 'success' column is already present from the initial schema
    pass


def downgrade():
    # No-op: nothing to remove
    pass
