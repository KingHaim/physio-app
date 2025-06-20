"""Add encrypted Calendly API token field

Revision ID: add_encrypted_calendly_token
Revises: 001_initial_schema
Create Date: 2025-06-18 16:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_encrypted_calendly_token'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade():
    # Add the encrypted Calendly API token field
    op.add_column('user', sa.Column('calendly_api_token_encrypted', sa.Text(), nullable=True))


def downgrade():
    # Remove the encrypted Calendly API token field
    op.drop_column('user', 'calendly_api_token_encrypted') 