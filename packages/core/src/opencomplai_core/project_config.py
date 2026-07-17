"""`opencomplai.yaml` — project-level tool-behavior config (scan defaults, evaluator
threshold overrides, allowlists).

Governs tool *behavior* only (scan defaults, thresholds, allowlists) — never a source
of compliance *declarations*. It must never become a second, competing source of truth
against the manifest for compliance posture; `SystemManifest` remains the sole
authority for what a system is declared to do. Additive to (not replacing) `.ocignore`
and explicit CLI flags — explicit CLI flags always override values from this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_FILENAME = "opencomplai.yaml"


@dataclass
class ProjectConfig:
    """Parsed `opencomplai.yaml` contents. All fields are optional tool-behavior
    defaults — absence of a field means "use the built-in default", never "treat as
    a compliance gap"."""

    scan_fail_on: str | None = None
    scan_framework_detectors: bool | None = None
    eval_threshold_overrides: dict[str, float] = field(default_factory=dict)
    allowlisted_categories: list[str] = field(default_factory=list)


def find_project_config(start_dir: Path) -> Path | None:
    """Look for `opencomplai.yaml` in `start_dir`, returning its path if present."""
    candidate = start_dir / DEFAULT_CONFIG_FILENAME
    return candidate if candidate.exists() else None


def load_project_config(path: Path) -> ProjectConfig:
    """Parse an `opencomplai.yaml` file. Missing/empty keys fall back to defaults."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    scan_section = raw.get("scan", {}) or {}
    eval_section = raw.get("eval", {}) or {}

    return ProjectConfig(
        scan_fail_on=scan_section.get("fail_on"),
        scan_framework_detectors=scan_section.get("framework_detectors"),
        eval_threshold_overrides=dict(eval_section.get("threshold_overrides", {}) or {}),
        allowlisted_categories=list(scan_section.get("allowlisted_categories", []) or []),
    )


def apply_project_config_defaults(
    config: ProjectConfig | None,
    *,
    cli_fail_on_was_explicit: bool,
    current_fail_on: str,
    cli_framework_detectors_was_explicit: bool,
    current_framework_detectors: bool,
) -> tuple[str, bool]:
    """Resolve (fail_on, framework_detectors) honoring the precedence: explicit CLI
    flag > opencomplai.yaml > built-in default.

    Callers pass whether each CLI flag was explicitly supplied (Typer's `Context` or
    a sentinel default can determine this) so an unset CLI flag can be overridden by
    the project config, while an explicitly-passed CLI flag always wins.
    """
    fail_on = current_fail_on
    framework_detectors = current_framework_detectors

    if config is not None:
        if not cli_fail_on_was_explicit and config.scan_fail_on is not None:
            fail_on = config.scan_fail_on
        if (
            not cli_framework_detectors_was_explicit
            and config.scan_framework_detectors is not None
        ):
            framework_detectors = config.scan_framework_detectors

    return fail_on, framework_detectors
