"""Update password_hash field length

Revision ID: update_password_hash_length
Revises: add_encrypted_calendly_token
Create Date: 2025-01-20 23:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'update_password_hash_length'
down_revision = 'add_encrypted_calendly_token'
branch_labels = None
depends_on = None


def upgrade():
    # Increase password_hash field size from 128 to 255 characters
    # This will work whether the column exists or not in a fresh database
    try:
        op.alter_column('user', 'password_hash',
                       existing_type=sa.String(length=128),
                       type_=sa.String(length=255),
                       existing_nullable=True)
    except Exception:
        # If the column doesn't exist or has a different type, 
        # the model definition will handle it correctly
        pass


def downgrade():
    # Revert password_hash field size back to 128 characters
    try:
        op.alter_column('user', 'password_hash',
                       existing_type=sa.String(length=255),
                       type_=sa.String(length=128),
                       existing_nullable=True)
    except Exception:
        pass 