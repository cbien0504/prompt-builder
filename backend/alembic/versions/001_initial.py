"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-15 11:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create folders table
    op.create_table(
        'folders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('path', sa.String(length=1024), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('total_files', sa.Integer(), server_default='0'),
        sa.Column('indexed_files', sa.Integer(), server_default='0'),
        sa.Column('total_chunks', sa.Integer(), server_default='0'),
        sa.Column('last_indexed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('error_message', sa.Text()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('path')
    )
    op.create_index('idx_folders_status', 'folders', ['status'])
    op.create_index('idx_folders_path', 'folders', ['path'])

    # Create index_stats table
    op.create_table(
        'index_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('folder_id', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=1024), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('chunks_count', sa.Integer(), nullable=False),
        sa.Column('indexed_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['folder_id'], ['folders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_index_stats_folder_id', 'index_stats', ['folder_id'])
    op.create_index('idx_index_stats_file_hash', 'index_stats', ['file_hash'])


def downgrade() -> None:
    op.drop_index('idx_index_stats_file_hash', table_name='index_stats')
    op.drop_index('idx_index_stats_folder_id', table_name='index_stats')
    op.drop_table('index_stats')
    
    op.drop_index('idx_folders_path', table_name='folders')
    op.drop_index('idx_folders_status', table_name='folders')
    op.drop_table('folders')
