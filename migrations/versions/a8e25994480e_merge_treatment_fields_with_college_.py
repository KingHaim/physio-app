"""merge treatment fields with college acronym

Revision ID: a8e25994480e
Revises: add_college_acronym, add_treatment_clinical_fields
Create Date: 2025-06-30 15:39:47.643651

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a8e25994480e'
down_revision = ('add_college_acronym', 'add_treatment_clinical_fields')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
