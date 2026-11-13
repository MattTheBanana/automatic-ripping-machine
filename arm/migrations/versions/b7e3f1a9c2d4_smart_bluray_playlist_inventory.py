"""Persist MakeMKV Blu-ray playlist and segment metadata."""
from alembic import op
import sqlalchemy as sa


revision = "b7e3f1a9c2d4"
down_revision = "a2b6c1d8e4f0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("track", schema=None) as batch_op:
        batch_op.add_column(sa.Column("playlist", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("segment_map", sa.Text(), nullable=True))
    op.add_column("job", sa.Column("makemkv_disc_title", sa.String(length=256), nullable=True))


def downgrade():
    op.drop_column("job", "makemkv_disc_title")
    with op.batch_alter_table("track", schema=None) as batch_op:
        batch_op.drop_column("segment_map")
        batch_op.drop_column("playlist")
