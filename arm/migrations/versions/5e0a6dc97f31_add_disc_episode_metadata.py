"""Add season, disc, and episode range to ripping jobs.

Revision ID: 5e0a6dc97f31
Revises: 2e47b9d1f14a
Create Date: 2026-10-23
"""
from alembic import op
import sqlalchemy as sa

revision = "5e0a6dc97f31"
down_revision = "2e47b9d1f14a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("job", sa.Column("season_number", sa.Integer(), nullable=True))
    op.add_column("job", sa.Column("disc_number", sa.Integer(), nullable=True))
    op.add_column("job", sa.Column("episode_start", sa.Integer(), nullable=True))
    op.add_column("job", sa.Column("episode_end", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("job", "episode_end")
    op.drop_column("job", "episode_start")
    op.drop_column("job", "disc_number")
    op.drop_column("job", "season_number")
