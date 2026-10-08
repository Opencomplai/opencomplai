"""Add control_instances.waiver_source (SU-106).

Records where a WAIVED control came from ("exclusion" or "manual") so an
exclusion-derived waiver can be lifted when the manifest exclusion is removed.
Purely additive and nullable: stored rows keep NULL, which is treated as a
manual waiver. No RLS or privilege change (the table already has both from 0007).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("control_instances") as batch_op:
        batch_op.add_column(sa.Column("waiver_source", sa.String, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("control_instances") as batch_op:
        batch_op.drop_column("waiver_source")
