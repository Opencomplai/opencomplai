"""Default-path tokens for Annex III areas 5 to 8: evidence, register, floors.

The default scan path (``run_scan`` without intent analysis) reaches no area 5 to
8 through a specific token today. The admission rule for areas 2 to 4 is applied to
the four taxonomy keys ``essential_services``, ``law_enforcement``, ``migration``
and ``justice``. The candidate forms are the multi-word phrases the knowledge
pack lists for those keys, written as one identifier (``credit score`` becomes
``credit_score``). A form ships only if all of these hold:

* at least 2 distinct positive training fixtures of its own area,
* 0 hits on every training fixture with no area and on every held-out negative,
* it maps to exactly one area and matches no Art. 5 signal,
* default precision stays at or above 4/9 and recall at or above 4/29.

``REGISTER`` is the complete list of tokens added for these areas; an empty
register is the legal "no token added" result. Positives are counted on the 46
training fixtures only. The held-out set is used for the zero-hit negative check
and is reported, never used to choose a token. The measurements and decisions are
recorded in docs/src/concepts/annex-iii-benchmark.md; this file recomputes them.
"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from opencomplai_core.models import SignalCategory
from opencomplai_core.rules import (
    ANNEX_III_CATEGORIES,
    match_annex_iii_categories,
    match_prohibited_signals,
    normalize_text,
)
from opencomplai_core.scan_engine import run_scan
from opencomplai_core.scanner import mapping
from opencomplai_core.scanner.detectors._signals import (
    load_signals,
    match_token_identifier,
)
from opencomplai_core.scanner.mapping import (
    _AREA_TO_TAXONOMY,
    signal_category_to_taxonomy,
)

_TESTS_DIR = Path(__file__).parent
_REPO = Path(__file__).resolve().parents[3]
_DOCS_PAGE = _REPO / "docs" / "src" / "concepts" / "annex-iii-benchmark.md"
_SECTION = "## Default-path dictionary, areas 5 to 8"
_EVIDENCE_HEADER = (
    "| Area | Forms considered | With fixture hits | Positives | No-area hits "
    "| Decision |"
)
_AREAS = (5, 6, 7, 8)
_KEY_OF_AREA = {area: _AREA_TO_TAXONOMY[area] for area in _AREAS}
_AREA_OF_KEY = {key: area for area, key in _KEY_OF_AREA.items()}
_KEYS = tuple(_KEY_OF_AREA.values())
# The ``area_signals`` keys the shipped mapping accepts, plus the four keys under
# evaluation: a candidate is measured through the real mapping lookup.
_EVAL_KEYS = (*mapping._AREA_SIGNAL_KEYS, *_KEYS)

# Every dictionary token that yielded a key of areas 5 to 8 before this epic: the
# category map sends each ``vector_embedding`` token (EMBEDDINGS_VECTOR) and each
# ``pii_hints`` token (PII_DATAFLOW) to essential_services whatever the token.
# Snapshotted at dictionary 1.5.0 before any edit; never recomputed.
LEGACY_AREA_TOKENS: frozenset[str] = frozenset(
    {
        "voyageai",
        "jina",
        "embedding",
        "rerank",
        "similarity_search",
        "email",
        "ssn",
        "passport",
        "patient_id",
        "phi",
        "pii",
        "biometric_id",
    }
)

# Demoted to ml_frameworks (still AI usage, no area) by the generic embedding
# token review: present in LEGACY_AREA_TOKENS, absent from the live set.
DEMOTED_BY_A4B: frozenset[str] = frozenset(
    {"voyageai", "jina", "embedding", "rerank", "similarity_search"}
)

# token -> {category, area_key, phrase, sources, confidence,
#           needs_founder_review, positives}. No form met the admission rule on
# the 46 training programs and the 24 held-out programs, so nothing was added.
REGISTER: dict[str, dict] = {}

# Default scan path counts, recorded at dictionary 1.5.0 at the start of this
# epic. A historical record: never recomputed.
_BEFORE_BLOCK = """Default scan path
| Area | Name | Fixtures | TP | FP | FN | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | biometrics | 4 | 4 | 5 | 0 | 44.4% | 100.0% |
| 2 | critical_infrastructure | 3 | 2 | 0 | 1 | 100.0% | 66.7% |
| 3 | education | 4 | 0 | 0 | 4 | n/a | 0.0% |
| 4 | employment | 4 | 0 | 0 | 4 | n/a | 0.0% |
| 5 | essential_services | 5 | 0 | 0 | 5 | n/a | 0.0% |
| 6 | law_enforcement | 3 | 0 | 0 | 3 | n/a | 0.0% |
| 7 | migration | 3 | 0 | 0 | 3 | n/a | 0.0% |
| 8 | justice_democracy | 3 | 0 | 0 | 3 | n/a | 0.0% |
| Overall | all areas | 29 | 6 | 5 | 23 | 54.5% | 20.7% |

