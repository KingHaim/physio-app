"""Merge location management with main branch

Revision ID: 9bd157c79821
Revises: 7ac1f468c109, add_location_management
Create Date: 2025-06-23 15:03:53.135086

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9bd157c79821'
down_revision = ('7ac1f468c109', 'add_location_management')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
