"""add_google_calendar_integration_fields

Revision ID: 3ee95b6c9aa6
Revises: 80922477c9bf
Create Date: 2025-08-06 21:16:20.262140

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3ee95b6c9aa6'
down_revision = '80922477c9bf'
branch_labels = None
depends_on = None


def upgrade():
    # ### Create Google Calendar configuration table ###
    op.create_table('google_calendar_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Text(), nullable=True),
        sa.Column('client_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('redirect_uri', sa.String(length=500), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=True, default=False),
        sa.Column('configured_by_user_id', sa.Integer(), nullable=True),
        sa.Column('configured_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['configured_by_user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # ### Add Google Calendar fields to User table ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('google_calendar_token_encrypted', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('google_calendar_refresh_token_encrypted', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('google_calendar_enabled', sa.Boolean(), nullable=True, default=False))
        batch_op.add_column(sa.Column('google_calendar_primary_calendar_id', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('google_calendar_last_sync', sa.DateTime(), nullable=True))

    # ### Add Google Calendar fields to Treatment table ###
    with op.batch_alter_table('treatment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('google_calendar_event_id', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('google_calendar_event_summary', sa.String(length=255), nullable=True))
        
    # ### Create indexes for better performance ###
    try:
        op.create_index('idx_treatment_google_calendar_event_id', 'treatment', ['google_calendar_event_id'], unique=False)
    except:
        # Index might already exist, ignore error
        pass


def downgrade():
    # ### Drop indexes ###
    try:
        op.drop_index('idx_treatment_google_calendar_event_id', table_name='treatment')
    except:
        # Index might not exist, ignore error
        pass
        
    # ### Remove Google Calendar fields from Treatment table ###
    with op.batch_alter_table('treatment', schema=None) as batch_op:
        batch_op.drop_column('google_calendar_event_summary')
        batch_op.drop_column('google_calendar_event_id')

    # ### Remove Google Calendar fields from User table ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('google_calendar_last_sync')
        batch_op.drop_column('google_calendar_primary_calendar_id')
        batch_op.drop_column('google_calendar_enabled')
        batch_op.drop_column('google_calendar_refresh_token_encrypted')
        batch_op.drop_column('google_calendar_token_encrypted')
    
    # ### Drop Google Calendar configuration table ###
    op.drop_table('google_calendar_config')
