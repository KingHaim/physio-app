"""sync Alembic state after reverting models

Revision ID: 02aa07e3be67
Revises: eacf40bd2a7d
Create Date: 2025-04-18 13:51:03.082306

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '02aa07e3be67'
down_revision = 'eacf40bd2a7d'
branch_labels = None
depends_on = None


def upgrade():
    # ### Manual adjustments for 'user' table ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Ensure email is not nullable (if it wasn't already)
        batch_op.alter_column('email',
               existing_type=sa.VARCHAR(length=120),
               nullable=False)
        # Adjust password hash length (if changed)
        batch_op.alter_column('password_hash',
               existing_type=sa.VARCHAR(length=128), # Assuming original was 128
               type_=sa.String(length=256),
               existing_nullable=True) # Keep existing nullable status
        # Add new columns
        batch_op.add_column(sa.Column('role', sa.String(length=20), nullable=False, server_default='physio'))
        batch_op.add_column(sa.Column('patient_id', sa.Integer(), nullable=True))
        # Add foreign key constraint
        batch_op.create_foreign_key(
            batch_op.f('fk_user_patient_id_patient'), # Use batch_op.f for auto-naming
            'patient', ['patient_id'], ['id']
        )
    # ### End Manual adjustments ###

    # Remove incorrect operations generated for 'treatment' table
    # op.drop_table('_alembic_tmp_treatment') # Usually safe to remove this line if the table doesn't exist
    # with op.batch_alter_table('treatment', schema=None) as batch_op:
    #     batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=False)) <--- REMOVE
    #     batch_op.add_column(sa.Column('password_hash', sa.String(length=256), nullable=True)) <--- REMOVE
    #     batch_op.add_column(sa.Column('is_admin', sa.Boolean(), nullable=True)) <--- REMOVE
    #     batch_op.add_column(sa.Column('role', sa.String(length=20), nullable=False)) <--- REMOVE
    #     batch_op.alter_column('patient_id', existing_type=sa.INTEGER(), nullable=True) <--- REMOVE (if it was specific to treatment)
    #     batch_op.create_index(batch_op.f('ix_treatment_email'), ['email'], unique=True) <--- REMOVE

def downgrade():
    # ### Manual adjustments for 'user' table ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Drop foreign key first
        batch_op.drop_constraint(batch_op.f('fk_user_patient_id_patient'), type_='foreignkey')
        # Drop new columns
        batch_op.drop_column('patient_id')
        batch_op.drop_column('role')
        # Revert password hash length
        batch_op.alter_column('password_hash',
               existing_type=sa.String(length=256),
               type_=sa.VARCHAR(length=128), # Revert to original
               existing_nullable=True)
        # Revert email nullability (assuming it was nullable before)
        batch_op.alter_column('email',
               existing_type=sa.VARCHAR(length=120),
               nullable=True) # Make nullable again
    # ### End Manual adjustments ###

    # Remove incorrect operations generated for 'treatment' table
    # with op.batch_alter_table('treatment', schema=None) as batch_op:
    #     batch_op.drop_index(batch_op.f('ix_treatment_email')) <--- REMOVE
    #     batch_op.alter_column('patient_id', existing_type=sa.INTEGER(), nullable=False) <--- REMOVE (if specific)
    #     batch_op.drop_column('role') <--- REMOVE
    #     batch_op.drop_column('is_admin') <--- REMOVE
    #     batch_op.drop_column('password_hash') <--- REMOVE
    #     batch_op.drop_column('email') <--- REMOVE
    # op.create_table('_alembic_tmp_treatment', ...) <--- REMOVE
