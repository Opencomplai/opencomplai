"""`CorroborationReport.default_scan_coverage` is additive and omitted when None."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_core.scan_engine import run_scan
from opencomplai_core.scanner.feature_types import ScanConfig


def _report(tmp_path: Path):
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    return run_scan(
        system_id="s",
        commit_ref="HEAD",
        repo_root=tmp_path,
        declared_purpose="customer support chatbot",
        config=ScanConfig(),
    )


def test_report_without_field_dumps_without_key(tmp_path):
    report = _report(tmp_path)
    assert report.default_scan_coverage is None
    assert "default_scan_coverage" not in report.model_dump_json()


def test_field_round_trips_when_set(tmp_path):
    report = _report(tmp_path)
    report.default_scan_coverage = {"version": 1, "areas": {"1": "default_tokens"}}
    data = json.loads(report.model_dump_json())
    assert data["default_scan_coverage"]["areas"] == {"1": "default_tokens"}
    again = type(report).model_validate(data)
    assert again.default_scan_coverage == report.default_scan_coverage