scan_none_clean: 14 of 17"""


def _load(path: Path, tag: str):
    spec = importlib.util.spec_from_file_location(f"default_path_5_to_8_{tag}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The area 2 to 4 evidence helper, loaded by path (not copied).
_b2b = _load(_TESTS_DIR / "test_default_path_area_tokens.py", "b2b")
bench = _b2b.bench
fixtures_mod = _b2b.fixtures_mod
heldout_mod = _b2b.heldout_mod


def _candidate_forms() -> list[tuple[str, str, str]]:
    """(spaced phrase, token, taxonomy key) for every usable multi-word phrase.

    The underscore token itself never equals the pack phrase in the rule matcher,
    so the checks run on the spaced phrase.
    """
    seen: set[str] = set()
    forms: list[tuple[str, str, str]] = []
    for key in _KEYS:
        for raw in sorted(ANNEX_III_CATEGORIES[key]):
            phrase = normalize_text(raw)
            if " " not in phrase or phrase in seen:
                continue
            if match_annex_iii_categories(phrase).categories != [key]:
                continue
            if match_prohibited_signals(phrase):
                continue
            seen.add(phrase)
            forms.append((phrase, phrase.replace(" ", "_"), key))
    return forms


FORMS = _candidate_forms()


def _evidence(tokens: dict[str, int]) -> dict[str, dict]:
    """B2b's per-token fixture evidence, with the four keys accepted by the map."""
    with mock.patch.object(mapping, "_AREA_SIGNAL_KEYS", _EVAL_KEYS):
        return _b2b._candidate_evidence(tokens)


def _admits(row: dict) -> bool:
    return (
        len(row["positives"]) >= 2
        and not row["no_area"]
        and not row["heldout_negative"]
        and not row["other_area"]
    )


def _hits(row: dict) -> int:
    return len(row["positives"]) + len(row["no_area"]) + len(row["other_area"])


def _area_table(evidence: dict[str, dict]) -> str:
    n_none = sum(1 for f in fixtures_mod.FIXTURES if f["area"] is None)
    n_held = sum(1 for f in heldout_mod.HELDOUT if f["area"] is None)
    lines = [_EVIDENCE_HEADER, "|---:|---:|---:|---:|---:|---|"]
    for area in _AREAS:
        key = _KEY_OF_AREA[area]
        forms = [t for _, t, k in FORMS if k == key]
        rows = [evidence[t] for t in forms]
        positives = {n for r in rows for n in r["positives"]}
        none_hits = {n for r in rows for n in r["no_area"]} | {
            n for r in rows for n in r["heldout_negative"]
        }
        n_area = sum(1 for f in fixtures_mod.FIXTURES if f["area"] == area)
        added = sorted(t for t in REGISTER if REGISTER[t]["area_key"] == key)
        decision = (
            "added: " + ", ".join(f"`{t}`" for t in added)
            if added
            else "no token added"
        )
        lines.append(
            f"| {area} | {len(forms)} | {sum(1 for r in rows if _hits(r))} "
            f"| {len(positives)}/{n_area} | {len(none_hits)}/{n_none + n_held} "
            f"| {decision} |"
        )
    return "\n".join(lines)


def _live_after_block(measured: dict) -> str:
    n_none = sum(1 for f in fixtures_mod.FIXTURES if f["area"] is None)
    return (
        "Default scan path\n"
        + bench.format_table(measured, "scan")
        + f"\n\nscan_none_clean: {measured['scan_none_clean']} of {n_none}"
    )


def _fenced_in_tab(text: str) -> str:
    """The block as the docs page writes it: a fence indented inside a tab."""
    body = "\n".join(f"    {ln}" if ln else "" for ln in text.splitlines())
    return f"    ```text\n{body}\n    ```"


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
    return _evidence({t: _AREA_OF_KEY[k] for _, t, k in FORMS})


