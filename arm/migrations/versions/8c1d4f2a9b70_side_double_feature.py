"""Add side selection and second feature metadata to ripping jobs.

Revision ID: 8c1d4f2a9b70
Revises: 7db1c8e4a2f9
Create Date: 2026-10-27
"""
from alembic import op
import sqlalchemy as sa

revision = "8c1d4f2a9b70"
down_revision = "7db1c8e4a2f9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("job", sa.Column("disc_side", sa.String(length=1), nullable=True))
    op.add_column("job", sa.Column("plot", sa.Text(), nullable=True))
    op.add_column("job", sa.Column("secondary_title", sa.String(length=256), nullable=True))
    op.add_column("job", sa.Column("secondary_year", sa.String(length=4), nullable=True))
    op.add_column("job", sa.Column("secondary_video_type", sa.String(length=20), nullable=True))
    op.add_column("job", sa.Column("secondary_imdb_id", sa.String(length=15), nullable=True))
    op.add_column("job", sa.Column("secondary_tmdb_id", sa.String(length=20), nullable=True))
    op.add_column("job", sa.Column("secondary_poster_url", sa.String(length=512), nullable=True))
    op.add_column("job", sa.Column("secondary_plot", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("job", "secondary_plot")
    op.drop_column("job", "secondary_poster_url")
    op.drop_column("job", "secondary_tmdb_id")
    op.drop_column("job", "secondary_imdb_id")
    op.drop_column("job", "secondary_video_type")
    op.drop_column("job", "secondary_year")
    op.drop_column("job", "secondary_title")
    op.drop_column("job", "plot")
    op.drop_column("job", "disc_side")
