"""Initial Evidence Vault schema.

Creates ledger_events and evidence_objects tables.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ledger_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("payload_hash", sa.String(71), nullable=False),
        sa.Column("prev_hash", sa.String(71), nullable=False),
        sa.Column("signer_id", sa.String(256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_ledger_events_ts", "ledger_events", ["ts"])
    op.create_index("ix_ledger_events_event_type", "ledger_events", ["event_type"])

    op.create_table(
        "evidence_objects",
        sa.Column("evidence_id", sa.String(36), primary_key=True),
        sa.Column("content_hash", sa.String(71), nullable=False, unique=True),
        sa.Column("storage_uri", sa.String(1024), nullable=False),
        sa.Column("encryption_profile", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_evidence_objects_content_hash", "evidence_objects", ["content_hash"]
    )


def downgrade() -> None:
    op.drop_table("evidence_objects")
    op.drop_table("ledger_events")
