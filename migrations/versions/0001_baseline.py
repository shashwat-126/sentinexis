"""baseline schema -- mirrors current Base.metadata.create_all() output

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-07

Creates every table the platform's services currently manage via
`Base.metadata.create_all()` at startup: Incidents + Incident Events +
Actions + Metric Snapshots + Audit Logs (incident-service), Notifications
(notification-service), and the two original tables (inference_results,
incident_logs). Running this against a fresh database gets you the exact
same schema `docker compose up` would create -- from here on, schema
changes should be new Alembic revisions instead of relying on create_all.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("incident_uid", sa.String(32), unique=True, index=True, nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False, index=True),
        sa.Column("service_name", sa.String(128), nullable=False, index=True),
        sa.Column("severity", sa.String(16), nullable=False, index=True),
        sa.Column("anomaly_score", sa.Float, nullable=True),
        sa.Column("metrics", postgresql.JSONB, nullable=True),
        sa.Column("root_cause", sa.String(64), nullable=True, index=True),
        sa.Column("recommended_action", sa.String(128), nullable=True),
        sa.Column("executed_action", sa.String(128), nullable=True),
        sa.Column("recovery_status", sa.String(16), nullable=False, index=True),
        sa.Column("resolved_time", sa.DateTime, nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "incident_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("incident_id", sa.Integer, sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "actions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("incident_id", sa.Integer, sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("target", sa.String(128), nullable=False),
        sa.Column("backend", sa.String(16), nullable=False),
        sa.Column("mode", sa.String(16), nullable=True),
        sa.Column("result", sa.String(32), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("service_name", sa.String(128), nullable=False, index=True),
        sa.Column("cpu_percent", sa.Float, nullable=True),
        sa.Column("memory_percent", sa.Float, nullable=True),
        sa.Column("disk_percent", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Float, nullable=True),
        sa.Column("error_rate_percent", sa.Float, nullable=True),
        sa.Column("http_requests_per_sec", sa.Float, nullable=True),
        sa.Column("queue_length", sa.Float, nullable=True),
        sa.Column("container_restarts", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, index=True),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("incident_id", sa.Integer, nullable=True, index=True),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, index=True),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("incident_id", sa.Integer, nullable=True, index=True),
        sa.Column("incident_uid", sa.String(32), nullable=True, index=True),
        sa.Column("service_name", sa.String(128), index=True),
        sa.Column("severity", sa.String(16)),
        sa.Column("status", sa.String(32)),
        sa.Column("channel", sa.String(16), index=True),
        sa.Column("sent", sa.Boolean, default=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("title", sa.String(256), nullable=True),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, index=True),
    )

    # Original tables, predating the AIOps expansion -- kept for backward
    # compatibility with result-service and aiops-engine's legacy audit log.
    op.create_table(
        "inference_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("req_id", sa.String, unique=True, index=True),
        sa.Column("status", sa.String),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime),
    )

    op.create_table(
        "incident_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("service_name", sa.String),
        sa.Column("anomaly_type", sa.String),
        sa.Column("action_taken", sa.String),
        sa.Column("created_at", sa.DateTime),
    )


def downgrade():
    op.drop_table("incident_logs")
    op.drop_table("inference_results")
    op.drop_table("notifications")
    op.drop_table("audit_logs")
    op.drop_table("metric_snapshots")
    op.drop_table("actions")
    op.drop_table("incident_events")
    op.drop_table("incidents")
