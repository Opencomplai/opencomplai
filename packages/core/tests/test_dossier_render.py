"""Annex IV dossier Markdown/PDF rendering (presentation only)."""

from __future__ import annotations

import os
import re
import sys
import zlib
from pathlib import Path

import pytest
from opencomplai_core.dossier import (
    PROVIDER_SUPPLIED_PLACEHOLDER,
    AnnexIVDossier,
    AnnexIVSection1,
    AnnexIVSection2,
    AnnexIVSection3,
    AnnexIVSection4,
    AnnexIVSection5,
    AnnexIVSection6,
    AnnexIVSection7,
    AnnexIVSection8,
    AnnexIVSection9,
    ArticleTwelveRecordKeeping,
)
from opencomplai_core.dossier_generator import STUB_TEXT
from opencomplai_core.dossier_render import (
    INCOMPLETE_BANNER,
    render_markdown,
    render_pdf,
    write_renders,
)

GOLDEN = Path(__file__).parent / "fixtures" / "dossier_render" / "high_incomplete.md"
UPDATE = os.environ.get("OPENCOMPLAI_UPDATE_GOLDEN") == "1"


def _dossier(*, attested: bool = False, complete: bool = False) -> AnnexIVDossier:
    """A fixed dossier built from literals (fixed id and timestamp)."""
    s2 = STUB_TEXT if not complete else "Described in the model card."
    return AnnexIVDossier(
        dossier_id="00000000-0000-4000-8000-000000000129",
        system_id="credit-scorer",
        commit_ref="abc1234",
        generated_at="2026-01-02T03:04:05+00:00",
        section1=AnnexIVSection1(
            system_name="credit-scorer",
            system_version="1.0.0",
            provider_name="Example Provider",
            intended_purpose="credit scoring for loan applications",
            compliance_target="EU_AI_ACT",
            risk_class="high",
            deployment_context="production",
        ),
        section2=AnnexIVSection2(
            training_data_description=s2,
            model_architecture=s2,
            performance_metrics={"f1": 0.9, "auc": 0.95},
            known_limitations=["Thin-file applicants"],
        ),
        section3=AnnexIVSection3(
            human_oversight_measures=["Manual review of declines"],
            provider_supplied=attested,
        ),
        section4=AnnexIVSection4(provider_supplied=attested),
        section5=AnnexIVSection5(
            risk_assessment_id="ra-1",
            risk_level="high",
            rules_evaluated=3,
            rules_passed=2,
            rules_failed=1,
            failed_rule_ids=["EU_AIA_ART6_HIGH_RISK"],
            rationale_hash="sha256:" + "a" * 64,
        ),
        section6=AnnexIVSection6(provider_supplied=attested),
        section7=AnnexIVSection7(provider_supplied=attested),
        section8=AnnexIVSection8(provider_supplied=attested),
        section9=AnnexIVSection9(provider_supplied=attested),
        record_keeping=ArticleTwelveRecordKeeping(logging_enabled=True),
        evidence_hashes=["sha256:" + "b" * 64],
        bundle_checksum="c" * 64,
        section2_complete=complete,
        annex_iv_complete=complete,
    )


def test_markdown_matches_golden() -> None:
    text = render_markdown(_dossier(), schema_valid=False)
    if UPDATE:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_bytes(text.encode("utf-8"))
        return
    assert GOLDEN.is_file(), "missing golden; run with OPENCOMPLAI_UPDATE_GOLDEN=1"
    assert text == GOLDEN.read_bytes().decode("utf-8")


def test_placeholders_and_missing_marked_not_provided() -> None:
    # Section 6 is attested yet still carries the placeholder text: it must be
    # marked from the value itself, not only from the provider_supplied flag.
    dossier = _dossier(attested=True, complete=True)
    dossier.section6.note = PROVIDER_SUPPLIED_PLACEHOLDER
    dossier.section2.model_architecture = STUB_TEXT
    dossier.record_keeping = None
    text = render_markdown(dossier, schema_valid=True)
    assert "- note: **NOT PROVIDED**" in text
    assert f"_placeholder text: {PROVIDER_SUPPLIED_PLACEHOLDER}_" in text
    assert "- model_architecture: **NOT PROVIDED**" in text
    assert f"_placeholder text: {STUB_TEXT}_" in text
    assert "- change_log_reference: **NOT PROVIDED**" in text  # None
    assert "- changes: **NOT PROVIDED**" in text  # empty list
    assert "## Article 12 record keeping\n\nNOT PROVIDED" in text


def test_complete_dossier_has_no_incomplete_banner() -> None:
    text = render_markdown(_dossier(attested=True, complete=True), schema_valid=True)
    assert "INCOMPLETE" not in text
    assert "No completeness gap flagged by the dossier" in text
    assert "NOT PROVIDED below" not in text


def test_incomplete_banner_lists_reasons() -> None:
    text = render_markdown(_dossier(), schema_valid=False)
    assert text.split("\n")[2] == f"**{INCOMPLETE_BANNER}**"
    assert "- Schema validation failed." in text
    assert "- Section 2 is a stub." in text
    assert "- Section 9 is not provided by the provider." in text


def test_non_attested_sections_not_called_attested() -> None:
    dossier = _dossier(complete=True)  # flags True, provider_supplied False
    text = render_markdown(dossier, schema_valid=True)
    assert "INCOMPLETE" not in text
    assert (
        "Sections not attested by the provider are marked NOT PROVIDED below." in text
    )
    # The only use of the word is that single line; nothing claims attestation.
    assert len(re.findall(r"attested", text)) == 1
    assert "- provider_supplied: No" in text
    assert "- monitoring_approach: **NOT PROVIDED**" in text


def test_render_is_deterministic() -> None:
    assert render_markdown(_dossier(), schema_valid=False) == render_markdown(
        _dossier(), schema_valid=False
    )


def _decoded_pdf_text(pdf_bytes: bytes) -> str:
    chunks: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.DOTALL):
        try:
            chunks.append(
                zlib.decompress(match.group(1)).decode("latin-1", errors="ignore")
            )
        except zlib.error:
            chunks.append(match.group(1).decode("latin-1", errors="ignore"))
    return "\n".join(chunks)


def test_pdf_contains_incomplete_marker() -> None:
    pytest.importorskip("fpdf")
    pdf = render_pdf(_dossier(), schema_valid=False)
    assert pdf.startswith(b"%PDF")
    text = _decoded_pdf_text(pdf)
    assert "INCOMPLETE" in text
    assert "NOT PROVIDED" in text


def test_pdf_missing_fpdf_raises_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "fpdf", None)
    with pytest.raises(ImportError, match="fpdf2"):
        render_pdf(_dossier(), schema_valid=False)


def test_write_renders_writes_md_before_pdf_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "fpdf", None)
    with pytest.raises(ImportError):
        write_renders(_dossier(), tmp_path, ["md", "pdf"], schema_valid=False)
    assert (tmp_path / "dossier_00000000-0000-4000-8000-000000000129.md").is_file()
