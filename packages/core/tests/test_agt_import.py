"""AGT audit-log importer: honest labelling, PARTIAL cap, no gate coupling."""

from __future__ import annotations

import ast
from pathlib import Path

import opencomplai_core
import opencomplai_core.bridges.agt as agt
import pytest
from opencomplai_core.bridges.agt import (
    INTEGRITY_LABEL,
    cap_status,
    import_jsonl,
    parse_map,
)
from opencomplai_core.models import GapStatus

FIXTURE = Path(__file__).parent / "fixtures" / "agt_audit" / "sample_agt.jsonl"
CORE = Path(opencomplai_core.__file__).parent


def test_preset_maps_fixture_fields():
    res = import_jsonl(FIXTURE)
    assert len(res.records) == 6
    assert res.rejected == 1
    assert res.rejected_samples == ((3, "not valid JSON"),)
    assert res.total_lines == 7
    first = res.records[0]
    assert (first.ts, first.agent_id, first.action) == (
        "2026-03-01T09:15:00Z",
        "agent-alpha",
        "search_docs",
    )
    assert (first.decision, first.rule) == ("allow", "allow-read-only")
    assert first.told == "Find the public onboarding guide"
    assert {r.decision for r in res.records} == {
        "allow",
        "deny",
        "approval_required",
        "escalate",
    }
    assert res.records[2].approver == "reviewer-one"
    assert res.records[2].line == 4  # blank and non-JSON lines keep their numbers


def test_map_override_wins(tmp_path):
    p = tmp_path / "a.jsonl"
    p.write_text('{"timestamp": "x", "when": "2026-01-01", "act": "do"}\n')
    res = import_jsonl(p, parse_map(["ts=when", "action=act"]))
    assert (res.records[0].ts, res.records[0].action) == ("2026-01-01", "do")


@pytest.mark.parametrize("pair", ["nope", "ts=", "bogus=a.b", "=x"])
def test_parse_map_rejects_bad_pair(pair):
    with pytest.raises(ValueError, match="bad --map"):
        parse_map([pair])


def test_malformed_lines_are_rejected_not_raised(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_bytes(b'[1,2]\n\xff\xfe\n{"unrelated": 1}\n{"action": "ok"}\n"str"\n')
    res = import_jsonl(p)
    assert len(res.records) == 1
    assert res.rejected == 4
    assert [n for n, _ in res.rejected_samples] == [1, 2, 3, 5]


def test_rejected_samples_are_capped(tmp_path):
    p = tmp_path / "many.jsonl"
    p.write_text("junk\n" * 50)
    res = import_jsonl(p)
    assert res.rejected == 50
    assert len(res.rejected_samples) == 20


def test_clean_log_is_partial_not_met():
    res = import_jsonl(FIXTURE)
    assert res.status == GapStatus.PARTIAL
    assert res.status != GapStatus.MET


def test_empty_or_unmappable_file_is_unverified(tmp_path):
    for body in (b"", b"\n\n", b'{"nothing": "mapped"}\n'):
        p = tmp_path / "e.jsonl"
        p.write_bytes(body)
        assert import_jsonl(p).status == GapStatus.UNVERIFIED


def test_status_never_met_for_any_input():
    for requested in GapStatus:
        assert cap_status(requested) != GapStatus.MET
        for count in range(4):
            best = cap_status(GapStatus.MET) if count else GapStatus.UNVERIFIED
            assert best != GapStatus.MET
    assert cap_status(GapStatus.MET) == GapStatus.PARTIAL
    assert cap_status(GapStatus.MISSING) == GapStatus.MISSING


def test_integrity_label_is_never_verified():
    res = import_jsonl(FIXTURE)
    assert res.integrity == INTEGRITY_LABEL == "format-valid, not verified"
    assert any("not verified" in c for c in res.caveats)
    assert any("Completeness and retention are not claimed" in c for c in res.caveats)


def test_preset_is_flagged_low_confidence():
    meta = agt.AGT_PRESET
    assert meta["confidence"] == "low"
    assert meta["needs_founder_review"] is True
    assert meta["source"]


def test_import_is_deterministic():
    assert import_jsonl(FIXTURE) == import_jsonl(FIXTURE)


def test_bom_and_crlf_are_tolerated(tmp_path):
    raw = FIXTURE.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    p = tmp_path / "crlf.jsonl"
    p.write_bytes(b"\xef\xbb\xbf" + raw)
    res = import_jsonl(p)
    base = import_jsonl(FIXTURE)
    assert len(res.records) == len(base.records)
    assert res.rejected == base.rejected
    assert [r.raw_sha256 for r in res.records] == [r.raw_sha256 for r in base.records]


def test_long_values_are_truncated(tmp_path):
    p = tmp_path / "long.jsonl"
    p.write_text('{"action": "' + "x" * 900 + '"}\n')
    assert len(import_jsonl(p).records[0].action) == 500


def _imports(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
            names += [f"{node.module}.{a.name}" for a in node.names]
    return names


def test_no_network_or_vendor_imports():
    banned = ("socket", "urllib", "http", "requests", "agentmesh", "agent_governance")
    for path in (Path(agt.__file__), CORE / "agent_dispute_report.py"):
        for name in _imports(path):
            assert name.split(".")[0] not in banned, (path.name, name)


def test_gap_and_check_paths_do_not_import_agt_bridge():
    cli = (
        Path(__file__).parents[2] / "cli" / "src" / "opencomplai_cli" / "exit_codes.py"
    )
    for path in (
        CORE / "gap_report.py",
        CORE / "engine.py",
        CORE / "frameworks.py",
        cli,
    ):
        for name in _imports(path):
            assert "bridges" not in name, (path.name, name)
            assert "agt" not in name.split("."), (path.name, name)
        assert "agent_dispute_report" not in path.read_text(encoding="utf-8")
