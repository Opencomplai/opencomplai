"""Operator roles recorded on a manifest."""

from __future__ import annotations

from opencomplai_core.models import SystemManifest


def effective_roles(manifest: SystemManifest) -> list[str]:
    """Every recorded role, primary first, deduplicated; `[]` when none is set."""
    roles = [manifest.operator_role] if manifest.operator_role else []
    roles += manifest.operator_roles or []
    return list(dict.fromkeys(r for r in roles if r))
