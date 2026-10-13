"""Proposal leads in the scan engine: a side channel that changes nothing else."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import warnings
from pathlib import Path
from typing import Any

import pytest
from opencomplai_core.models import EuAiScanSummary
from opencomplai_core.scan_engine import run_scan
from opencomplai_core.scanner.proposal_leads import (
    LEAD_BAND_RULES,
    lead_band,
    leads_from_evidence,
)

_PURPOSE = "customer support chatbot"
_ALL_AREAS = frozenset(range(3, 9))
_BENCH = Path(__file__).resolve().parents[2] / "ai" / "tests" / "benchmark"

# area -> (code signal of the knowledge pack, person-cue argument)
_SIGNALS = {
    3: ("auto_grade", "grades"),
    4: ("rank_candidates", "applicants"),
    5: ("credit_score", "customer"),
    6: ("recidivism_score", "defendant"),
    7: ("visa_score", "applicant"),
    8: ("voter_target", "voters"),
}
_IMPORT = "from sklearn.ensemble import RandomForestClassifier\n\n\n"


def _program(signal: str, arg: str, name: str = "run") -> str:
    return f"{_IMPORT}def {name}({arg}):\n    result = {signal}({arg})\n    return result\n"


def _repo(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def _scan(root: Path, purpose: str = _PURPOSE, **kwargs: Any):
    if kwargs.get("ai_intent"):
        kwargs.setdefault("ai_model", "codebert-onnx")
    with contextlib.chdir(root), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return run_scan("lead-sys", "HEAD", root, purpose, **kwargs)


@pytest.fixture
def plugin() -> None:
    pytest.importorskip("opencomplai_ai")


@pytest.mark.parametrize("area", sorted(_SIGNALS))
def test_leads_for_each_area_3_to_8(plugin, tmp_path, area):
    signal, arg = _SIGNALS[area]
    root = _repo(tmp_path, {"src/a.py": _program(signal, arg)})
    report = _scan(root, lead_areas=_ALL_AREAS)
    assert report.eu_ai_scan is not None
    leads = report.eu_ai_scan.proposal_leads
    assert [
        (x.reason, x.file, x.line, x.function, x.annex_iii_area, x.signals)
        for x in leads
    ] == [("deterministic_matcher", "src/a.py", 5, signal, area, [signal])]
    assert leads[0].confidence_band == ("low" if area == 5 else "medium")
    # a lead is not a finding
    assert report.eu_ai_scan.high_risk == []
    assert report.eu_ai_scan.regulatory_finding_count == 0
    assert all(e.intent_annotation is None for e in report.evidence)
    assert all(e.detector_id != "DET_INTENT_V1" for e in report.evidence)


def test_area_5_band_is_lowest():
    assert LEAD_BAND_RULES["needs_founder_review"] is True
    assert lead_band(5, ["credit_score"]) == "low"
    assert lead_band(4, ["rank_candidates"]) == "medium"
    assert lead_band(4, ["candidate ranking"]) == "low"  # keyword only
    assert {lead_band(a, ["rank_candidates"]) for a in range(1, 9)} <= {"low", "medium"}


def test_area_5_band_is_lowest_in_a_scan(plugin, tmp_path):
    _repo(
        tmp_path,
        {
            "src/five.py": _program(*_SIGNALS[5]),
            "src/four.py": _program(*_SIGNALS[4]),
        },
    )
    leads = _scan(tmp_path, lead_areas=_ALL_AREAS).eu_ai_scan.proposal_leads
    assert {x.annex_iii_area: x.confidence_band for x in leads} == {
        4: "medium",
        5: "low",
    }


def test_declared_purpose_echo_excluded(plugin, tmp_path):
    from opencomplai_ai.classifier import IntentClassifier

    purpose = "Screen job applicants for hiring decisions"
    snippet = "value = model.predict(x)"
    echo = IntentClassifier().classify(snippet, purpose, "a.py:1", token="predict")
    assert echo is not None
    assert echo.declared_purpose_used is True
    _repo(
        tmp_path,
        {"src/a.py": f"{_IMPORT}def f(x):\n    return model.predict(x)\n"},
    )
    assert _scan(tmp_path, purpose, lead_areas=_ALL_AREAS).eu_ai_scan is None
    # the intent path reports the echo as a finding; leads must not
    found = _scan(tmp_path, purpose, ai_intent=True).eu_ai_scan
    assert found is not None
    assert [f.annex_iii_area for f in found.high_risk] == [4]
    assert found.proposal_leads == []


def test_empty_leads_not_serialised(tmp_path):
    assert "proposal_leads" not in EuAiScanSummary().model_dump_json()
    assert EuAiScanSummary().model_dump()["proposal_leads"] == []
    root = _repo(tmp_path, {"src/a.py": "x = 1\n"})
    report = _scan(root, lead_areas=_ALL_AREAS)
    assert report.eu_ai_scan is None
    assert "proposal_leads" not in report.model_dump_json()
    assert _scan(root).eu_ai_scan is None


def test_leads_serialised_when_present(plugin, tmp_path):
    root = _repo(tmp_path, {"src/a.py": _program(*_SIGNALS[4])})
    report = _scan(root, lead_areas=_ALL_AREAS)
    block = json.loads(report.model_dump_json())["eu_ai_scan"]
    assert [x["annex_iii_area"] for x in block["proposal_leads"]] == [4]


def test_leads_do_not_change_hash_or_gate_inputs(plugin, tmp_path):
    root = _repo(
        tmp_path,
        {
            "src/a.py": _program(*_SIGNALS[4]),
            "src/b.py": "import face_recognition\n",
        },
    )
    plain = _scan(root)
    led = _scan(root, lead_areas=_ALL_AREAS)
    assert led.eu_ai_scan is not None
    assert plain.eu_ai_scan is None
    for name in (
        "report_hash",
        "input_digest",
        "config_hash",
        "scan_id",
        "severity",
        "discrepancies",
        "detected_categories",
        "scan_errors",
        "detector_errors",
        "warnings",
        "limits_hit",
        "source_tree_sha256",
    ):
        assert getattr(led, name) == getattr(plain, name), name
    assert [e.model_dump() for e in led.evidence] == [
        e.model_dump() for e in plain.evidence
    ]
    assert [f.model_dump() for f in led.findings] == [
        f.model_dump() for f in plain.findings
    ]


def test_leads_off_with_ai_intent(plugin, tmp_path):
    root = _repo(tmp_path, {"src/a.py": _program(*_SIGNALS[4])})
    intent = _scan(root, ai_intent=True)
    both = _scan(root, ai_intent=True, lead_areas=_ALL_AREAS)
    assert both.eu_ai_scan is not None
    assert both.eu_ai_scan.proposal_leads == []
    assert both.report_hash == intent.report_hash
    assert (
        json.loads(both.model_dump_json())["eu_ai_scan"]
        == json.loads(intent.model_dump_json())["eu_ai_scan"]
    )


def test_lead_areas_restrict_the_areas(plugin, tmp_path):
    _repo(
        tmp_path,
        {
            "src/four.py": _program(*_SIGNALS[4]),
            "src/seven.py": _program(*_SIGNALS[7]),
        },
    )
    both = _scan(tmp_path, lead_areas=_ALL_AREAS).eu_ai_scan.proposal_leads
    assert [x.annex_iii_area for x in both] == [4, 7]
    only = _scan(tmp_path, lead_areas=frozenset({7})).eu_ai_scan.proposal_leads
    assert [(x.file, x.annex_iii_area) for x in only] == [("src/seven.py", 7)]
    assert _scan(tmp_path, lead_areas=frozenset({3})).eu_ai_scan is None


def test_leads_sorted_and_one_per_call_site(plugin, tmp_path):
    _repo(
        tmp_path,
        {
            "src/b.py": _program(*_SIGNALS[7]),
            "src/a.py": _program(*_SIGNALS[4]),
        },
    )
    leads = _scan(tmp_path, lead_areas=_ALL_AREAS).eu_ai_scan.proposal_leads
    keys = [(x.file, x.line, x.function, x.annex_iii_area) for x in leads]
    assert keys == sorted(set(keys))
    assert leads_from_evidence([], _ALL_AREAS) == []


def test_matcher_failure_is_a_missing_lead_not_a_failed_scan(
    plugin, tmp_path, monkeypatch
):
    from opencomplai_ai.detector import IntentDetector

    def boom(self, *args, **kwargs):
        raise ValueError("backend exploded")

    monkeypatch.setattr(IntentDetector, "detect", boom)
    root = _repo(tmp_path, {"src/a.py": _program(*_SIGNALS[4])})
    with contextlib.chdir(root), pytest.warns(UserWarning, match="leads skipped"):
        report = run_scan("lead-sys", "HEAD", root, _PURPOSE, lead_areas=_ALL_AREAS)
    assert report.eu_ai_scan is None
    assert report.scan_errors == []
    assert report.detector_errors == []
    assert not any("leads" in w for w in report.warnings)


# --- the matcher itself is not touched by this tier --------------------------

_CLASSIFIED = [
    # snippet, declared purpose, token -> (tier, area, matched signals, declared echo)
    (
        "scores = rank_candidates(applicants)",
        "",
        "rank_candidates",
        ("high_risk", 4, ["rank_candidates"], False, 0.8),
    ),
    (
        "# candidate ranking for hiring\nresult = run(applicants)",
        "",
        "run",
        ("high_risk", 4, ["candidate ranking"], False, 0.8),
    ),
    (
        "risk = credit_score(portfolio)",
        "",
        "credit_score",
        ("minimal", None, ["credit_score"], False, 0.6),
    ),
    ("total = sum(prices)", "", "sum", None),
    (
        "value = model.predict(x)",
        "Screen job applicants for hiring decisions",
        "predict",
        ("high_risk", 4, ["predict"], True, 0.8),
    ),
]

# Figures recorded for the 46-program training set on the intent path:
# area -> (tp, fp, fn).
_INTENT_PINS = {
    1: (4, 0, 0),
    2: (1, 0, 2),
    3: (4, 0, 0),
    4: (3, 0, 1),
    5: (5, 8, 0),
    6: (2, 0, 1),
    7: (1, 0, 2),
    8: (2, 0, 1),
}


def test_matcher_module_not_modified_semantics(plugin):
    from opencomplai_ai.classifier import IntentClassifier

    classifier = IntentClassifier()
    for snippet, purpose, token, expected in _CLASSIFIED:
        ann = classifier.classify(snippet, purpose, "src/a.py:1", token=token)
        if expected is None:
            assert ann is None, snippet
            continue
        assert ann is not None, snippet
        assert (
            ann.risk_tier,
            ann.annex_iii_area,
            list(ann.matched_signals),
            ann.declared_purpose_used,
            ann.confidence,
        ) == expected, snippet

    spec = importlib.util.spec_from_file_location(
        "leads_engine_run_benchmark", _BENCH / "run_benchmark.py"
    )
    assert spec is not None
    assert spec.loader is not None
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    measured = bench.measure()
    assert measured["fixtures"] == 46
    assert {
        area: (c["tp"], c["fp"], c["fn"]) for area, c in measured["per_area"].items()
    } == _INTENT_PINS
