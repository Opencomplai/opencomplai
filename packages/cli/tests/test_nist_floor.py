"""The NIST AI RMF row statuses did not move when the pack became hybrid.

`fixtures/nist_floor_statuses.json` holds every row's status before that change.
The regenerated NIST gaps golden must give the same status for each row, in the
`nist_rmf_report` block and in the pack's own report.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
FLOOR = json.loads(
    (HERE / "fixtures" / "nist_floor_statuses.json").read_text(encoding="utf-8")
)
PAYLOAD = json.loads(
    (HERE / "golden" / "gaps_credit_nist.json").read_text(encoding="utf-8")
)["payload"]


def test_floor_has_every_row() -> None:
    assert len(FLOOR) == 72


def test_nist_rmf_report_statuses_equal_the_floor() -> None:
    rows = PAYLOAD["nist_rmf_report"]["subcategories"]
    got = {f"NIST_AI_RMF:{row['subcategory']}": row["status"] for row in rows}
    assert got == FLOOR


def test_pack_report_statuses_equal_the_floor() -> None:
    rows = PAYLOAD["frameworks"]["NIST_AI_RMF"]["report"]["articles"]
    got = {row["article"]: row["status"] for row in rows}
    assert got == FLOOR
