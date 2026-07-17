"""Sanitize helpers for hostile-repo report surfaces."""

from __future__ import annotations

from opencomplai_core.scanner.sanitize import (
    sanitize_path_for_display,
    sanitize_report_text,
    strip_ansi,
)


def test_strip_ansi_removes_csi():
    raw = "evil\x1b[31mred\x1b[0m"
    assert strip_ansi(raw) == "evilred"


def test_sanitize_neutralizes_rich_markup():
    text = sanitize_report_text("file[bold]name.py", for_rich=True)
    assert "[bold]" not in text
    assert "\\[" in text


def test_sanitize_path_strips_nulls():
    assert "\x00" not in sanitize_path_for_display("a\x00b.py")
