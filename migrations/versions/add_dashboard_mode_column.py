"""Add dashboard_mode column to user table

Revision ID: add_dashboard_mode_column
Revises: e98b6cca46a0
Create Date: 2025-07-20 18:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'add_dashboard_mode_column'
down_revision = 'e98b6cca46a0'
branch_labels = None
depends_on = None


def upgrade():
    # Check if column already exists before adding it
    connection = op.get_bind()
    
    # For SQLite, check if column exists
    if connection.dialect.name == 'sqlite':
        result = connection.execute(text("PRAGMA table_info(user)"))
        columns = [row[1] for row in result]
        if 'dashboard_mode' not in columns:
            with op.batch_alter_table('user', schema=None) as batch_op:
                batch_op.add_column(sa.Column('dashboard_mode', sa.String(length=20), nullable=False, server_default='individual'))
    
    # For PostgreSQL, check if column exists
    elif connection.dialect.name == 'postgresql':
        result = connection.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='user' AND column_name='dashboard_mode'
        """))
        if not result.fetchone():
            with op.batch_alter_table('user', schema=None) as batch_op:
                batch_op.add_column(sa.Column('dashboard_mode', sa.String(length=20), nullable=False, server_default='individual'))


def downgrade():
    # Remove the column
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('dashboard_mode') 