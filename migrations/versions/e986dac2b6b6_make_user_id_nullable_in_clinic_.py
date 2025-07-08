"""Make user_id nullable in clinic_memberships for invitations

Revision ID: e986dac2b6b6
Revises: 1c087d82525e
Create Date: 2025-07-06 14:22:26.334042

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e986dac2b6b6'
down_revision = 'add_college_acronym'
branch_labels = None
depends_on = None


def upgrade():
    # Make user_id nullable in clinic_memberships table to allow invitations
    # for users who don't exist yet
    with op.batch_alter_table('clinic_memberships', schema=None) as batch_op:
        # Make user_id nullable
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        
        # Drop the old unique constraint if it exists
        try:
            batch_op.drop_constraint('unique_user_clinic_membership', type_='unique')
        except:
            # Constraint might not exist or have different name, continue
            pass


def downgrade():
    # Revert changes - make user_id non-nullable and add back unique constraint
    with op.batch_alter_table('clinic_memberships', schema=None) as batch_op:
        # Remove any records with NULL user_id first (cleanup orphaned invitations)
        op.execute("DELETE FROM clinic_memberships WHERE user_id IS NULL")
        
        # Make user_id non-nullable again
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        
        # Add back the unique constraint
        batch_op.create_unique_constraint('unique_user_clinic_membership', ['user_id', 'clinic_id'])
