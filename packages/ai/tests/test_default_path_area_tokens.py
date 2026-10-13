"""Default-path tokens for Annex III areas 2 to 4: evidence, admission rule, floors.

The default scan path (``run_scan`` without intent analysis) reaches no area 2, 3
or 4 today. Each candidate token is evaluated for how often it fires on the 46
training fixtures and the held-out set, and ships a token only when it passes the
admission rule:

* at least 2 distinct positive training fixtures of its own area,
* 0 hits on every training fixture with no area and on every held-out negative,
* overall default precision stays at or above 4/9 and recall at or above 4/29,
* the intent-path ``per_area`` counts and the training top-1 tuple do not move.

"No token added" is a complete result. The candidate list, the measurements and
the decisions are recorded in docs/src/concepts/annex-iii-benchmark.md; this
file recomputes them. Held-out positives are reported and never used to choose.
"""

from __future__ import annotations

import importlib.util
import json
import re
import tempfile
from contextlib import contextmanager, nullcontext
from pathlib import Path
from unittest import mock

import pytest
from opencomplai_core.knowledge.annex_iii import lookup_by_area
from opencomplai_core.models import EvidenceScope, SignalCategory
from opencomplai_core.scan_engine import run_scan
from opencomplai_core.scanner.detectors import _signals
from opencomplai_core.scanner.mapping import _AREA_TO_TAXONOMY

_TESTS_DIR = Path(__file__).parent
_BENCH_DIR = _TESTS_DIR / "benchmark"
_REPO = Path(__file__).resolve().parents[3]
_SIGNALS_JSON = (
    _REPO
    / "packages"
    / "core"
    / "src"
    / "opencomplai_core"
    / "scanner"
    / "data"
    / "ai_signals.json"
)
_DOCS_PAGE = _REPO / "docs" / "src" / "concepts" / "annex-iii-benchmark.md"
_SECTION = "## Default-path evidence for areas 2 to 4"
_HEADER = (
    "| Token | Area | Positives | No-area hits | Held-out hits | Decision | "
    "Source | Confidence | needs_founder_review |"
)
_AREAS = (2, 3, 4)

# Domain libraries and one client method, each with the source that names it.
# (token, area, source). Evaluated like the pack tokens; none is assumed to pass.
_LIBRARIES = (
    ("pandapower", 2, "pandapower, power-system modelling library (pandapower.org)"),
    ("pymodbus", 2, "pymodbus, Modbus protocol library (PyPI)"),
    (
        "write_register",
        2,
        "pymodbus client method write_register (Modbus function code 6)",
    ),
    ("opcua", 2, "python-opcua, OPC UA client library (IEC 62541)"),
    ("asyncua", 2, "asyncua, OPC UA client library (IEC 62541)"),
    ("snap7", 2, "python-snap7, Siemens S7 PLC protocol client"),
    ("pycomm3", 2, "pycomm3, Allen-Bradley EtherNet/IP PLC client"),
    ("traci", 2, "Eclipse SUMO traffic simulation control interface (TraCI)"),
    ("sumolib", 2, "Eclipse SUMO traffic network library (sumolib)"),
)
# Names that occur in the 10 area 2 to 4 training fixtures and in no pack list.
# Listed so the evidence shows why they are not shipped: each is one fixture's
# own function or file name.
_FIXTURE_NAMES = (
    ("scada_link", 2, "file name in grid-load-balancer, not an import"),
    ("rank_applicants", 3, "function name in admissions-ranker"),
    ("mark_essay", 3, "function name in essay-grader"),
    ("rank_resumes", 4, "function name in resume-screener"),
    ("score_interview", 4, "function name in interview-scorer"),
    ("attrition_risk", 4, "function name in attrition-risk"),
)


