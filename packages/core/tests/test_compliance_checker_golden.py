"""Golden fixture parity tests for the FLI compliance checker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.compliance_checker.engine import evaluate
from opencomplai_core.compliance_checker.models import CheckerSession, EntityType

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "checker_golden"


def _fixture_paths() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("*.json"))


@pytest.mark.parametrize("fixture_path", _fixture_paths(), ids=lambda p: p.stem)
def test_golden_fixture(fixture_path: Path):
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    session = CheckerSession.model_validate(payload["session"])
    expected = payload["expected"]

    result = evaluate(session)

    assert result.in_scope == expected["in_scope"]
    assert result.is_high_risk == expected["is_high_risk"]
    assert result.is_prohibited == expected["is_prohibited"]

    if expected["effective_entity"] is None:
        assert result.effective_entity is None
    else:
        assert result.effective_entity == EntityType(expected["effective_entity"])

    assert [item.id for item in result.status_changes] == expected["status_change_ids"]
    assert [item.id for item in result.obligations] == expected["obligation_ids"]
    assert result.determination_path == expected["determination_path"]
