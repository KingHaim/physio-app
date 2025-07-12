"""Merge migration heads

Revision ID: ef95bfd223e1
Revises: 1c087d82525e, e986dac2b6b6
Create Date: 2025-07-12 20:22:00.091576

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ef95bfd223e1'
down_revision = ('1c087d82525e', 'e986dac2b6b6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
