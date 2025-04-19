"""Add PracticeReport model

Revision ID: 368cf09a3a7f
Revises: 02aa07e3be67
Create Date: 2025-04-19 01:05:40.945389

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '368cf09a3a7f'
down_revision = '02aa07e3be67'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('practice_reports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('generated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_table('_alembic_tmp_treatment')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('_alembic_tmp_treatment',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('patient_id', sa.INTEGER(), nullable=True),
    sa.Column('treatment_type', sa.VARCHAR(length=100), nullable=False),
    sa.Column('assessment', sa.TEXT(), nullable=True),
    sa.Column('notes', sa.TEXT(), nullable=True),
    sa.Column('status', sa.VARCHAR(length=50), nullable=True),
    sa.Column('provider', sa.VARCHAR(length=100), nullable=True),
    sa.Column('created_at', sa.DATETIME(), nullable=True),
    sa.Column('updated_at', sa.DATETIME(), nullable=True),
    sa.Column('body_chart_url', sa.VARCHAR(length=255), nullable=True),
    sa.Column('pain_level', sa.INTEGER(), nullable=True),
    sa.Column('movement_restriction', sa.VARCHAR(length=50), nullable=True),
    sa.Column('evaluation_data', sqlite.JSON(), nullable=True),
    sa.Column('location', sa.VARCHAR(length=100), nullable=True),
    sa.Column('visit_type', sa.VARCHAR(length=50), nullable=True),
    sa.Column('fee_charged', sa.FLOAT(), nullable=True),
    sa.Column('payment_method', sa.VARCHAR(length=50), nullable=True),
    sa.Column('email', sa.VARCHAR(length=120), nullable=False),
    sa.Column('password_hash', sa.VARCHAR(length=256), nullable=True),
    sa.Column('is_admin', sa.BOOLEAN(), nullable=True),
    sa.Column('role', sa.VARCHAR(length=20), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_table('practice_reports')
    # ### end Alembic commands ###
