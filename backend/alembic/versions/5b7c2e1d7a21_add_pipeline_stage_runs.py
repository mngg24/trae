from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "5b7c2e1d7a21"
down_revision: str | None = "3e0a4a9f6d3c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipeline_stage_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pipeline_run_id", sa.String(length=36), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pipeline_run_id", "stage", name="uq_pipeline_stage_runs_run_stage"),
    )
    op.create_index(
        "ix_pipeline_stage_runs_pipeline_run_id",
        "pipeline_stage_runs",
        ["pipeline_run_id"],
        unique=False,
    )
    op.create_index("ix_pipeline_stage_runs_stage", "pipeline_stage_runs", ["stage"], unique=False)
    op.create_index("ix_pipeline_stage_runs_status", "pipeline_stage_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pipeline_stage_runs_status", table_name="pipeline_stage_runs")
    op.drop_index("ix_pipeline_stage_runs_stage", table_name="pipeline_stage_runs")
    op.drop_index("ix_pipeline_stage_runs_pipeline_run_id", table_name="pipeline_stage_runs")
    op.drop_table("pipeline_stage_runs")

