"""Initial schema - all tables

Revision ID: 001_initial
Revises:
Create Date: 2026-04-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Companies
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("api_key", sa.String(255), unique=True, nullable=False),
        sa.Column("plan", sa.String(50), server_default="free"),
        sa.Column("settings", postgresql.JSON(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), server_default="admin"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Scripts
    op.create_table(
        "scripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("content", postgresql.JSON(), nullable=False),
        sa.Column("audio_status", sa.String(50), server_default="pending"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Script Audio Files
    op.create_table(
        "script_audio_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("script_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scripts.id"), nullable=False),
        sa.Column("node_key", sa.String(100), nullable=False),
        sa.Column("language_code", sa.String(10), nullable=False),
        sa.Column("voice_id", sa.String(50), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("audio_url", sa.String(500), nullable=False),
        sa.Column("audio_duration_ms", sa.Integer(), server_default="0"),
        sa.Column("file_size_bytes", sa.Integer(), server_default="0"),
        sa.Column("generation_cost_credits", sa.Float(), server_default="0.0"),
        sa.Column("status", sa.String(50), server_default="generating"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("script_id", "node_key", "language_code", name="uq_script_node_language"),
    )

    # Campaigns
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("script_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scripts.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("direction", sa.String(20), server_default="outbound"),
        sa.Column("schedule", postgresql.JSON(), nullable=True),
        sa.Column("settings", postgresql.JSON(), server_default='{"max_retries": 3, "retry_interval_minutes": 30, "concurrent_limit": 10}'),
        sa.Column("phone_list_url", sa.String(500), nullable=True),
        sa.Column("total_numbers", sa.Integer(), server_default="0"),
        sa.Column("called_count", sa.Integer(), server_default="0"),
        sa.Column("success_count", sa.Integer(), server_default="0"),
        sa.Column("failed_count", sa.Integer(), server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Call Logs
    op.create_table(
        "call_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("exotel_call_sid", sa.String(100), nullable=True, index=True),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(20), server_default="outbound"),
        sa.Column("status", sa.String(50), server_default="queued"),
        sa.Column("language_detected", sa.String(10), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), server_default="0"),
        sa.Column("recording_url", sa.String(500), nullable=True),
        sa.Column("transcript", postgresql.JSON(), server_default="[]"),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("outcome_tags", postgresql.JSON(), server_default="[]"),
        sa.Column("cost_breakdown", postgresql.JSON(), server_default="{}"),
        sa.Column("metadata", postgresql.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Phone Numbers
    op.create_table(
        "phone_numbers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("customer_data", postgresql.JSON(), server_default="{}"),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), server_default="0"),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Analytics Daily
    op.create_table(
        "analytics_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("total_calls", sa.Integer(), server_default="0"),
        sa.Column("successful_calls", sa.Integer(), server_default="0"),
        sa.Column("failed_calls", sa.Integer(), server_default="0"),
        sa.Column("avg_duration_seconds", sa.Float(), server_default="0.0"),
        sa.Column("total_cost", sa.Float(), server_default="0.0"),
        sa.Column("language_breakdown", postgresql.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "campaign_id", "date", name="uq_company_campaign_date"),
    )


def downgrade() -> None:
    op.drop_table("analytics_daily")
    op.drop_table("phone_numbers")
    op.drop_table("call_logs")
    op.drop_table("campaigns")
    op.drop_table("script_audio_files")
    op.drop_table("scripts")
    op.drop_table("users")
    op.drop_table("companies")
