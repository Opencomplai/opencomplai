"""Shared golden-vector parity test (DASHBOARD-GA DG-13).

``dashboard-saas/schemas/checker_golden_vectors.json`` is asserted from
BOTH this root suite (running the OSS engine directly) and the dashboard
suite (``dashboard-saas/packages/dashboard_checker/tests/
test_golden_vectors_shared.py``, running the vendored engine) — the same
fixture, two engines, one expected result per vector. This is the
cross-tree half of the drift contract:
``dashboard-saas/scripts/checker_drift_check.py`` guards the *source*
(vendored files must not diverge from the OSS files); this test (mirrored
on the dashboard side) guards the *behavior* (both engines must actually
agree on every vector, not just look byte-identical).

The fixture path is resolved relative to this repo's root rather than
copied locally — there is exactly one shared file, not two independent
copies that could drift from each other.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.compliance_checker.engine import evaluate
from opencomplai_core.compliance_checker.models import CheckerSession

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "dashboard-saas"
    / "schemas"
    / "checker_golden_vectors.json"
)

_REQUIRED_CATEGORY_PREFIXES = (
    "prohibited",
    "high_risk:annex_i",
    "high_risk:annex_iii",
    "derogation:hr3_art_6_3",
    "derogation:hr4_narrow_task",
    "derogation:hr5_no_significant_risk",
    "derogation:hr6_accessory",
    "profiling_override",
    "out_of_scope",
    "entity:provider",
    "entity:deployer",
    "entity:distributor",
    "entity:importer",
    "entity:product_manufacturer",
    "entity:authorised_rep",
)


def _load_vectors() -> list[dict]:
    if not FIXTURE_PATH.exists():
        pytest.skip("dashboard-saas/schemas/checker_golden_vectors.json not reachable")
    doc = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return doc["vectors"]


def test_shared_golden_vectors_match_oss_engine() -> None:
    """Every vector in the shared fixture must match the OSS engine's own
    output exactly — this is the fixture's authoritative source of truth,
    the same engine the vendored copy is drift-checked against."""
    vectors = _load_vectors()
    assert len(vectors) >= 20, "shared golden fixture must carry at least 20 vectors"

    for vector in vectors:
        session = CheckerSession.model_validate(vector["session"])
        expected = vector["expected"]
        result = evaluate(session)

        name = vector["name"]
        assert result.in_scope == expected["in_scope"], name
        assert result.is_high_risk == expected["is_high_risk"], name
        assert result.is_prohibited == expected["is_prohibited"], name
        effective = result.effective_entity.value if result.effective_entity else None
        assert effective == expected["effective_entity"], name
        assert [i.id for i in result.status_changes] == expected["status_change_ids"], (
            name
        )
        assert [i.id for i in result.obligations] == expected["obligation_ids"], name
        assert result.determination_path == expected["determination_path"], name


def test_shared_golden_vectors_cover_required_categories() -> None:
    """The fixture must keep covering every category DG-13 requires:
    prohibited, high-risk via Annex I + Annex III, each Art. 6(3)
    derogation, the profiling override, out-of-scope, and every
    EntityType — not just happen to total 20+ vectors."""
    vectors = _load_vectors()
    seen: set[str] = set()
    for vector in vectors:
        seen.update(vector["categories"])

    missing = [prefix for prefix in _REQUIRED_CATEGORY_PREFIXES if prefix not in seen]
    assert not missing, f"golden fixture is missing required categories: {missing}"
