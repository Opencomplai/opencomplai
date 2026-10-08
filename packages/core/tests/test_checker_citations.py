"""Citation, FRIA-scope and prohibition text in the checker data (SU-101a)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import opencomplai_cli.commands.checker as cli_checker
from opencomplai_core.compliance_checker.engine import evaluate
from opencomplai_core.compliance_checker.models import CheckerSession

DATA = (
    Path(__file__).resolve().parents[1] / "src/opencomplai_core/compliance_checker/data"
)
FLAGS = Path(__file__).parent / "fixtures" / "checker_review_flags.json"
STALE = re.compile(
    r"Art\. 28|Art\. 29|social scoring by public authorities|public authorities or Union"
)


def _obligations() -> dict:
    return json.loads((DATA / "obligations.json").read_text(encoding="utf-8"))


def _fria_label() -> str:
    questions = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    return questions["r5_fria"]["label"]


def test_no_proposal_era_strings_in_core_checker_data():
    for path in (
        DATA / "obligations.json",
        DATA / "questions.json",
        Path(cli_checker.__file__),
    ):
        hit = STALE.search(path.read_text(encoding="utf-8"))
        assert hit is None, f"{path.name}: {hit.group(0)}"


def test_fria_scope_names_public_services_and_annex_iii_5b_5c():
    obligations = _obligations()
    for text in (
        obligations["fria"]["body"],
        obligations["deployer_high_risk"]["body"],
        _fria_label(),
    ):
        assert "public services" in text
        assert "5(b)" in text
        assert "5(c)" in text
    assert obligations["fria"]["article_ref"] == "Art. 27"


def test_credit_scoring_deployer_session_produces_fria():
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "deployer",
                "hr2_annex_iii": True,
                "r5_fria": True,
            }
        )
    )
    assert "fria" in [o.id for o in result.obligations]


def test_prohibited_body_lists_ninth_practice_with_date():
    prohibited = _obligations()["prohibited"]
    assert "social scoring of natural persons" in prohibited["body"]
    assert "2 December 2026" in prohibited["body"]
    assert "non-consensual intimate imagery" in prohibited["body"]
    assert prohibited["article_ref"] == "Art. 5"


def test_cli_fria_prompt_matches_questions_json():
    assert _fria_label() in Path(cli_checker.__file__).read_text(encoding="utf-8")


def test_every_changed_text_has_a_complete_review_flag():
    flags = json.loads(FLAGS.read_text(encoding="utf-8"))
    expected = {
        "obligations.authorised_representative",
        "obligations.deployer_general",
        "obligations.deployer_high_risk",
        "obligations.fria",
        "obligations.prohibited",
        "obligations.ai_literacy",
        "obligations.provider_art_6_4_registration",
        "questions.r5_fria",
        "engine.fria_requires_annex_iii",
        "docs.risk_levels_prohibited",
    }
    assert expected <= flags.keys()
    for key in expected:
        flag = flags[key]
        assert flag["source"].strip(), key
        assert flag["note"].strip(), key
        assert flag["confidence"] in {"high", "medium", "low"}, key
        assert flag["needs_founder_review"] is True, key
