"""Make haim user admin

Revision ID: e805e9722b4f
Revises: ade9873039e7
Create Date: 2025-06-09 19:07:04.880441

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e805e9722b4f'
down_revision = 'ade9873039e7'
branch_labels = None
depends_on = None


def upgrade():
    # Update haim user to be admin
    op.execute("""
        UPDATE user 
        SET is_admin = true, role = 'admin' 
        WHERE username = 'haim'
    """)


def downgrade():
    # Rollback haim user admin status
    op.execute("""
        UPDATE user 
        SET is_admin = false, role = 'physio' 
        WHERE username = 'haim'
    """)
