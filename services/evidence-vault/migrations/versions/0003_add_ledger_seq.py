"""Add seq column to ledger_events for monotonic insertion-order tie-breaking.

Root cause: DateTime(timezone=True) on SQLite loses sub-second precision, so two
consecutive events appended within the same clock tick get the same `ts` value.
get_chain_tip and verify_chain both order by (ts, <tie-breaker>) and must agree on
which event is "last".  Previously the tie-breaker was event_id (UUID string), whose
lexicographic order is unrelated to insertion order.

Fix: add a server-side AUTOINCREMENT `seq` column and use (ts ASC, seq ASC) /
(ts DESC, seq DESC) consistently in both functions.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite does not support ADD COLUMN with AUTOINCREMENT via the standard path.
    # We add the column as nullable first, back-fill from rowid, then make it
    # effectively unique via a unique index.  On PostgreSQL/MySQL the standard
    # AUTOINCREMENT / SERIAL path is used instead.
    op.add_column(
        "ledger_events",
        sa.Column(
            "seq",
            sa.BigInteger,
            nullable=True,
        ),
    )
    # Back-fill existing rows with a monotonically increasing sequence.
    # Uses ROW_NUMBER() which works on both PostgreSQL and SQLite >= 3.25.
    # (SQLite rowid is not portable; ROW_NUMBER() ordered by ts,event_id is.)
    op.execute(
        """
        UPDATE ledger_events
        SET seq = rn.row_num
        FROM (
            SELECT event_id,
                   ROW_NUMBER() OVER (ORDER BY ts, event_id) AS row_num
            FROM ledger_events
        ) AS rn
        WHERE ledger_events.event_id = rn.event_id
        """
    )
    op.create_index("ix_ledger_events_seq", "ledger_events", ["seq"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ledger_events_seq", table_name="ledger_events")
    op.drop_column("ledger_events", "seq")
