"""Fix patient name field length for encrypted data

Revision ID: fix_patient_name_length
Revises: 03fc6caf29de
Create Date: 2025-06-22 18:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_patient_name_length'
down_revision = '03fc6caf29de'
branch_labels = None
depends_on = None


def upgrade():
    """Increase the length of patient name field to accommodate encrypted data."""
    # Increase name field from VARCHAR(100) to VARCHAR(500) to accommodate encrypted data
    op.alter_column('patient', 'name',
                    existing_type=sa.String(length=100),
                    type_=sa.String(length=500),
                    existing_nullable=False)
    
    # Also increase email field length for consistency
    op.alter_column('patient', 'email',
                    existing_type=sa.String(length=100),
                    type_=sa.String(length=500),
                    existing_nullable=True)


def downgrade():
    """Revert the field length changes."""
    # Revert name field back to VARCHAR(100)
    op.alter_column('patient', 'name',
                    existing_type=sa.String(length=500),
                    type_=sa.String(length=100),
                    existing_nullable=False)
    
    # Revert email field back to VARCHAR(100)
    op.alter_column('patient', 'email',
                    existing_type=sa.String(length=500),
                    type_=sa.String(length=100),
                    existing_nullable=True) 