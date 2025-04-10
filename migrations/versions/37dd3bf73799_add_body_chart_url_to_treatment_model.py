"""Add body_chart_url to Treatment model

Revision ID: 37dd3bf73799
Revises: 
Create Date: 2025-04-11 01:02:43.348283

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '37dd3bf73799'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('treatment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('treatment_type', sa.String(length=100), nullable=False))
        batch_op.add_column(sa.Column('assessment', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('provider', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('body_chart_url', sa.String(length=255), nullable=True))
        batch_op.alter_column('status',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=50),
               existing_nullable=True)
        batch_op.drop_column('next_appointment')
        batch_op.drop_column('progress_notes')
        batch_op.drop_column('description')
        batch_op.drop_column('date')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('treatment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('date', sa.DATETIME(), nullable=False))
        batch_op.add_column(sa.Column('description', sa.TEXT(), nullable=False))
        batch_op.add_column(sa.Column('progress_notes', sa.TEXT(), nullable=True))
        batch_op.add_column(sa.Column('next_appointment', sa.DATETIME(), nullable=True))
        batch_op.alter_column('status',
               existing_type=sa.String(length=50),
               type_=sa.VARCHAR(length=20),
               existing_nullable=True)
        batch_op.drop_column('body_chart_url')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('provider')
        batch_op.drop_column('notes')
        batch_op.drop_column('assessment')
        batch_op.drop_column('treatment_type')

    # ### end Alembic commands ###
