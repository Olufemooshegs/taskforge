"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-11

Hand-written to include CHECK constraints, partial indexes, and the
development seed (tenant + default queues) that autogenerate misses.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Stable seed IDs so `.env` TENANT_ID matches what the DB has.
DEV_TENANT_ID = "00000000-0000-0000-0000-000000000001"
DEV_QUEUE_DEFAULT_ID = "00000000-0000-0000-0000-000000000101"
DEV_QUEUE_EMAILS_ID = "00000000-0000-0000-0000-000000000102"


def upgrade() -> None:
    # ---- tenants ----
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('active','suspended')", name="ck_tenants_status"),
    )

    # ---- queues ----
    op.create_table(
        "queues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("max_concurrency", sa.Integer, nullable=False, server_default="10"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_queues_tenant_name"),
        sa.CheckConstraint("max_concurrency > 0", name="ck_queues_max_concurrency_pos"),
    )

    # ---- workers ----
    op.create_table(
        "workers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("pid", sa.Integer, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="starting"),
        sa.Column("supported_queues", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("concurrency", sa.Integer, nullable=False, server_default="1"),
        sa.Column("last_heartbeat_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('starting','active','draining','stopped')",
            name="ck_workers_status",
        ),
        sa.CheckConstraint("concurrency > 0", name="ck_workers_concurrency_pos"),
    )

    # ---- jobs ----
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("queue_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("queues.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("task_name", sa.String(150), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("priority", sa.SmallInteger, nullable=False, server_default="2"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="5"),
        sa.Column("scheduled_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("locked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lease_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lease_generation", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("payload_fingerprint", sa.String(64), nullable=True),
        sa.Column("retry_policy", postgresql.JSONB, nullable=True),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="300"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("priority BETWEEN 1 AND 3", name="ck_jobs_priority"),
        sa.CheckConstraint("attempts >= 0 AND max_attempts > 0", name="ck_jobs_attempts"),
        sa.CheckConstraint(
            "status IN ('scheduled','queued','running','retry_scheduled',"
            "'succeeded','failed','dead_lettered','cancelled')",
            name="ck_jobs_status",
        ),
    )

    # ---- job_attempts ----
    op.create_table(
        "job_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("workers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger, nullable=True),
        sa.Column("error_type", sa.String(150), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("error_traceback", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_job_attempts_job_number"),
        sa.CheckConstraint(
            "status IN ('running','succeeded','failed','worker_lost','timed_out','cancelled')",
            name="ck_attempts_status",
        ),
    )

    # ---- dead_letter_entries ----
    op.create_table(
        "dead_letter_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("final_error_type", sa.String(150), nullable=True),
        sa.Column("dead_lettered_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("replay_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ---- outbox_events ----
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("next_attempt_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("locked_by", sa.String(255), nullable=True),
        sa.Column("locked_until", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # ---- audit_logs ----
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("extra_data", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ---- indexes (spec 5.9 + idempotency partial unique) ----
    op.execute(
        "CREATE INDEX idx_jobs_claimable "
        "ON jobs (queue_id, priority DESC, scheduled_at ASC, created_at ASC) "
        "WHERE status = 'queued'"
    )
    op.execute(
        "CREATE INDEX idx_jobs_scheduled "
        "ON jobs (scheduled_at) "
        "WHERE status IN ('scheduled','retry_scheduled')"
    )
    op.execute(
        "CREATE INDEX idx_jobs_expired_leases "
        "ON jobs (locked_until) "
        "WHERE status = 'running'"
    )
    op.execute(
        "CREATE INDEX idx_jobs_tenant_created "
        "ON jobs (tenant_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_attempts_job "
        "ON job_attempts (job_id, attempt_number DESC)"
    )
    op.execute(
        "CREATE UNIQUE INDEX idx_jobs_idempotency "
        "ON jobs (tenant_id, idempotency_key) "
        "WHERE idempotency_key IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_dl_tenant_created "
        "ON dead_letter_entries (tenant_id, dead_lettered_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_outbox_pending "
        "ON outbox_events (next_attempt_at ASC) "
        "WHERE published_at IS NULL"
    )
    op.execute(
        "CREATE INDEX idx_audit_tenant_created "
        "ON audit_logs (tenant_id, created_at DESC)"
    )

    # ---- dev seed (spec 5: one tenant + default queues) ----
    op.execute(
        sa.text(
            "INSERT INTO tenants (id, name, status) "
            "VALUES (CAST(:id AS uuid), :name, 'active')"
        ).bindparams(id=DEV_TENANT_ID, name="Development Tenant")
    )
    op.execute(
        sa.text(
            "INSERT INTO queues (id, tenant_id, name, max_concurrency, is_active) VALUES "
            "(CAST(:id AS uuid), CAST(:tenant_id AS uuid), 'default', 10, true), "
            "(CAST(:id2 AS uuid), CAST(:tenant_id AS uuid), 'emails', 10, true)"
        ).bindparams(
            id=DEV_QUEUE_DEFAULT_ID,
            id2=DEV_QUEUE_EMAILS_ID,
            tenant_id=DEV_TENANT_ID,
        )
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("outbox_events")
    op.drop_table("dead_letter_entries")
    op.drop_table("job_attempts")
    op.drop_table("jobs")
    op.drop_table("workers")
    op.drop_table("queues")
    op.drop_table("tenants")
