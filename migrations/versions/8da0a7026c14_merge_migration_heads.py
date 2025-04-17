"""Merge migration heads

Revision ID: 8da0a7026c14
Revises: 14befc8bd3a5, 819cc60fee52
Create Date: 2025-04-17 11:24:44.224848

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8da0a7026c14'
down_revision = ('14befc8bd3a5', '819cc60fee52')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
