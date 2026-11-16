"""The full HTML section of a non-EU pack: evidence, sources, scope, timeline."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from opencomplai_core import pack_registry, regulatory_timeline
from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack
from opencomplai_core.models import (
    DISCLAIMER_V2,
    ArticleGapSource,
    ArticleGapStatus,
    FrameworkReport,
    GapReport,
    GapStatus,
)
from opencomplai_core.report_engine import render_framework_section

KEY = "TST"
ROWS = {
    f"{KEY}:R1": {
        "title": "Risk register",
        "sources": [
            {"kind": "artifact", "ref": "risk_register", "role": "corroborating"},
            {"kind": "attestation", "ref": f"{KEY}:R1"},
        ],
        "needs_founder_review": True,
    },
    f"{KEY}:R2": {
        "title": "Policy",
        "sources": [{"kind": "attestation", "ref": f"{KEY}:R2"}],
        "needs_founder_review": False,
    },
    f"{KEY}:R3": {"title": "Instructions", "sources": []},
}


@pytest.fixture
def pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(
        FRAMEWORKS,
        KEY,
        FrameworkPack(KEY, "Test pack", requirements_data=ROWS),
    )
    folder = tmp_path / KEY
    folder.mkdir()
    (folder / "pack.json").write_text(
        json.dumps(
            {
                "id": KEY,
                "order": 1,
                "kind": "native",
                "name": "Test pack",
                "short_name": KEY,
                "status": "attestation-led",
                "disclaimer_ref": "DISCLAIMER_V2",
                "requirements": "requirements.json",
                "data_files": [],
                "legacy_file": "x.json",
                "copyright": "eu_law",
                "row_count": 3,
                "target_machine_share": 0,
                "timeline": "file",
                "catalogue": False,
            }
        ),
        encoding="utf-8",
    )
    (folder / "requirements.json").write_text(json.dumps(ROWS), encoding="utf-8")
    (folder / "timeline.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "id": "tst.first",
                        "title": "First <duty>",
                        "applies_from": "2030-01-01",
                        "scope_note": "Applies to test systems.",
                        "source": "Test source",
                        "confidence": "medium",
                        "needs_founder_review": True,
                        "requirements": [f"{KEY}:R1"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pack_registry, "PACKS_DIR", tmp_path)
    regulatory_timeline.load_pack_timeline.cache_clear()
    yield
    regulatory_timeline.load_pack_timeline.cache_clear()


def _row(rid: str, status: GapStatus, **over: Any) -> ArticleGapStatus:
    return ArticleGapStatus(
        article=rid,
        status=status,
        source=ArticleGapSource.ARTIFACT,
        evidence_ref="docs/risk_register.md",
        rationale="<b>thin</b>",
        **over,
    )


def _report(**over: Any) -> FrameworkReport:
    base: dict[str, Any] = {
        "framework": KEY,
        "label": "Test pack",
        "data_version": "cccccccccccc",
        "disclaimer_ref": "DISCLAIMER_V2",
        "excluded": {f"{KEY}:R3": "No deployers: internal tool only."},
        "report": GapReport(
            system_id="s",
            commit_ref="HEAD",
            generated_at="2026-01-01T00:00:00+00:00",
            articles=[
                _row(
                    f"{KEY}:R1",
                    GapStatus.MET,
                    evidence_class="hybrid",
                    corroborated=True,
                ),
                _row(f"{KEY}:R2", GapStatus.MISSING, evidence_class="organisational"),
            ],
        ),
    }
    base.update(over)
    return FrameworkReport(**base)


def test_section_renders_each_element(pack: None) -> None:
    out = render_framework_section(
        _report(applicability={"outcome": "voluntary", "reason": "Not in scope."})
    )
    assert "<h2>Test pack</h2>" in out
    assert "Data version cccccccccccc" in out
    assert "Applicability: voluntary" in out
    assert "Not in scope." in out
    assert "1 of 2 requirements checked from evidence" in out
    assert "<th>Evidence class</th>" in out
    assert "<td>hybrid</td>" in out
    assert "artifact: risk_register (corroborating); attestation: TST:R1" in out
    assert "<td>docs/risk_register.md</td>" in out
    assert "MET <em>corroborated</em>" in out
    assert "MISSING <em>" not in out
    assert "<li>TST:R3: No deployers: internal tool only.</li>" in out
    assert "<li>2030-01-01 - First &lt;duty&gt; [Test source;" in out
    assert DISCLAIMER_V2 in out
    assert "&lt;b&gt;thin&lt;/b&gt;" in out
    assert "<b>thin</b>" not in out


def test_unreviewed_mapping_is_flagged_only_where_the_data_says_so(pack: None) -> None:
    out = render_framework_section(_report())
    assert out.count("mapping not yet reviewed") == 1
    assert out.index("mapping not yet reviewed") < out.index("TST:R2")


def test_no_class_no_applicability_no_timeline_adds_nothing(
    pack: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plain = _report(
        excluded={},
        report=GapReport(
            system_id="s",
            commit_ref="HEAD",
            generated_at="2026-01-01T00:00:00+00:00",
            articles=[_row(f"{KEY}:R2", GapStatus.MISSING)],
        ),
    )
    monkeypatch.setattr(pack_registry, "PACKS_DIR", tmp_path / "none")
    out = render_framework_section(plain)
    assert "checked from evidence" not in out
    assert "Applicability" not in out
    assert "<p>Timeline</p>" not in out
    assert "<p>Excluded</p>" not in out


def test_section_never_claims_compliance(pack: None) -> None:
    out = render_framework_section(_report()).lower()
    assert "compliant" not in out
    assert "certified" not in out
