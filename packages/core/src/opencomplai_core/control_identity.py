"""Deterministic identity helpers for the control instance registry.

Two pure functions, no I/O:

* `make_control_id` — the D2 deterministic ControlInstance primary key, so
  upserting a control for the same {tenant, system, obligation} triple across
  repeated runs is idempotent instead of creating duplicate rows.
* `fingerprint_manifest` — the D5 reassessment trigger. A stable hash over a
  watched subset of `SystemManifest` fields; when the fingerprint changes
  between runs, the manifest's compliance-relevant shape changed and the
  affected controls should be pushed back to PENDING_REVIEW / re-queued via
  `ReviewReason.MANIFEST_CHANGE`.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencomplai_core.models import SystemManifest

# D5 watched-fields subset: the SystemManifest fields whose change should
# trigger reassessment. Chosen from the actual SystemManifest field set
# (packages/core/src/opencomplai_core/models.py):
#   - intended_purpose        -> required by D5 verbatim (maps to Annex III
#                                 categories; a purpose change can move a
#                                 system across the risk classification).
#   - model_architecture      -> required by D5 verbatim (Annex IV Section 2
#                                 input; an architecture change can invalidate
#                                 prior technical documentation / conformity
#                                 evidence).
#   - high_risk_presumption   -> required by D5 verbatim (directly gates which
#                                 obligations apply).
#   - training_data_description -> the data-category-bearing field SystemManifest
#                                 actually has; provenance/curation changes can
#                                 affect Art. 10 data-governance evidence.
#   - operator_role           -> the deployment-context field SystemManifest
#                                 actually has (provider/deployer/etc. from the
#                                 applicability checker); a role change changes
#                                 which obligations apply to this system.
#   - operator_roles          -> every role the checker found. Unlike the fields
#                                 above, an EMPTY list is skipped (like None) so
#                                 manifests written before the field existed
#                                 keep their old fingerprint.
#   - human_oversight         -> the declared oversight roles; a change re-queues
#                                 the Art. 14 control. Skipped when absent (the
#                                 serializer omits it), so old fingerprints hold.
# SystemManifest has no literal `deployment_context`/`data_categories` fields
# (those live on `ModelMetadata`, a separate model not covered by D5), so
# `operator_role` and `training_data_description` are the closest existing
# analogues on SystemManifest itself.
WATCHED_MANIFEST_FIELDS: tuple[str, ...] = (
    "intended_purpose",
    "model_architecture",
    "high_risk_presumption",
    "training_data_description",
    "operator_role",
    "operator_roles",
    "human_oversight",
)

# Watched fields that are skipped when empty, not only when None.
_SKIP_WHEN_EMPTY = frozenset({"operator_roles"})


def make_control_id(tenant_id: str, system_id: str, obligation_id: str) -> str:
    """Deterministic ControlInstance id (D2): sha256(tenant|system|obligation)[:32]."""
    digest = hashlib.sha256(
        f"{tenant_id}|{system_id}|{obligation_id}".encode()
    ).hexdigest()
    return digest[:32]


def fingerprint_manifest(manifest: SystemManifest | dict[str, Any]) -> str:
    """Stable sha256 fingerprint over the D5 watched-fields subset of a manifest.

    Accepts either a `SystemManifest` instance or a plain dict of manifest
    fields. Fields not present in `WATCHED_MANIFEST_FIELDS`, any watched
    field whose value is None, and an empty `operator_roles` are excluded
    before hashing. The remaining
    subset is serialized as canonical JSON (sorted keys, compact separators)
    so the fingerprint is stable regardless of field declaration/insertion
    order and only changes when a watched field's value actually changes.
    """
    if isinstance(manifest, dict):
        values = manifest
    else:
        values = manifest.model_dump()

    subset = {
        field: values[field]
        for field in WATCHED_MANIFEST_FIELDS
        if field in values
        and values[field] is not None
        and not (field in _SKIP_WHEN_EMPTY and not values[field])
    }
    canonical = json.dumps(subset, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
