"""Add repo_count to folders

Revision ID: 002_add_repo_count
Revises: 001_initial
Create Date: 2026-01-15 14:22:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_repo_count'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add repo_count column to folders table
    op.add_column('folders', sa.Column('repo_count', sa.Integer(), server_default='0', nullable=True))


def downgrade() -> None:
    # Remove repo_count column
    op.drop_column('folders', 'repo_count')
