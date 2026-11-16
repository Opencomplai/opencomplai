"""Tests for the Art. 9/Art. 17 GAP-PROBES split: content-aware Art. 9 probe,
and Art. 17 (QMS) carved out of the Art. 16 provider-obligations probe.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core.control_catalog import get_catalog
from opencomplai_core.gap_probes import SCAFFOLD_PLACEHOLDER, artifact_gap_status
from opencomplai_core.gap_report import build_gap_report, load_gap_article_map
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
)
from opencomplai_core.recommend_engine import load_template_map, render_recommendations


def test_empty_risk_register_is_partial_not_met(tmp_path: Path):
    (tmp_path / "risk_register.json").write_text("{}", encoding="utf-8")
    row = artifact_gap_status("risk_register", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.35
    assert "lacks risk-identification and mitigation content markers" in row.rationale


def test_risk_register_with_content_markers_is_higher_confidence_partial(
    tmp_path: Path,
):
    (tmp_path / "risk_register.json").write_text(
        '{"entries": [{"note": "risk identification: hazard of biased output.'
        ' mitigation: control measure applied before release."}]}',
        encoding="utf-8",
    )
    row = artifact_gap_status("risk_register", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.6
    assert "content markers found" in row.rationale


def test_art17_split_from_art16(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "qms.md").write_text("Our quality management system.", encoding="utf-8")

    load_gap_article_map.cache_clear()
    report = build_gap_report("sys", "HEAD", repo_root=tmp_path)

    art17 = next(r for r in report.articles if r.article == "Art. 17")
    assert art17.status == GapStatus.PARTIAL
    assert "qms.md" in art17.evidence_ref

    art16 = next(r for r in report.articles if r.article == "Art. 16")
    assert art16.status == GapStatus.MISSING
    assert "qms.md" not in art16.evidence_ref


def test_art17_present_in_gap_article_map():
    load_gap_article_map.cache_clear()
    article_map = load_gap_article_map()
    assert "Art. 17" in article_map
    sources = article_map["Art. 17"]["sources"]
    assert sources == [{"kind": "artifact", "ref": "provider_qms"}]


def test_art17_template_mapping_renders(tmp_path: Path):
    template_map = load_template_map()
    assert template_map["Art. 17"]["template_id"] == "qms_outline"

    report = GapReport(
        system_id="test-sys",
        commit_ref="HEAD",
        generated_at="2026-08-17T00:00:00Z",
        articles=[
            ArticleGapStatus(
                article="Art. 17",
                status=GapStatus.MISSING,
                source=ArticleGapSource.ARTIFACT,
                evidence_ref="provider_qms",
                rationale="no QMS artifact found",
            )
        ],
    )
    written = render_recommendations(report, tmp_path)
    assert len(written) == 1
    assert written[0].exists()
    content = written[0].read_text(encoding="utf-8")
    assert "Art. 17" in content
    assert "Quality Management System" in content


def test_catalog_covers_art17():
    catalog = get_catalog()
    assert "Art. 17" in catalog


_SCAFFOLD_EXAMPLES = {
    "risk_register": (
        "docs/isms/risk-treatment-plan.md",
        "Risk assessment: identified risks and hazard list.\n"
        "Treatment: mitigation and control measure per risk.\n",
    ),
    "deployer_instructions": (
        "docs/instructions.md",
        "Intended purpose of the system.\nHuman oversight and known limitation.\n",
    ),
    "technical_documentation_dossier": (
        "dossier_abc.json",
        '{"dossier_id": "abc", "bundle_checksum": "sha256:00"}\n',
    ),
    "serious_incident_log": (
        "incident-log.json",
        '{"prev_hash": "sha256:00", "event": "example"}\n',
    ),
}


@pytest.mark.parametrize("ref", sorted(_SCAFFOLD_EXAMPLES))
def test_eu_artifact_probe_found_when_filled(tmp_path: Path, ref: str):
    rel, text = _SCAFFOLD_EXAMPLES[ref]
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)


@pytest.mark.parametrize("ref", sorted(_SCAFFOLD_EXAMPLES))
def test_eu_artifact_probe_unfilled_scaffold_reads_035(tmp_path: Path, ref: str):
    rel, text = _SCAFFOLD_EXAMPLES[ref]
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text + "\n" + SCAFFOLD_PLACEHOLDER + "\n", encoding="utf-8")
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.35)
