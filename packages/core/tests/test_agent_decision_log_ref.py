"""Art. 12 agent row: the decision log reference must name a real in-repo file."""

from __future__ import annotations

import builtins
import pathlib
from datetime import date
from pathlib import Path

from opencomplai_core.agent_sources import agent_gap_status
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import GapStatus, SystemManifest

_TODAY = date(2026, 10, 11)
_BASE = {
    "system_id": "sys-1",
    "intended_purpose": "credit scoring",
    "compliance_target": "EU_AI_ACT",
    "high_risk_presumption": True,
    "commit_ref": "abc123",
    "training_data_description": "internal loan applications 2018-2024",
    "model_architecture": "gradient boosted trees",
    "operator_role": "provider",
}
_NAME = "zephyr-planner-7"
_AGENT = {
    "id": "agent-a1",
    "name": _NAME,
    "tools": [{"name": "approve-wire-9", "kind": "function"}],
    "models": [{"provider": "OpenAI", "model": "gpt-x"}],
    "mandate": {"permitted_actions": ["tool:approve-wire-9"]},
    "guardrails": [{"kind": "output filter"}],
}
_MISSING = "decision log file is missing"
_ANCHOR = "anchor was not found"


def _manifest(ref: str) -> SystemManifest:
    agent = {**_AGENT, "logging": {"decision_log_ref": ref}}
    return SystemManifest(**_BASE, agent_inventory={"agents": [agent]})


def _art12(ref: str, repo_root: Path | None):
    return agent_gap_status(
        "Art. 12", _manifest(ref), None, today=_TODAY, repo_root=repo_root
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "logs").mkdir(parents=True)
    return repo


def test_existing_file_stays_partial(tmp_path) -> None:
    repo = _repo(tmp_path)
    (repo / "logs" / "decisions.jsonl").write_text("{}\n", encoding="utf-8")
    row = _art12("logs/decisions.jsonl", repo)
    assert row.status is GapStatus.PARTIAL
    assert _MISSING not in row.rationale
    assert _ANCHOR not in row.rationale


def test_missing_file_is_missing_with_reason(tmp_path) -> None:
    row = _art12("logs/decisions.jsonl", _repo(tmp_path))
    assert row.status is GapStatus.MISSING
    assert _MISSING in row.rationale


def test_traversal_absolute_and_directory_are_missing(tmp_path) -> None:
    repo = _repo(tmp_path)
    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}\n", encoding="utf-8")
    for ref in ("../outside.jsonl", str(outside), "logs"):
        row = _art12(ref, repo)
        assert row.status is GapStatus.MISSING, ref
        assert _MISSING in row.rationale, ref


def test_anchor_found_reads_as_before(tmp_path) -> None:
    repo = _repo(tmp_path)
    (repo / "logs" / "log.md").write_text(
        "# Agent\n\n## Decision Log\n\nentries\n", encoding="utf-8"
    )
    (repo / "logs" / "d.jsonl").write_text('{"run": "run-42"}\n', encoding="utf-8")
    for ref in ("logs/log.md#decision-log", "logs/d.jsonl#run-42"):
        row = _art12(ref, repo)
        assert row.status is GapStatus.PARTIAL, ref
        assert _ANCHOR not in row.rationale, ref
        assert _MISSING not in row.rationale, ref


def test_missing_anchor_is_partial_with_note(tmp_path) -> None:
    repo = _repo(tmp_path)
    (repo / "logs" / "log.md").write_text("## Other\n", encoding="utf-8")
    row = _art12("logs/log.md#decision-log", repo)
    assert row.status is GapStatus.PARTIAL
    assert _ANCHOR in row.rationale
    assert _MISSING not in row.rationale


def test_anchor_on_missing_file_is_missing(tmp_path) -> None:
    row = _art12("logs/absent.md#a", _repo(tmp_path))
    assert row.status is GapStatus.MISSING
    assert _MISSING in row.rationale
    assert _ANCHOR not in row.rationale


def test_outside_path_is_never_opened(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    (tmp_path / "outside.md").write_text("secret anchor\n", encoding="utf-8")
    opened: list[Path] = []
    real_path_open = pathlib.Path.open
    real_open = builtins.open

    def path_open(self, *args, **kwargs):
        opened.append(Path(self))
        return real_path_open(self, *args, **kwargs)

    def builtin_open(file, *args, **kwargs):
        opened.append(Path(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "open", path_open)
    monkeypatch.setattr(builtins, "open", builtin_open)
    root = repo.resolve()
    absolute = str(tmp_path / "outside.md")
    for ref in (
        "../outside.md",
        absolute,
        "../outside.md#secret",
        f"{absolute}#secret",
    ):
        assert _art12(ref, repo).status is GapStatus.MISSING, ref
    outside = [p for p in opened if not p.resolve().is_relative_to(root)]
    assert not outside


def test_no_repo_root_keeps_presence_only() -> None:
    row = _art12("logs/absent.jsonl", None)
    assert row.status is GapStatus.PARTIAL
    assert _MISSING not in row.rationale


def test_url_ref_is_not_checked(tmp_path) -> None:
    row = _art12("https://example.org/log#x", _repo(tmp_path))
    assert row.status is GapStatus.PARTIAL
    assert _MISSING not in row.rationale
    assert _ANCHOR not in row.rationale


def test_reason_text_carries_no_path(tmp_path) -> None:
    repo = _repo(tmp_path)
    (repo / "logs" / "present.md").write_text("x\n", encoding="utf-8")
    for ref in ("logs/secret-name.jsonl", "logs/present.md#secret-anchor"):
        row = _art12(ref, repo)
        for banned in (ref, "secret-name", "secret-anchor", _NAME, "agent-a1"):
            assert banned not in row.rationale, (ref, banned)


def test_build_gap_report_wires_repo_root(tmp_path) -> None:
    (tmp_path / "agent-log.jsonl").write_text("{}\n", encoding="utf-8")
    manifest = _manifest("logs/absent.jsonl")

    def art12_row():
        report = build_gap_report(
            "s", "HEAD", manifest=manifest, repo_root=tmp_path, today=_TODAY
        )
        rows = [a for a in report.articles if a.article == "Art. 12"]
        assert len(rows) == 1
        return rows[0]

    row = art12_row()
    assert row.status is GapStatus.MISSING
    assert _MISSING in row.rationale
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "absent.jsonl").write_text("{}\n", encoding="utf-8")
    row = art12_row()
    assert row.status is GapStatus.PARTIAL
    assert _MISSING not in row.rationale
