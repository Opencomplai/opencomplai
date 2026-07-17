"""Sanitize hostile strings before they reach terminal/HTML/JSON report surfaces.

Strips ANSI/OSC control sequences and neutralizes Rich markup metacharacters so a
malicious filename or comment cannot inject styling or escape sequences into CLI
output (SOC2 CC7 / ISO A.8.28).
"""

from __future__ import annotations

import re

# CSI / OSC / other common ANSI escape forms
_ANSI_RE = re.compile(
    r"(?:\x1B[@-Z\\-_]"  # 2-char sequences
    r"|\x1B\[[0-?]*[ -/]*[@-~]"  # CSI
    r"|\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)"  # OSC
    r"|\x9B[0-?]*[ -/]*[@-~])"  # 8-bit CSI
)

# Characters that start Rich markup tags
_RICH_MARKUP_RE = re.compile(r"[\[\]]")


def strip_ansi(text: str) -> str:
    """Remove ANSI/OSC control sequences from *text*."""
    return _ANSI_RE.sub("", text)


def neutralize_rich_markup(text: str) -> str:
    """Escape Rich markup brackets so untrusted text cannot inject styles."""
    return text.replace("[", "\\[").replace("]", "\\]")


def sanitize_report_text(text: str, *, for_rich: bool = False) -> str:
    """Strip control chars; optionally neutralize Rich markup for console print."""
    cleaned = strip_ansi(text).replace("\x00", "")
    # Drop other C0 controls except tab/newline/carriage-return
    cleaned = "".join(
        ch for ch in cleaned if ch in ("\t", "\n", "\r") or ord(ch) >= 0x20
    )
    if for_rich:
        cleaned = neutralize_rich_markup(cleaned)
    return cleaned


def sanitize_path_for_display(path: str, *, for_rich: bool = False) -> str:
    """Sanitize a repo-relative path for display in reports and terminals."""
    return sanitize_report_text(path.replace("\\", "/"), for_rich=for_rich)
