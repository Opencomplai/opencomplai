"""Add dossier_index table for server-side dossier retrieval.

Closes Gap #2 from the self-audit: the doc-generator previously dropped the
generated dossier on the floor. The vault now stores the dossier JSON in CAS
and maps `dossier_id`/`system_id` to the content hash and the ledger event
that anchors its existence.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dossier_index",
        sa.Column("dossier_id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(256), nullable=False),
        sa.Column("commit_ref", sa.String(256), nullable=False),
        sa.Column("content_hash", sa.String(71), nullable=False),
        sa.Column("bundle_checksum", sa.String(71), nullable=False),
        sa.Column("ledger_event_id", sa.String(36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_dossier_index_system_id", "dossier_index", ["system_id"])


def downgrade() -> None:
    op.drop_index("ix_dossier_index_system_id", table_name="dossier_index")
    op.drop_table("dossier_index")
