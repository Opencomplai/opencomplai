"""Real glob matching for artifact probes (SU-23a)."""

from __future__ import annotations

import os
from pathlib import Path

from opencomplai_core.gap_probes import (
    _PROBE_PATTERNS,
    _match_patterns,
    _scan_code_hints,
    artifact_gap_status,
    run_artifact_probe,
)
from opencomplai_core.models import GapStatus


def _touch(root: Path, *rels: str, text: str = "x") -> None:
    for rel in rels:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def test_double_star_matches_nested_and_zero_dirs(tmp_path: Path) -> None:
    _touch(tmp_path, "docs/qms/x.md", "docs/x.md", "docs/qms/y.md")
    assert _match_patterns(tmp_path, ("docs/**/x*",)) == ["docs/qms/x.md", "docs/x.md"]


def test_single_star_does_not_cross_directories(tmp_path: Path) -> None:
    _touch(tmp_path, "docs/x.md", "docs/qms/x.md")
    assert _match_patterns(tmp_path, ("docs/x*",)) == ["docs/x.md"]
    assert _match_patterns(tmp_path, ("docs/*.md",)) == ["docs/x.md"]


def test_matching_is_case_insensitive(tmp_path: Path) -> None:
    _touch(tmp_path, "DOCS/QMS/X.MD")
    assert _match_patterns(tmp_path, ("docs/**/x*",)) == ["DOCS/QMS/X.MD"]


def test_skipped_directories_are_never_walked(tmp_path: Path, monkeypatch) -> None:
    skip = (".venv", "node_modules", ".git")
    for d in skip:
        _touch(tmp_path, f"{d}/oversight_x.py")
    _touch(tmp_path, "src/oversight_y.py")
    visited: list[str] = []
    real = os.walk

    def spy(top, *a, **kw):
        for dirpath, dirs, files in real(top, *a, **kw):
            yield dirpath, dirs, files
            visited.extend(Path(dirpath).relative_to(top).parts)

    monkeypatch.setattr("opencomplai_core.gap_probes.os.walk", spy)
    assert _match_patterns(tmp_path, ("**/oversight*",)) == ["src/oversight_y.py"]
    assert not set(skip) & set(visited)


def test_code_hint_scan_skips_vendor_dirs(tmp_path: Path) -> None:
    import re

    rx = re.compile("human_oversight")
    _touch(tmp_path, ".venv/lib/a.py", text="human_oversight")
    assert _scan_code_hints(tmp_path, rx) == 0
    _touch(tmp_path, "src/a.py", text="human_oversight")
    assert _scan_code_hints(tmp_path, rx) == 1


def test_provider_qms_finds_any_file_under_docs_qms(tmp_path: Path) -> None:
    _touch(tmp_path, "docs/qms/anything.md", "docs/qms/sub/deep.md")
    st = artifact_gap_status("provider_qms", tmp_path)
    assert st.status == GapStatus.PARTIAL
    assert st.evidence_ref.startswith("docs/qms/")


def test_clause_probes_do_not_gain_the_directory_pattern() -> None:
    for ref, pats in _PROBE_PATTERNS.items():
        if ref.startswith("provider_qms_17_1_"):
            assert "docs/qms/**" not in pats
    assert "docs/qms/**" in _PROBE_PATTERNS["provider_qms"]


def test_duplicate_matches_are_collapsed(tmp_path: Path) -> None:
    _touch(tmp_path, "docs/risk_register.md")
    assert run_artifact_probe("risk_register", tmp_path).found_paths == [
        "docs/risk_register.md"
    ]


def test_results_are_sorted_and_capped_at_five(tmp_path: Path) -> None:
    _touch(tmp_path, *[f"docs/f{i}.md" for i in (6, 3, 1, 7, 5, 2, 4)])
    first = _match_patterns(tmp_path, ("docs/f*",))
    assert first == [f"docs/f{i}.md" for i in range(1, 6)]
    assert _match_patterns(tmp_path, ("docs/f*",)) == first


def test_exact_root_name_still_matches(tmp_path: Path) -> None:
    _touch(tmp_path, "INSTRUCTIONS.md")
    assert _match_patterns(tmp_path, ("INSTRUCTIONS.md",)) == ["INSTRUCTIONS.md"]