def _candidates() -> list[tuple[str, int, str]]:
    seen: set[str] = set()
    rows: list[tuple[str, int, str]] = []
    for area in _AREAS:
        for entry in lookup_by_area(area):
            for token in entry.code_signals:
                if token not in seen:
                    seen.add(token)
                    rows.append(
                        (
                            token,
                            area,
                            f"Annex III pack code_signals, area {area}"
                            f" sub-point {entry.subpoint}",
                        )
                    )
    for token, area, source in (*_LIBRARIES, *_FIXTURE_NAMES):
        assert token not in seen, token
        seen.add(token)
        rows.append((token, area, source))
    return rows


CANDIDATES = _candidates()
_AREA_OF = {token: area for token, area, _ in CANDIDATES}


def _load(name: str, tag: str):
    spec = importlib.util.spec_from_file_location(
        f"default_path_tokens_{tag}", _BENCH_DIR / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixtures_mod = _load("fixtures", "fixtures")
heldout_mod = _load("heldout_fixtures", "heldout")
bench = _load("run_benchmark", "bench")


def _load_heldout_pins():
    spec = importlib.util.spec_from_file_location(
        "default_path_tokens_heldout_pins",
        _TESTS_DIR / "test_annex_iii_heldout_benchmark.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _shipped() -> dict[str, list[str]]:
    data = json.loads(_SIGNALS_JSON.read_text(encoding="utf-8"))
    return data.get("area_signals", {})


@contextmanager
def _view(token_areas: dict[str, int]):
    """Candidate-only dictionary view: the tokens first in ``scoring`` and listed
    in ``area_signals``, in place of what ships. The detectors and the taxonomy
    mapping both read the dictionary through ``_signals.load_signals``, so the
    real code paths run; nothing on disk changes.
    """
    real = _signals.load_signals()
    front = list(token_areas)
    groups: dict[str, list[str]] = {}
    for token, area in token_areas.items():
        groups.setdefault(_AREA_TO_TAXONOMY[area], []).append(token)
    patched = {
        **real,
        "scoring": [*front, *[t for t in real["scoring"] if t not in front]],
        "area_signals": groups,
    }
    saved = dict(_signals._PATTERN_CACHE)
    _signals._PATTERN_CACHE.clear()
    try:
        with mock.patch.object(_signals, "load_signals", return_value=patched):
            yield
    finally:
        _signals._PATTERN_CACHE.clear()
        _signals._PATTERN_CACHE.update(saved)


def _write(fixture: dict, root: Path) -> str:
    """Write a fixture's files under root; return its lower-cased path and text."""
    parts = []
    for rel, text in fixture["files"].items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        parts.append(f"{rel}\n{text}")
    return "\n".join(parts).lower()


def _could_match(token: str, haystack: str) -> bool:
    """Sound pre-filter: a token can only match text that holds each of its parts."""
    return all(part in haystack for part in re.split(r"[_.\-]", token.lower()) if part)


def _token_hit(report, token: str, area: int) -> bool:
    """True when evidence labelled with the token reached its area on the scan."""
    ids = {
        e.evidence_id
        for e in report.evidence
        if e.category == SignalCategory.SCORING_PROFILING
        and e.token_label.partition("@")[0] == token
    }
    key = _AREA_TO_TAXONOMY[area]
    return any(
        ids & set(f.evidence_ids)
        and key in f.mapped_taxonomy
        and (f.scope != EvidenceScope.DOCS or f.strength >= 0.5)
        for f in report.findings
    )


def _candidate_evidence(
    tokens: dict[str, int], *, inject: bool = True
) -> dict[str, dict]:
    """Per token: which training and held-out fixtures it reaches its area on.

    Each token is measured alone (so another candidate never shadows it: the first
    list token to match an identifier wins). Returns, per token, the fixture names
    of ``positives`` (labelled with the token's area), ``no_area`` (training
    fixtures with no area), ``other_area`` (labelled with another area),
    ``heldout_negative`` (held-out fixtures with no area) and
    ``heldout_positive`` (reported only). ``inject=False`` reads the live
    dictionary, for tokens that already shipped.
    """
    sets = (
        ("train", fixtures_mod.FIXTURES),
        ("held", heldout_mod.HELDOUT),
    )
    out = {
        t: {
            "positives": [],
            "no_area": [],
            "other_area": [],
            "heldout_negative": [],
            "heldout_positive": [],
        }
        for t in tokens
    }
    for set_name, fixtures in sets:
        for fx in fixtures:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                haystack = _write(fx, root)
                for token, area in tokens.items():
                    if not _could_match(token, haystack):
                        continue
                    ctx = _view({token: area}) if inject else nullcontext()
                    with ctx:
                        report = run_scan(fx["name"], "HEAD", root, fx["purpose"])
                    if not _token_hit(report, token, area):
                        continue
                    if set_name == "train":
                        if fx["area"] == area:
                            key = "positives"
                        elif fx["area"] is None:
                            key = "no_area"
                        else:
                            key = "other_area"
                    else:
                        if fx["area"] == area:
                            key = "heldout_positive"
                        elif fx["area"] is None:
                            key = "heldout_negative"
                        else:
                            continue
                    out[token][key].append(fx["name"])
    return out


def _admits(row: dict) -> bool:
    return (
        len(row["positives"]) >= 2
        and not row["no_area"]
        and not row["heldout_negative"]
    )


def _pack_sourced(source: str) -> bool:
    return source.startswith("Annex III pack")


def _decision(token: str, row: dict, source: str, shipped: bool) -> str:
    if shipped:
        return "accepted"
    if (token, _AREA_OF[token], source) in _FIXTURE_NAMES:
        return "rejected: one fixture's own name"
    if row["no_area"] or row["heldout_negative"] or row["other_area"]:
        return "rejected: fires on a program of another label"
    if len(row["positives"]) == 1:
        return "rejected: one positive"
    if not row["positives"]:
        return "rejected: no positive"
    return "rejected: admission rule not met"


def _evidence_table(evidence: dict[str, dict], shipped: set[str]) -> str:
    train = fixtures_mod.FIXTURES
    n_area = {a: sum(1 for f in train if f["area"] == a) for a in _AREAS}
    n_none = sum(1 for f in train if f["area"] is None)
    n_held = sum(1 for f in heldout_mod.HELDOUT if f["area"] is None)
    lines = [_HEADER, "|---|---:|---:|---:|---:|---|---|---|---|"]
    for token, area, source in CANDIDATES:
        row = evidence[token]
        is_shipped = token in shipped
        confidence = "low" if is_shipped or not _pack_sourced(source) else "medium"
        lines.append(
            f"| `{token}` | {area} | {len(row['positives'])}/{n_area[area]} "
            f"| {len(row['no_area'])}/{n_none} "
            f"| {len(row['heldout_negative'])}/{n_held} "
            f"| {_decision(token, row, source, is_shipped)} "
            f"| {source} | {confidence} | yes |"
        )
    return "\n".join(lines)


# Default scan path counts per area, (TP, FP, FN), measured at dictionary 1.4.0
# before any token was added. A historical record: never recomputed.
_SCAN_BEFORE = {
    1: (4, 5, 0),
    2: (0, 0, 3),
    3: (0, 0, 4),
    4: (0, 0, 4),
    5: (0, 0, 5),
    6: (0, 0, 3),
    7: (0, 0, 3),
    8: (0, 0, 3),
}


def _before_after_table(measured: dict) -> str:
    """One combined table: recorded 1.4.0 counts next to the live ones.

    Deliberately not the shape of ``bench.format_table``, so the page holds the
    live default-path table exactly once (in the Results section).
    """
    lines = [
        "| Area | Name | Fixtures | TP before | TP after | FP before | FP after "
        "| FN before | FN after | Precision before | Precision after "
        "| Recall before | Recall after |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    rows = [(str(a), lookup_by_area(a)[0].area_name, a) for a in _SCAN_BEFORE]
    rows.append(("Overall", "all areas", None))
    for label, name, area in rows:
        if area is None:
            before = tuple(sum(c[i] for c in _SCAN_BEFORE.values()) for i in range(3))
            after = tuple(measured["scan_overall"][k] for k in ("tp", "fp", "fn"))
            fixtures = sum(
                measured["scan_per_area"][a]["fixtures"] for a in _SCAN_BEFORE
            )
        else:
            before = _SCAN_BEFORE[area]
            cells = measured["scan_per_area"][area]
            after = tuple(cells[k] for k in ("tp", "fp", "fn"))
            fixtures = cells["fixtures"]
        p0, r0 = (
            bench._pct(before[0], before[0] + before[1]),
            bench._pct(before[0], before[0] + before[2]),
        )
        p1, r1 = (
            bench._pct(after[0], after[0] + after[1]),
            bench._pct(after[0], after[0] + after[2]),
        )
        lines.append(
            f"| {label} | {name} | {fixtures} | {before[0]} | {after[0]} "
            f"| {before[1]} | {after[1]} | {before[2]} | {after[2]} "
            f"| {p0} | {p1} | {r0} | {r1} |"
        )
    return "\n".join(lines)


def _table_blocks(page: str) -> list[str]:
    blocks, current = [], []
    for line in [*page.splitlines(), ""]:
        if line.startswith("|"):
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    return blocks


@pytest.fixture(scope="module")
def measured() -> dict:
    return bench.measure()


@pytest.fixture(scope="module")
def evidence() -> dict[str, dict]:
    return _candidate_evidence({t: a for t, a, _ in CANDIDATES})


def _shipped_tokens() -> dict[str, int]:
    area_of_key = {key: area for area, key in _AREA_TO_TAXONOMY.items()}
    return {
        token: area_of_key[key]
        for key, tokens in _shipped().items()
        for token in tokens
    }


def test_every_shipped_token_meets_the_admission_rule(record_property):
    shipped = _shipped_tokens()
    if not shipped:
        record_property("message", "no token shipped: nothing to admit (vacuous)")
        return
    live = _candidate_evidence(shipped, inject=False)
    for token in shipped:
        row = live[token]
        assert len(row["positives"]) >= 2, (token, row)
        assert not row["no_area"], (token, row)
        assert not row["heldout_negative"], (token, row)
        assert not row["other_area"], (token, row)


def test_default_path_floors_hold(measured):
    c = measured["scan_overall"]
    # precision >= 4/9 and recall >= 4/29, compared without division
    assert c["tp"] * 9 >= (c["tp"] + c["fp"]) * 4, c
    assert c["tp"] * 29 >= (c["tp"] + c["fn"]) * 4, c


def test_held_out_numbers_not_worse_than_recorded():
    pins = _load_heldout_pins().HELDOUT_PINNED
    tp0, fp0, fn0 = pins["scan_overall"]
    live = bench.measure_heldout()["scan_overall"]
    # cross-multiplied: live precision >= recorded and live recall >= recorded
    assert live["tp"] * (tp0 + fp0) >= tp0 * (live["tp"] + live["fp"]), live
    assert live["tp"] * (tp0 + fn0) >= tp0 * (live["tp"] + live["fn"]), live


def test_docs_page_records_area_2_to_4_evidence(evidence, measured):
    page = _DOCS_PAGE.read_text(encoding="utf-8")
    blocks = _table_blocks(page)
    # The evidence section compares before and after in one combined table and
    # never repeats the live default-path table, so a corrupted primary table
    # (or a source reverted to 1.4.0) cannot hide behind a second copy.
    assert _before_after_table(measured) in blocks
    assert blocks.count(bench.format_table(measured, "scan")) == 1
    assert any(ln.startswith(_SECTION) for ln in page.splitlines())
    lower = page.lower()
    assert "synthetic" in lower
    assert "single-labelled" in lower
    shipped = set(_shipped_tokens())
    table = _evidence_table(evidence, shipped)
    assert table in _table_blocks(page)
    assert len(table.splitlines()) == len(CANDIDATES) + 2
    for line in table.splitlines()[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        assert cells[-2] in {"medium", "low"}, line
        assert cells[-1] == "yes", line
