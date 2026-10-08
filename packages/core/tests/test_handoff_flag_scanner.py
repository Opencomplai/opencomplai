"""SU-G7j: the handoff flag scanner reads comment forms, and the packet lists them."""

from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_CHECKER = _REPO / "PLAN" / "SUMMIT-HANDOFF" / "check_handoff.py"

if not _CHECKER.is_file():
    pytest.skip(
        "enterprise-only handoff checker (the public tree strips PLAN/)",
        allow_module_level=True,
    )

_spec = importlib.util.spec_from_file_location("check_handoff", _CHECKER)
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)

_CATALOG = "packages/core/src/opencomplai_core/control_catalog.py"
_INCIDENT = (
    "dashboard-saas/services/ingest-api/src/dashboard_ingest/incident_projection.py"
)


def _hits_for(tmp_path, monkeypatch, text: str) -> set[int]:
    src = tmp_path / "src"
    src.mkdir()
    (src / "planted.py").write_bytes(text.encode("utf-8"))
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    return {n for p, n, _t in checker.flag_hits() if p == "src/planted.py"}


def test_scanner_flags_the_planted_comment_forms(tmp_path, monkeypatch):
    text = (
        "# placeholders flagged needs_founder_review\n"
        "# Field set is needs_founder_review (E-15): confidence low\n"
        "# (unverified: planted note)\n"
    )
    assert _hits_for(tmp_path, monkeypatch, text) == {1, 2, 3}


def test_scanner_ignores_declarations_and_false_values(tmp_path, monkeypatch):
    text = (
        "needs_founder_review: bool = False\n"
        "# needs_founder_review: false\n"
        "x = row.needs_founder_review\n"
    )
    assert _hits_for(tmp_path, monkeypatch, text) == set()


def test_packet_lists_every_flag_in_the_blind_spot_files():
    packet = (_CHECKER.parent / "04-lawyer-packet.md").read_text(encoding="utf-8")
    ids = set(re.findall(r"`([^`\s]+):(\d+)`", packet))
    hits = checker.flag_hits()
    for path, minimum in ((_CATALOG, 4), (_INCIDENT, 1)):
        found = [h for h in hits if h[0] == path]
        assert len(found) >= minimum, path
        listed = {n for p, n in ids if p == path}
        assert len(listed) >= len(found), path
