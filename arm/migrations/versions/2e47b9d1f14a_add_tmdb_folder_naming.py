"""Store TMDB IDs and per-job output folder identifier preference.

Revision ID: 2e47b9d1f14a
Revises: edf2272c0a9d
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2e47b9d1f14a"
down_revision = "edf2272c0a9d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("job", sa.Column("tmdb_id", sa.String(length=20), nullable=True))
    op.add_column("config", sa.Column("FOLDER_ID_TYPE", sa.String(length=16), nullable=True))


def downgrade():
    op.drop_column("config", "FOLDER_ID_TYPE")
    op.drop_column("job", "tmdb_id")
