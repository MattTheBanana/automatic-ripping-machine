"""Merge existing migration heads and add disc UI preferences."""

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = "7db1c8e4a2f9"
down_revision = ("50d63e3650d2", "5e0a6dc97f31")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "job",
        sa.Column("special_features", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "job",
        sa.Column("special_features_auto", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "ui_settings",
        sa.Column("show_job_ripper", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "ui_settings",
        sa.Column("show_job_rip_method", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "ui_settings",
        sa.Column("show_job_main_feature", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "ui_settings",
        sa.Column("show_job_min_length", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "ui_settings",
        sa.Column("show_job_max_length", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "ui_settings",
        sa.Column(
            "device_display_mode",
            sa.String(length=16),
            nullable=False,
            server_default="coded",
        ),
    )


def downgrade():
    op.drop_column("ui_settings", "device_display_mode")
    op.drop_column("ui_settings", "show_job_max_length")
    op.drop_column("ui_settings", "show_job_min_length")
    op.drop_column("ui_settings", "show_job_main_feature")
    op.drop_column("ui_settings", "show_job_rip_method")
    op.drop_column("ui_settings", "show_job_ripper")
    op.drop_column("job", "special_features_auto")
    op.drop_column("job", "special_features")
