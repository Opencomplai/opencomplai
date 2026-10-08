"""E-15 guard (SU-G5i): every new gap-map ref carries a provenance record."""

from __future__ import annotations

from opencomplai_core import agent_sources, gap_probes, manifest_sources
from opencomplai_core.control_catalog import ControlCatalogEntry, get_catalog
from opencomplai_core.dossier_generator import RECORD_KEEPING_REVIEW_NOTE
from opencomplai_core.gap_probes import PROBE_PROVENANCE, STUB_SOURCE_REFS
from opencomplai_core.gap_report import load_gap_article_map

# On main before this round; their records are a separate wording task.
LEGACY_REFS = frozenset(
    {
        "risk_register",
        "human_oversight_construct",
        "provider_qms_bundle",
        "provider_qms",
        "provider_fria",
        "distributor_conformity",
        "conformity_assessment_docs",
        "EVAL_BIAS_FAIRNESS_V1",
        "EVAL_SAFETY_LEXICAL_V1",
        "EVAL_DATA_LEAKAGE_V1",
    }
)
GUARDED_KINDS = ("artifact", "manifest", "evaluator")
NAMED_REFS = (
    ("manifest", "record_keeping_declaration"),
    ("evaluator", "EVAL_ADVERSARIAL_V1"),
    ("artifact", "gpai_model_documentation"),
    ("artifact", "gpai_downstream_information"),
    ("artifact", "gpai_systemic_risk_evaluation"),
)


def _record(kind: str, ref: str) -> dict:
    if kind == "manifest":
        notes = {
            **agent_sources.NEEDS_REVIEW_NOTES,
            **manifest_sources.NEEDS_REVIEW_NOTES,
        }
        return notes.get(ref, {})
    return gap_probes.PROBE_PROVENANCE.get(ref, {})


def _ok(rec: dict) -> bool:
    source = str(rec.get("source") or "")
    if not source.strip() or rec.get("needs_founder_review") is not True:
        return False
    if rec.get("confidence") not in {"low", "medium"}:
        return False
    low_only = "heuristic" in source.lower() or "file-name convention" in source.lower()
    return rec["confidence"] == "low" or not low_only


def refs_without_provenance(article_map: dict) -> list[tuple[str, str]]:
    bad = []
    for row in article_map.values():
        for src in row.get("sources", []):
            kind, ref = src["kind"], src["ref"]
            if kind not in GUARDED_KINDS or ref in LEGACY_REFS:
                continue
            if ref in STUB_SOURCE_REFS.get(kind, frozenset()):
                continue
            if not _ok(_record(kind, ref)) and (kind, ref) not in bad:
                bad.append((kind, ref))
    return bad


def _overstated(article_map: dict) -> list[str]:
    out = []
    for article, row in article_map.items():
        note = str(row.get("note") or "").lower()
        if (
            row.get("needs_founder_review") is True
            and ("placeholder" in note or "heuristic" in note)
            and row.get("confidence") != "low"
        ):
            out.append(article)
    return out


def test_every_new_gap_ref_has_provenance():
    assert refs_without_provenance(load_gap_article_map()) == []


def test_named_refs_resolve_to_low_flagged_records():
    present = {
        (s["kind"], s["ref"])
        for row in load_gap_article_map().values()
        for s in row.get("sources", [])
    }
    for kind, ref in NAMED_REFS:
        assert (kind, ref) in present, ref
        rec = _record(kind, ref)
        assert rec.get("confidence") == "low", ref
        assert rec.get("needs_founder_review") is True, ref


def test_walker_flags_a_ref_without_provenance(monkeypatch):
    synthetic = {
        "Art. X": {
            "sources": [
                {"kind": "artifact", "ref": "zz_new_artifact"},
                {"kind": "evaluator", "ref": "EVAL_ZZ_NEW"},
                {"kind": "manifest", "ref": "zz_new_declaration"},
            ]
        }
    }
    assert len(refs_without_provenance(synthetic)) == 3
    monkeypatch.setitem(
        PROBE_PROVENANCE,
        "zz_new_artifact",
        {
            "source": "heuristic probe",
            "confidence": "medium",
            "needs_founder_review": True,
        },
    )
    assert ("artifact", "zz_new_artifact") in refs_without_provenance(synthetic)


def test_record_keeping_record_matches_dossier_note():
    rec = _record("manifest", "record_keeping_declaration")
    for key in ("source", "confidence", "needs_founder_review"):
        assert rec[key] == RECORD_KEEPING_REVIEW_NOTE[key], key


def test_placeholder_or_heuristic_rows_are_low_confidence():
    article_map = load_gap_article_map()
    assert _overstated(article_map) == []
    for article in ("Art. 26", "Art. 49", "Art. 72", "Art. 73"):
        assert article_map[article]["confidence"] == "low", article


def test_row_notes_name_their_artifact_probes():
    noted = {a: r for a, r in load_gap_article_map().items() if r.get("note")}
    assert noted
    for article, row in noted.items():
        note = row["note"]
        assert "without evidence" not in note.lower(), article
        for src in row.get("sources", []):
            if src["kind"] == "artifact":
                assert src["ref"] in note, (article, src["ref"])


def test_overstated_row_guard_flags_a_medium_row():
    rows = {
        "Art. A": {
            "needs_founder_review": True,
            "note": "Placeholder sources",
            "confidence": "medium",
        },
        "Art. B": {
            "needs_founder_review": True,
            "note": "heuristic, capped",
            "confidence": "low",
        },
    }
    assert _overstated(rows) == ["Art. A"]


# The 21 article rows on main at the round base; later rows must carry provenance.
BASE_CATALOG_ROWS = frozenset(
    f"Art. {n}"
    for n in (
        4,
        5,
        6,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        24,
        25,
        27,
        43,
        47,
        48,
        50,
        53,
        55,
    )
)


def catalog_rows_without_provenance(catalog) -> list[str]:
    return sorted(
        key
        for key, row in catalog.items()
        if key not in BASE_CATALOG_ROWS
        and (
            not (row.source or "").strip()
            or row.needs_founder_review is not True
            or row.confidence not in ("low", "medium")
        )
    )


def test_new_catalog_rows_carry_provenance():
    assert catalog_rows_without_provenance(get_catalog()) == []


def test_placeholder_ttl_rows_are_low_and_flagged():
    catalog = get_catalog()
    for article in ("Art. 26", "Art. 49", "Art. 72", "Art. 73"):
        row = catalog[article]
        assert (row.source or "").strip(), article
        assert row.confidence == "low", article
        assert row.needs_founder_review is True, article


def test_catalog_guard_flags_rows_without_provenance():
    full = {"source": "s", "confidence": "low", "needs_founder_review": True}
    catalog = {
        "bare": ControlCatalogEntry("t", 1),
        "high": ControlCatalogEntry("t", 1, **{**full, "confidence": "high"}),
        "unflagged": ControlCatalogEntry(
            "t", 1, **{**full, "needs_founder_review": False}
        ),
        "ok": ControlCatalogEntry("t", 1, **{**full, "confidence": "medium"}),
        "Art. 4": ControlCatalogEntry("t", 1),
    }
    assert catalog_rows_without_provenance(catalog) == ["bare", "high", "unflagged"]
