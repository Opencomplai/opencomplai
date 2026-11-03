"""Tests for the multi-role checker merge and the rationale export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.compliance_checker import CheckerSession, evaluate
from opencomplai_core.compliance_checker.merge import merge_role_results
from opencomplai_core.compliance_checker.report import (
    render_json,
    render_markdown,
    render_pdf,
)

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "checker_golden"
    / "06_high_risk_provider.json"
)


def _answers() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["session"]["answers"]


def _eval(role: str):
    answers = {**_answers(), "e1_entity_type": role}
    result = evaluate(CheckerSession(answers=answers))
    result.answers = dict(answers)
    return result


def _merged():
    return merge_role_results(
        [("provider", _eval("provider")), ("deployer", _eval("deployer"))]
    )


def test_single_role_returns_result_unchanged() -> None:
    result = _eval("provider")
    merged = merge_role_results([("provider", result)])
    assert merged.result is result
    assert merged.roles == ["provider"]
    assert merged.obligation_ids == [o.id for o in result.obligations]


def test_merge_unions_obligations_in_order_without_duplicates() -> None:
    merged = _merged()
    ids = merged.obligation_ids
    assert "deployer_high_risk" in ids
    assert "provider_high_risk" in ids
    assert ids.count("ai_literacy") == 1
    assert len(ids) == len(set(ids))
    provider_ids = [o.id for o in _eval("provider").obligations]
    assert ids[: len(provider_ids)] == provider_ids
    assert merged.result.session_id is None
    assert merged.result.effective_entity == _eval("provider").effective_entity


def test_flags_are_any() -> None:
    a, b = _eval("provider"), _eval("deployer")
    a.is_high_risk = False
    b.is_high_risk = False
    b.is_prohibited = True
    merged = merge_role_results([("provider", a), ("deployer", b)])
    assert merged.result.is_prohibited is True
    assert merged.result.is_high_risk is False
    assert merged.result.in_scope == (a.in_scope or b.in_scope)
    b.is_high_risk = True
    assert merge_role_results([("p", a), ("d", b)]).result.is_high_risk is True


def test_path_has_role_markers() -> None:
    path = _merged().result.determination_path
    provider_path = _eval("provider").determination_path
    assert path[0] == "role:provider"
    assert path[1 : 1 + len(provider_path)] == provider_path
    assert path[1 + len(provider_path)] == "role:deployer"


def test_rationale_lines_are_deterministic() -> None:
    first, second = _merged().rationale, _merged().rationale
    assert first == second
    assert len(first) == 2
    assert first[0].startswith(
        "provider (effective provider): high risk; obligations: "
    )
    assert first[1].startswith("deployer (effective deployer): ")


def test_empty_input_raises() -> None:
    with pytest.raises(ValueError, match="at least one"):
        merge_role_results([])


def test_render_markdown_unchanged_without_rationale() -> None:
    result = _eval("provider")
    plain = render_markdown(result)
    assert render_markdown(result, rationale=None) == plain
    assert render_markdown(result, rationale=[]) == plain
    assert "Role rationale" not in plain
    assert render_json(result, rationale=None) == result.model_dump_json(indent=2)


def test_render_markdown_and_json_include_rationale() -> None:
    result = _eval("provider")
    lines = ["provider (effective provider): high risk; obligations: x"]
    md = render_markdown(result, rationale=lines)
    assert md.index("## Role rationale") < md.index("## Disclaimer")
    assert f"- {lines[0]}" in md
    data = json.loads(render_json(result, rationale=lines))
    assert data["rationale"] == lines
    assert data["in_scope"] == result.in_scope
    assert render_pdf(result, rationale=lines).startswith(b"%PDF")


def _session(**answers) -> CheckerSession:
    return CheckerSession(
        answers={"gate_is_ai_system": True, "s1_in_scope": True, **answers}
    )


def test_merge_drops_notes_another_role_contradicts() -> None:
    """Consistency review CF-03 and CF-10."""
    high = {"hr2_annex_iii": True, "hr7_profiling": True, "s1_scope_region": "eu"}
    runs = [
        (role, evaluate(_session(e1_entity_type=role, **high)))
        for role in ("provider", "deployer")
    ]
    assert "high_risk_exception" in [n.id for n in runs[1][1].status_changes]
    merged = merge_role_results(runs)
    assert "high_risk_exception" not in [n.id for n in merged.result.status_changes]

    runs = [
        (role, evaluate(_session(e1_entity_type=role, e2_modifications=True)))
        for role in ("provider", "deployer")
    ]
    merged = merge_role_results(runs)
    assert "become_provider" not in [n.id for n in merged.result.status_changes]
    alone = merge_role_results(runs[1:])
    assert "become_provider" in [n.id for n in alone.result.status_changes]


def test_merge_unions_obligation_basis() -> None:
    runs = [
        (role, evaluate(_session(e1_entity_type=role, s1_gpai=True)))
        for role in ("provider", "deployer")
    ]
    merged = merge_role_results(runs)
    assert merged.result.obligation_basis["ai_literacy"] == ["e1_entity_type"]
    assert merged.result.obligation_basis["gpai_provider"] == ["s1_gpai"]


def test_merge_drops_one_roles_out_of_scope_note_when_another_is_in_scope() -> None:
    runs = [
        ("provider", evaluate(_session(e1_entity_type="provider"))),
        (
            "product_manufacturer",
            evaluate(_session(e1_entity_type="product_manufacturer")),
        ),
    ]
    assert "out_of_scope" in [n.id for n in runs[1][1].status_changes]
    merged = merge_role_results(runs)
    assert merged.result.in_scope is True
    assert "out_of_scope" not in [n.id for n in merged.result.status_changes]
