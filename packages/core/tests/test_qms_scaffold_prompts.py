"""Scaffold prompt lines are not author content (SU-L06)."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.gap_probes import (
    SCAFFOLD_PLACEHOLDER,
    artifact_gap_status,
    qms_clause_results,
    summarise_qms_clauses,
)
from opencomplai_core.qms_document import QMS_SCAFFOLD_STEMS, scaffold_qms


def _files(root: Path) -> list[Path]:
    return [
        root / "docs" / "qms" / f"{stem}.md" for stem in QMS_SCAFFOLD_STEMS.values()
    ]


def _drop_placeholders(root: Path, newline: str = "\n", trail: str = "") -> None:
    for path in _files(root):
        kept = [
            ln + trail
            for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() != SCAFFOLD_PLACEHOLDER
        ]
        path.write_bytes((newline.join(kept) + newline).encode("utf-8"))


def _labels(root: Path) -> list[str]:
    return [r.label for r in qms_clause_results(root)]


def test_deleting_only_placeholders_leaves_every_clause_unfilled(
    tmp_path: Path,
) -> None:
    scaffold_qms(tmp_path)
    _drop_placeholders(tmp_path)
    assert len(_files(tmp_path)) == 13
    for path in _files(tmp_path):
        assert SCAFFOLD_PLACEHOLDER not in path.read_text(encoding="utf-8")
    results = qms_clause_results(tmp_path)
    assert [r.label for r in results] == ["Unfilled"] * 13
    assert all(r.content_bearing is False for r in results)
    assert summarise_qms_clauses(results).present == 0
    rationale = artifact_gap_status("provider_qms", tmp_path).rationale
    assert "Per-clause: 0 present / 13 unfilled / 0 missing (of 13)." in rationale


def test_prompt_lines_are_ignored_with_crlf_and_trailing_spaces(tmp_path: Path) -> None:
    scaffold_qms(tmp_path)
    _drop_placeholders(tmp_path, newline="\r\n", trail="  ")
    assert _labels(tmp_path) == ["Unfilled"] * 13


def test_author_text_under_a_prompt_reads_present(tmp_path: Path) -> None:
    scaffold_qms(tmp_path)
    _drop_placeholders(tmp_path)
    qms = tmp_path / "docs" / "qms"
    rk = qms / "record-keeping.md"
    prompt_k = b"What records does it produce, and where are they stored?\n"
    data = rk.read_bytes()
    assert prompt_k in data
    rk.write_bytes(
        data.replace(
            prompt_k,
            prompt_k + b"We retain release approvals and evaluation reports in the "
            b"evidence vault for ten years.\n",
            1,
        )
    )
    af = qms / "accountability-framework.md"
    prompt_m = b"Who is accountable for it?\n"
    data = af.read_bytes()
    assert prompt_m in data
    af.write_bytes(
        data.replace(
            prompt_m,
            b"Who is accountable for it? The head of quality is responsible for this "
            b"framework and signs every release.\n",
            1,
        )
    )
    results = {r.letter: r for r in qms_clause_results(tmp_path)}
    assert len(results) == 13
    for letter, r in results.items():
        if letter in ("k", "m"):
            assert r.label == "Present", letter
            assert r.content_bearing is True, letter
        else:
            assert r.label == "Unfilled", letter