def _live_area_tokens() -> set[str]:
    """Every dictionary token that yields a key of areas 5 to 8."""
    sig = load_signals()
    keys = set(_KEYS)
    live: set[str] = set()
    for lst, category in (
        ("vector_embedding", SignalCategory.EMBEDDINGS_VECTOR),
        ("pii_hints", SignalCategory.PII_DATAFLOW),
        ("scoring", SignalCategory.SCORING_PROFILING),
        ("biometric", SignalCategory.BIOMETRIC),
    ):
        for token in sig.get(lst, []):
            if keys & set(signal_category_to_taxonomy(category, token)):
                live.add(token)
    for key in _KEYS:
        live.update(sig.get("area_signals", {}).get(key, []))
    return live


@pytest.mark.parametrize("token", sorted(REGISTER))
def test_register_tokens_meet_admission_rule(token: str):
    entry = REGISTER[token]
    key = entry["area_key"]
    assert key in _KEYS, key
    phrase = entry["phrase"]
    assert phrase.replace(" ", "_") == token
    assert match_annex_iii_categories(phrase).categories == [key], phrase
    assert match_prohibited_signals(phrase) == [], phrase
    assert entry["confidence"] == "medium"
    assert entry["needs_founder_review"] is True
    row = _evidence({token: _AREA_OF_KEY[key]})[token]
    assert not row["no_area"], (token, row)
    assert not row["heldout_negative"], (token, row)
    assert not row["other_area"], (token, row)
    assert len(row["positives"]) >= 2, (token, row)
    assert sorted(row["positives"]) == sorted(entry["positives"]), (token, row)
    assert token in load_signals()["area_signals"][key]


def test_dictionary_area_tokens_equal_legacy_plus_register():
    expected = (set(LEGACY_AREA_TOKENS) - DEMOTED_BY_A4B) | set(REGISTER)
    assert _live_area_tokens() == expected


def test_demoted_tokens_were_legacy_and_are_no_longer_area_tokens():
    assert DEMOTED_BY_A4B <= LEGACY_AREA_TOKENS
    assert not (DEMOTED_BY_A4B & _live_area_tokens())


def test_no_unregistered_form_meets_the_admission_rule(evidence):
    """The register is complete: no other measured form would have been admitted."""
    assert FORMS, "no candidate form was built from the knowledge pack"
    for _, token, key in FORMS:
        if token in REGISTER:
            continue
        assert not _admits(evidence[token]), (token, key, evidence[token])


def test_default_path_floors_hold(measured):
    c = measured["scan_overall"]
    # precision >= 4/9 and recall >= 4/29, compared without division
    assert c["tp"] * 9 >= (c["tp"] + c["fp"]) * 4, c
    assert c["tp"] * 29 >= (c["tp"] + c["fn"]) * 4, c


@pytest.mark.parametrize(
    "package",
    ["pinecone", "weaviate", "qdrant", "chromadb", "milvus", "lancedb"],
)
def test_removed_vector_store_sdks_stay_unmapped(package: str):
    assert match_token_identifier(package, "vector_embedding") is None
    assert all(package not in t for t in load_signals()["area_signals"].values())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "app.py").write_text(f"import {package}\n", encoding="utf-8")
        report = run_scan("vector-store", "HEAD", root, "an unrelated purpose")
    assert report.evidence, "the import produced no evidence at all"
    for item in report.evidence:
        mapped = signal_category_to_taxonomy(item.category, item.token_label)
        assert "essential_services" not in mapped, (package, item.token_label)
    assert "essential_services" not in report.detected_categories


def test_docs_page_has_before_after_and_area_evidence(evidence, measured):
    page = _DOCS_PAGE.read_text(encoding="utf-8")
    assert any(ln.startswith(_SECTION) for ln in page.splitlines())
    lower = " ".join(page.lower().split())
    assert "synthetic" in lower
    assert "single-labelled" in lower
    assert "no legal review" in lower
    # Before and after, as the runner prints them (default scan path section).
    assert _fenced_in_tab(_BEFORE_BLOCK) in page
    assert _fenced_in_tab(_live_after_block(measured)) in page
    # One evidence row per area 5 to 8, as a whole table block.
    table = _area_table(evidence)
    assert table in _table_blocks(page)
    assert len(table.splitlines()) == len(_AREAS) + 2
    # One signal-change row per admitted token, none when the register is empty.
    for token in REGISTER:
        rows = [ln for ln in page.splitlines() if ln.startswith(f"| `{token}` |")]
        assert rows, token
        assert rows[-1].endswith("| medium | yes |"), rows[-1]
