"""Add active-card date/time display preferences and opt-in smart title matching."""

from alembic import op
import sqlalchemy as sa

revision = "a2b6c1d8e4f0"
down_revision = "8c1d4f2a9b70"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ui_settings",
        sa.Column("start_date_format", sa.String(length=16), nullable=False, server_default="MM/DD/YYYY"),
    )
    op.add_column(
        "ui_settings",
        sa.Column("start_time_format", sa.String(length=8), nullable=False, server_default="12h"),
    )
    op.add_column(
        "ui_settings",
        sa.Column("smart_title_matching_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "ui_settings",
        sa.Column("smart_title_matching_url", sa.String(length=512), nullable=False,
                  server_default="http://ollama:11434"),
    )
    op.add_column(
        "ui_settings",
        sa.Column("smart_title_matching_model", sa.String(length=128), nullable=False,
                  server_default="qwen2.5:3b"),
    )


def downgrade():
    op.drop_column("ui_settings", "smart_title_matching_model")
    op.drop_column("ui_settings", "smart_title_matching_url")
    op.drop_column("ui_settings", "smart_title_matching_enabled")
    op.drop_column("ui_settings", "start_time_format")
    op.drop_column("ui_settings", "start_date_format")
