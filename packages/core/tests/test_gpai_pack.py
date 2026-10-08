"""GPAI provider pack (SU-135a): gated Annex XI/XII artifact probes and template."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core import recommend_engine
from opencomplai_core.compliance_checker.catalog import load_obligations
from opencomplai_core.gap_probes import _PROBE_PATTERNS, run_artifact_probe
from opencomplai_core.gap_report import build_gap_report, load_gap_article_map
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    CheckerSessionRef,
    GapReport,
    GapStatus,
    SystemManifest,
)
from opencomplai_core.recommend_engine import load_template_map, render_recommendations

TEMPLATE_DIR = Path(recommend_engine.__file__).parent / "templates" / "recommend"
MODEL_DOC = "gpai_model_documentation"
DOWNSTREAM = "gpai_downstream_information"
SYSTEMIC = "gpai_systemic_risk_evaluation"


def _report(tmp_path: Path, *obligation_ids: str, session: bool = True):
    ref = (
        CheckerSessionRef(
            checker_version="t",
            session_id="s",
            completed_at="2026-01-01T00:00:00Z",
            obligation_ids=list(obligation_ids),
        )
        if session
        else None
    )
    manifest = SystemManifest(
        system_id="s",
        intended_purpose="general-purpose model",
        compliance_target="EU_AI_ACT",
        commit_ref="HEAD",
        operator_role="provider",
        checker_session=ref,
    )
    report = build_gap_report(
        "s", "HEAD", repo_root=tmp_path, manifest=manifest, checker_session=ref
    )
    return {row.article: row for row in report.articles}


def _touch(tmp_path: Path, *names: str) -> None:
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# draft\n", encoding="utf-8")


def test_gpai_session_gets_artifact_sources_for_art_53_and_55(tmp_path):
    rows = _report(tmp_path, "gpai_provider", "gpai_systemic_risk")
    assert rows["Art. 53"].status is GapStatus.MISSING
    assert rows["Art. 53"].source is ArticleGapSource.ARTIFACT
    assert rows["Art. 53"].evidence_ref == MODEL_DOC
    assert rows["Art. 55"].status is GapStatus.MISSING
    assert rows["Art. 55"].source is ArticleGapSource.ARTIFACT
    assert rows["Art. 55"].evidence_ref == SYSTEMIC


def test_no_session_gpai_rows_unchanged(tmp_path):
    rows = _report(tmp_path, session=False)
    for article in ("Art. 53", "Art. 55"):
        assert rows[article].status is GapStatus.UNVERIFIED
        assert rows[article].source is ArticleGapSource.OBLIGATION


def test_non_gpai_session_has_no_gpai_artifact_rows(tmp_path):
    rows = _report(tmp_path, "deployer_general", "ai_literacy")
    # applies_when_any (SU-14a) moves both articles to not_applicable; either
    # way no GPAI artifact row may appear.
    for article in ("Art. 53", "Art. 55"):
        assert (
            article not in rows or rows[article].source is ArticleGapSource.OBLIGATION
        )


def test_systemic_gate_is_independent(tmp_path):
    rows = _report(tmp_path, "gpai_provider")
    assert rows["Art. 53"].status is GapStatus.MISSING
    assert rows["Art. 53"].source is ArticleGapSource.ARTIFACT
    assert (
        "Art. 55" not in rows or rows["Art. 55"].source is ArticleGapSource.OBLIGATION
    )


def test_annex_files_make_rows_partial_never_met(tmp_path):
    _touch(
        tmp_path,
        "docs/gpai/model-documentation.md",
        "docs/gpai/downstream-information.md",
        "docs/gpai/systemic-risk.md",
    )
    rows = _report(tmp_path, "gpai_provider", "gpai_systemic_risk")
    assert rows["Art. 53"].status is GapStatus.PARTIAL
    assert rows["Art. 55"].status is GapStatus.PARTIAL


def test_downstream_file_does_not_satisfy_model_documentation_probe(tmp_path):
    _touch(tmp_path, "docs/gpai/downstream-information.md")
    assert run_artifact_probe(MODEL_DOC, tmp_path).found_paths == []
    assert run_artifact_probe(DOWNSTREAM, tmp_path).found_paths


def _gated_sources():
    for article, config in load_gap_article_map().items():
        for source in config["sources"]:
            if "when_obligation_any" in source:
                yield article, source


def test_gated_sources_reference_known_probes_and_obligations():
    gated = list(_gated_sources())
    assert {s["ref"] for _, s in gated} == {MODEL_DOC, DOWNSTREAM, SYSTEMIC}
    known = set(load_obligations())
    for _, source in gated:
        assert source["kind"] == "artifact"
        assert source["ref"] in _PROBE_PATTERNS
        assert set(source["when_obligation_any"]) <= known


def _assert_flagged(entry: dict) -> None:
    assert isinstance(entry["source"], str)
    assert entry["source"]
    assert entry["confidence"] == "low"
    assert entry["needs_founder_review"] is True


def test_gpai_entries_are_flagged_for_review():
    article_map = load_gap_article_map()
    template_map = load_template_map()
    for article in ("Art. 53", "Art. 55"):
        _assert_flagged(article_map[article]["pack_note"])
        _assert_flagged(template_map[article])


def test_template_map_points_art_53_and_55_at_the_annex_template():
    template_map = load_template_map()
    for article in ("Art. 53", "Art. 55"):
        entry = template_map[article]
        assert entry["template_id"] == "gpai_annex_documentation"
        assert (TEMPLATE_DIR / entry["file"]).is_file()
    assert not (TEMPLATE_DIR / "gpai_obligation_stub.md").exists()


def test_recommend_renders_annex_template_for_missing_gpai_rows(tmp_path):
    rows = [
        ArticleGapStatus(
            article=article,
            status=GapStatus.MISSING,
            source=ArticleGapSource.ARTIFACT,
            evidence_ref=ref,
            rationale="no file found",
        )
        for article, ref in (("Art. 53", MODEL_DOC), ("Art. 55", SYSTEMIC))
    ]
    report = GapReport(
        system_id="s",
        commit_ref="HEAD",
        generated_at="2026-01-01T00:00:00Z",
        articles=rows,
    )
    written = {p.name: p for p in render_recommendations(report, tmp_path)}
    assert {
        "art53-gpai_annex_documentation.md",
        "art55-gpai_annex_documentation.md",
    } <= set(written)
    for name, path in written.items():
        if not name.endswith("gpai_annex_documentation.md"):
            continue
        text = path.read_text(encoding="utf-8")
        for needle in (
            "Annex XI",
            "Annex XII",
            "not legal advice",
            "docs/gpai/model-documentation.md",
            "docs/gpai/downstream-information.md",
            "docs/gpai/systemic-risk.md",
        ):
            assert needle in text
        assert "{{" not in text
