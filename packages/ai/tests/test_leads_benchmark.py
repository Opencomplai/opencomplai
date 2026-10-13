"""Annex III areas 3 to 8 ("leads") benchmark: shape, pinned numbers, runner output.

The numbers in ``LEADS_PINNED`` and ``LEADS_TOP1_PINNED`` are as measured once at
the commit that added this set, before any lead tier or matcher change. They move
only by a deliberate re-pin that edits no program and no label. The set is never to
be tuned against: a zero here is the recorded result, not a defect to fix by
editing a program, a label or the signal dictionary. The training and held-out
pins stay in ``test_annex_iii_benchmark.py`` and
``test_annex_iii_heldout_benchmark.py``, which are untouched.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import socket
from fractions import Fraction
from pathlib import Path

import pytest

_BENCH_DIR = Path(__file__).parent / "benchmark"
_FORBIDDEN_PATH_PARTS = ("test", "spec", "doc", "dev", "vendor", "generated")
_HEADING = (
    "Leads set (28 programs, areas 3 to 8; "
    "separate from the training and held-out sets)"
)

# Intent path and default scan path, as (tp, fp, fn); 28 programs, 19 labelled with
# an Annex III area (3 to 8) and 9 hard negatives. Areas 1 and 2 carry only false
# positives: the set has no program labelled with them.
LEADS_PINNED = {
    "fixtures": 28,
    "none_fixtures": 9,
    "none_clean": 9,
    "scan_none_clean": 9,
    "overall": (2, 2, 17),
    "scan_overall": (0, 1, 19),
    "per_area": {
        1: (0, 0, 0),
        2: (0, 0, 0),
        3: (0, 0, 3),
        4: (1, 0, 2),
        5: (0, 2, 4),
        6: (1, 0, 2),
        7: (0, 0, 3),
        8: (0, 0, 3),
    },
    "scan_per_area": {
        1: (0, 1, 0),
        2: (0, 0, 0),
        3: (0, 0, 3),
        4: (0, 0, 3),
        5: (0, 0, 4),
        6: (0, 0, 3),
        7: (0, 0, 3),
        8: (0, 0, 3),
    },
    # language -> (programs, area-labelled programs detected on the intent path)
    "by_language": {
        "go": (4, 0),
        "java": (5, 0),
        "javascript": (3, 1),
        "python": (12, 0),
        "typescript": (4, 1),
    },
}

# (n, correct, none, tie, wrong) of the proposal's single pick per labelled program.
LEADS_TOP1_PINNED = (19, 0, 17, 0, 2)

# sha256 of repr(sorted((name, area, kind))) over fixtures_leads.LEADS.
LEADS_SHA256 = "ba332cd875c079804f646c3bb52832680e6128c91d46a95e303757ed6dc2107f"

# The three existing sets, pinned here so they cannot drift unseen.
TRAINING_SHA256 = "7e6eec824d41b61bb508927a41ef2a37e9b6b0c10abb64063868bdff7a4249de"
HELDOUT_SHA256 = "d308e6bf11fcab535409e123672e6f353a053f748dbd2f4fd899e55ef7888704"


def _load(name: str, tag: str):
    spec = importlib.util.spec_from_file_location(
        f"annex_iii_leads_{tag}", _BENCH_DIR / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixtures_mod = _load("fixtures", "fixtures")
heldout_mod = _load("heldout_fixtures", "heldout")
candidates_mod = _load("candidate_fixtures", "candidates")
leads_mod = _load("fixtures_leads", "leads")
bench = _load("run_benchmark", "bench")


@pytest.fixture(scope="module")
def leads_measured() -> dict:
    return bench.measure_leads()


@pytest.fixture(scope="module")
def leads_top1() -> dict:
    return bench.measure_top1(leads_mod.LEADS)


def _counts(per_area: dict) -> dict:
    return {a: (c["tp"], c["fp"], c["fn"]) for a, c in per_area.items()}


def _tuple(c: dict) -> tuple[int, int, int]:
    return (c["tp"], c["fp"], c["fn"])


def _digest(pairs: list) -> str:
    return hashlib.sha256(repr(sorted(pairs)).encode("utf-8")).hexdigest()


def test_leads_set_shape():
    fixtures = leads_mod.LEADS
    names = [f["name"] for f in fixtures]
    assert len(fixtures) >= 24
    assert len(set(names)) == len(names)
    existing = {f["name"] for f in fixtures_mod.FIXTURES}
    existing |= {f["name"] for f in heldout_mod.HELDOUT}
    assert not set(names) & existing
    for f in fixtures:
        assert f["labeller"] in {"author", "second_pass"}, f["name"]
        assert f["purpose"], f["name"]
        assert f["why"], f["name"]
        assert f["kind"] in {"positive", "hard_negative"}, f["name"]
        assert (f["kind"] == "hard_negative") == (f["area"] is None), f["name"]
        assert "art5" not in f, f["name"]
    areas = {f["area"] for f in fixtures}
    assert areas <= {None, *range(3, 9)}
    assert not any(f["area"] in (1, 2) for f in fixtures)
    for area in range(3, 9):
        positives = [
            f for f in fixtures if f["area"] == area and f["kind"] == "positive"
        ]
        assert len(positives) >= 3, area
    assert len([f for f in fixtures if f["kind"] == "hard_negative"]) >= 8
    non_python = [f for f in fixtures if f["language"] != "python"]
    assert len(non_python) >= 10
    by_lang = {f["language"] for f in non_python}
    assert by_lang <= {"javascript", "typescript", "java", "go"}
    assert (
        len([f for f in non_python if f["language"] in {"javascript", "typescript"}])
        >= 2
    )
    assert len([f for f in non_python if f["language"] == "java"]) >= 2
    assert len([f for f in non_python if f["language"] == "go"]) >= 2
    manifests = {"java": "pom.xml", "go": "go.mod"}
    for f in non_python:
        if f["language"] in manifests:
            assert manifests[f["language"]] in f["files"], f["name"]
    for f in fixtures:
        assert 2 <= len(f["files"]) <= 4, f["name"]
        for rel, text in f["files"].items():
            assert len(text.splitlines()) < 30, (f["name"], rel)
            text.encode("ascii")
            for part in Path(rel).parts:
                for banned in _FORBIDDEN_PATH_PARTS:
                    assert banned not in part.lower(), (f["name"], rel, banned)
    assert leads_mod.LEADS_META["needs_founder_review"] is True
    assert leads_mod.LEADS_META["confidence"] == "low"
    assert leads_mod.LEADS_META["source"]
    assert leads_mod.LEADS_META["labelled_by"]


def test_leads_numbers_are_pinned(leads_measured):
    m = leads_measured
    assert m["fixtures"] == LEADS_PINNED["fixtures"]
    assert m["none_fixtures"] == LEADS_PINNED["none_fixtures"]
    assert m["none_clean"] == LEADS_PINNED["none_clean"]
    assert m["scan_none_clean"] == LEADS_PINNED["scan_none_clean"]
    assert _tuple(m["overall"]) == LEADS_PINNED["overall"]
    assert _tuple(m["scan_overall"]) == LEADS_PINNED["scan_overall"]
    assert _counts(m["per_area"]) == LEADS_PINNED["per_area"]
    assert _counts(m["scan_per_area"]) == LEADS_PINNED["scan_per_area"]
    assert {
        lang: (row["fixtures"], row["area_tp"])
        for lang, row in m["by_language"].items()
    } == LEADS_PINNED["by_language"]
    assert m["by_kind"] == {"positive": 19, "hard_negative": 9}


def test_leads_top1_is_pinned(leads_top1):
    t = leads_top1
    assert (t["n"], t["correct"], t["none"], t["tie"], t["wrong"]) == (
        LEADS_TOP1_PINNED
    )


def test_leads_set_digest_is_pinned():
    pairs = [(f["name"], f["area"], f["kind"]) for f in leads_mod.LEADS]
    assert _digest(pairs) == LEADS_SHA256


def test_existing_sets_are_untouched():
    training = fixtures_mod.FIXTURES
    assert len(training) == 46
    assert _digest([(f["name"], f["area"]) for f in training]) == TRAINING_SHA256
    heldout = heldout_mod.HELDOUT
    assert len(heldout) == 24
    assert _digest([(f["name"], f["area"]) for f in heldout]) == HELDOUT_SHA256
    assert len(candidates_mod.CANDIDATE_FIXTURES) == 8


def test_script_prints_leads_section_separately(capsys):
    assert bench.main([]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines.count(_HEADING) == 1
    for path in ("Intent path", "Default scan path"):
        rows = [ln for ln in lines if ln.startswith(f"| Leads set | {path} |")]
        assert len(rows) == 1, path
    assert len([ln for ln in lines if ln.startswith("| Leads set |")]) == 2
    for prefix in (
        "leads_none_clean:",
        "leads_scan_none_clean:",
        "leads_by_kind:",
        "leads_language_go:",
        "leads_language_java:",
        "leads_top1:",
    ):
        assert len([ln for ln in lines if ln.startswith(prefix)]) == 1, prefix
    # The existing tests count these prefixes; the leads table must not add to them.
    assert len([ln for ln in lines if ln.startswith("| Overall |")]) == 2
    for area in range(1, 9):
        assert len([ln for ln in lines if ln.startswith(f"| {area} |")]) == 2, area
    assert len([ln for ln in lines if ln.startswith("| Set | n | Correct |")]) == 1
    assert len([ln for ln in lines if re.match(r"\| Held-out \| \d+ \|", ln)]) == 1
    assert len([ln for ln in lines if re.match(r"\| Training \| \d+ \|", ln)]) == 1
    # The old headings are still there and the leads block sits before candidates.
    assert any(ln.startswith("Training set (46 programs)") for ln in lines)
    assert any(ln.startswith("Held-out set (24 programs)") for ln in lines)
    assert "Proposal top-1" in lines
    heading = lines.index(_HEADING)
    candidates = next(
        i for i, ln in enumerate(lines) if ln.startswith("Candidates (leads for")
    )
    assert heading < candidates
    assert not any(ln.startswith("| Leads set |") for ln in lines[candidates:])


def test_leads_runs_offline_without_model(monkeypatch):
    import opencomplai_ai.downloader as downloader

    downloads: list[str] = []

    def no_socket(self, *args, **kwargs):
        raise OSError("sockets are disabled in this test")

    def no_download(model_id, *args, **kwargs):
        downloads.append(model_id)
        raise AssertionError("a model download was attempted")

    monkeypatch.setattr(socket.socket, "connect", no_socket)
    monkeypatch.setattr(downloader, "ensure_model", no_download)

    result = bench.measure_leads()
    top1 = bench.measure_top1(leads_mod.LEADS)

    assert result["fixtures"] == LEADS_PINNED["fixtures"]
    assert top1["n"] == LEADS_TOP1_PINNED[0]
    assert downloads == []


# --- Lead tier: what the CLI shows as leads, measured on the three sets --------
#
# Measured once with ``run_benchmark.py`` and written from its output; no fixture,
# label, token or dictionary was edited to move a number. A poor figure is the
# result. Areas 1 and 2 never produce a lead and are not listed.

_DOCS_PAGE = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "src"
    / "concepts"
    / "annex-iii-benchmark.md"
)

# Per set: programs, per-area (tp, fp, fn) for areas 3 to 8, overall (tp, fp, fn),
# top-1 (n, correct, none, tie, wrong) and the programs with a lead for an area
# they are not labelled with.
LEAD_TIER_PINNED = {
    "training": {
        "programs": 46,
        "per_area": {
            3: (2, 0, 2),
            4: (2, 0, 2),
            5: (4, 8, 1),
            6: (2, 0, 1),
            7: (0, 0, 3),
            8: (2, 0, 1),
        },
        "overall": (12, 8, 10),
        "top1": (29, 13, 9, 2, 5),
        "fp_programs": {
            5: [
                "admissions-ranker",
                "attrition-risk",
                "churn-predictor",
                "interview-scorer",
                "recidivism-risk-tool",
                "statement-credibility-scorer",
                "suspect-lead-ranker",
                "voter-microtargeting",
            ]
        },
    },
    "held-out": {
        "programs": 24,
        "per_area": {
            3: (0, 0, 1),
            4: (0, 0, 2),
            5: (0, 3, 2),
            6: (1, 0, 0),
            7: (0, 0, 2),
            8: (0, 0, 1),
        },
        "overall": (1, 3, 8),
        "top1": (12, 1, 9, 1, 1),
        "fp_programs": {
            5: [
                "home-thermostat-optimizer",
                "reoffending-risk-estimator",
                "water-network-pressure-guard",
            ]
        },
    },
    "areas 3-8": {
        "programs": 28,
        "per_area": {
            3: (0, 0, 3),
            4: (0, 0, 3),
            5: (0, 2, 4),
            6: (0, 0, 3),
            7: (0, 0, 3),
            8: (0, 0, 3),
        },
        "overall": (0, 2, 19),
        "top1": (19, 0, 17, 0, 2),
        "fp_programs": {5: ["parole-reoffending-scorer", "voter-persuasion-targeting"]},
    },
}

# area -> policy from the pooled floor (22 of 30 on precision, area 5 always shown
# at the lowest confidence). Kept equal to packages/cli/tests/test_leads_area_policy.py.
EXPECTED_POLICY = {
    3: "lead",
    4: "lead",
    5: "lowest_confidence",
    6: "lead",
    7: "notice_only",
    8: "lead",
}
EXPECTED_LEADS_DEFAULT_ON = True


@pytest.fixture(scope="module")
def lead_tier() -> dict:
    return {
        "training": bench.measure_lead_tier(fixtures_mod.FIXTURES),
        "held-out": bench.measure_lead_tier(heldout_mod.HELDOUT),
        "areas 3-8": bench.measure_lead_tier(leads_mod.LEADS),
    }


def test_leads_numbers_are_pinned_per_set_and_area(lead_tier):
    assert list(lead_tier) == list(LEAD_TIER_PINNED)
    for key, got in lead_tier.items():
        want = LEAD_TIER_PINNED[key]
        assert got["programs"] == want["programs"], key
        assert _counts(got["per_area"]) == want["per_area"], key
        assert _tuple(got["overall"]) == want["overall"], key
        top1 = got["top1"]
        assert (
            top1["n"],
            top1["correct"],
            top1["none"],
            top1["tie"],
            top1["wrong"],
        ) == want["top1"], key
        assert got["fp_programs"] == want["fp_programs"], key


def test_leads_area_policy_follows_the_floor(lead_tier):
    pooled = bench.leads_pooled(lead_tier)
    policy = bench.leads_area_policy(pooled)
    assert policy == EXPECTED_POLICY
    assert policy[5] == "lowest_confidence"
    floor = Fraction(*bench.LEADS_FLOOR)
    for area, tp_fp_fn in pooled.items():
        tp, fp, _ = tp_fp_fn
        if area == 5:
            continue
        met = tp > 0 and Fraction(tp, tp + fp) >= floor
        assert policy[area] == ("lead" if met else "notice_only"), area
        if policy[area] == "notice_only":
            assert tp == 0 or Fraction(tp, tp + fp) < floor, area
    # the boundary itself: exactly 22 of 30 is at the floor, 21 of 30 is under it
    edge = {3: (22, 8, 0), 4: (21, 9, 0), 5: (0, 9, 0), 6: (0, 0, 4), 7: (1, 0, 0)}
    edge = {a: edge.get(a, (0, 0, 0)) for a in pooled}
    assert bench.leads_area_policy(edge) == {
        3: "lead",
        4: "notice_only",
        5: "lowest_confidence",
        6: "notice_only",
        7: "lead",
        8: "notice_only",
    }
    assert bench.leads_default_on({**edge, 3: (22, 8, 0), 4: (0, 0, 0)}) is True
    assert bench.leads_default_on({**edge, 3: (21, 9, 0), 4: (0, 0, 0)}) is False


def test_default_switch_follows_the_overall_floor(lead_tier):
    pooled = bench.leads_pooled(lead_tier)
    tp = sum(c[0] for a, c in pooled.items() if a != 5)
    fp = sum(c[1] for a, c in pooled.items() if a != 5)
    floor = Fraction(*bench.LEADS_FLOOR)
    expected = tp + fp > 0 and Fraction(tp, tp + fp) >= floor
    assert bench.leads_default_on(pooled) is expected
    assert bench.leads_default_on(pooled) is EXPECTED_LEADS_DEFAULT_ON
    # the decision pool excludes area 5: a pool of area 5 alone is never "on"
    only_five = dict.fromkeys(pooled, (0, 0, 0))
    only_five[5] = pooled[5]
    assert bench.leads_default_on(only_five) is False


def test_floor_equals_training_intent_precision(lead_tier):
    training = bench.measure()["overall"]
    assert Fraction(training["tp"], training["tp"] + training["fp"]) == Fraction(
        *bench.LEADS_FLOOR
    )


def test_existing_pins_still_hold():
    training = bench.measure()
    assert _tuple(training["overall"]) == (22, 8, 7)
    heldout = bench.measure_heldout()
    assert _tuple(heldout["overall"]) == (4, 4, 8)
    t = bench.measure_top1(fixtures_mod.FIXTURES)
    assert (t["n"], t["correct"], t["none"], t["tie"], t["wrong"]) == (
        29,
        13,
        9,
        2,
        5,
    )
    t = bench.measure_top1(heldout_mod.HELDOUT)
    assert (t["n"], t["correct"], t["none"], t["tie"], t["wrong"]) == (12, 1, 9, 1, 1)


def _page_blocks(page: str) -> list[str]:
    blocks, current = [], []
    for line in [*page.splitlines(), ""]:
        if line.startswith("|"):
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    return blocks


def test_docs_page_shows_leads_tables(lead_tier):
    page = _DOCS_PAGE.read_text(encoding="utf-8")
    blocks = _page_blocks(page)
    pooled = bench.leads_pooled(lead_tier)
    tables = bench.format_leads_tables(lead_tier, pooled)
    assert len(tables) == 5
    for table in tables:
        assert table in blocks
    assert any(ln.startswith("## Leads on the three sets") for ln in page.splitlines())
    lower = page.lower()
    assert "synthetic" in lower
    assert "single author" in lower
    if not EXPECTED_LEADS_DEFAULT_ON:
        assert "OPENCOMPLAI_LEADS=1" in page


def test_leads_run_offline(monkeypatch):
    import opencomplai_ai.downloader as downloader

    downloads: list[str] = []

    def no_socket(self, *args, **kwargs):
        raise OSError("sockets are disabled in this test")

    def no_download(model_id, *args, **kwargs):
        downloads.append(model_id)
        raise AssertionError("a model download was attempted")

    monkeypatch.setattr(socket.socket, "connect", no_socket)
    monkeypatch.setattr(downloader, "ensure_model", no_download)

    result = bench.measure_lead_tier(leads_mod.LEADS)

    assert result["programs"] == LEAD_TIER_PINNED["areas 3-8"]["programs"]
    assert _counts(result["per_area"]) == LEAD_TIER_PINNED["areas 3-8"]["per_area"]
    assert downloads == []
