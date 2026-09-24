"""`opencomplai.yaml` — project-level tool-behavior config (scan defaults, evaluator
threshold overrides, allowlists, which frameworks gate `check`).

Governs tool *behavior* only (scan defaults, thresholds, allowlists, CI gating) —
never a source of compliance *declarations*. It must never become a second, competing
source of truth against the manifest for compliance posture; `SystemManifest` remains
the sole authority for what a system is declared to do. Gating decides which
frameworks' gaps fail CI; it declares nothing about the system. Additive to (not
replacing) `.ocignore` and explicit CLI flags — explicit CLI flags always override
values from this file.
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
    # Non-EU frameworks whose Missing (or Partial) rows fail `check`.
    gate_frameworks: list[str] = field(default_factory=list)
    gate_fail_on: str | None = None


def find_project_config(start_dir: Path) -> Path | None:
    """Look for `opencomplai.yaml` in `start_dir`, returning its path if present."""
    candidate = start_dir / DEFAULT_CONFIG_FILENAME
    return candidate if candidate.exists() else None


def _section(raw: dict, key: str, path: Path) -> dict:
    section = raw.get(key) or {}
    if not isinstance(section, dict):
        raise ValueError(f"{path.name}: {key} must be a mapping")
    return section


def load_project_config(path: Path) -> ProjectConfig:
    """Parse an `opencomplai.yaml` file. Missing/empty keys fall back to defaults.

    Raises ValueError when the file is not YAML or a section has the wrong shape.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"{path.name}: not valid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name}: must be a mapping")

    scan_section = _section(raw, "scan", path)
    eval_section = _section(raw, "eval", path)
    gate_section = _section(raw, "gate", path)
    gate_frameworks = gate_section.get("frameworks") or []
    if not isinstance(gate_frameworks, list) or not all(
        isinstance(fw, str) for fw in gate_frameworks
    ):
        raise ValueError(f"{path.name}: gate.frameworks must be a list of frameworks")
    gate_fail_on = gate_section.get("fail_on")
    if gate_fail_on is not None and not isinstance(gate_fail_on, str):
        raise ValueError(f"{path.name}: gate.fail_on must be missing or partial")

    return ProjectConfig(
        scan_fail_on=scan_section.get("fail_on"),
        scan_framework_detectors=scan_section.get("framework_detectors"),
        eval_threshold_overrides=dict(
            eval_section.get("threshold_overrides", {}) or {}
        ),
        allowlisted_categories=list(
            scan_section.get("allowlisted_categories", []) or []
        ),
        gate_frameworks=gate_frameworks,
        gate_fail_on=gate_fail_on,
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
