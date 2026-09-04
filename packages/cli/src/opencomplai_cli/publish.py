"""
Shared publish layer for pushing a signed ``ScanStatusArtifact`` to the
Opencomplai Premium Dashboard's ingest-api (GO-LIVE CORE-4).

Three callers share this module so the envelope they send is identical:

* ``opencomplai push`` (``opencomplai_cli.commands.push``)
* the GitHub Actions connector (``opencomplai_cli.connectors.github_actions``)
* the GitLab CI connector (``opencomplai_cli.connectors.gitlab_ci``)

Background (GO-LIVE DECISIONS.md G-2/G-4): the OSS
``opencomplai_core.models.ScanStatusArtifact`` and the dashboard's vendored
``first_scan_status.schema.json`` were never reconciled. G-2 found that
neither CI connector shaped its payload at all -- both posted the raw
artifact dict, which the schema's ``additionalProperties: false`` and its
``policy_bundle_version``/``timestamp``/``commit_ref`` requirements would
always reject with a 422. G-4 resolved this at both ends: the schema was
widened additively to accept the OSS evidentiary fields
(``evidence_hashes``, ``rationale_hash``, ``scan_summary``, ``gap_report``,
``eval_summary``, ``install_id``, ``signature``) and to widen the
``result`` enum with the three OSS-only ``ScanResult`` values
(``validation_fail``, ``policy_block``, ``degraded_complete``) -- and this
module supplies the other half: an *honest* mapper that synthesizes only
the handful of fields the OSS artifact genuinely lacks, and otherwise
passes every field through untouched. No evidentiary field is ever
dropped, renamed, or reshaped.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_MIN_COMMIT_REF_LENGTH = 7
_UNRESOLVED_COMMIT_REF = "unresolved"

# Environment variables a CI platform sets with the real commit SHA, checked
# in order, when the artifact's own commit_ref is unusable (e.g. the CLI's
# own "HEAD" default, or anything shorter than the schema's minLength: 7).
_CI_COMMIT_SHA_ENV_VARS = ("GITHUB_SHA", "CI_COMMIT_SHA")


# ---------------------------------------------------------------------------
# Redirect hardening
#
# urllib's default opener follows 301/302/303 on POST -- rewriting it to a
# bodyless GET -- and replays every original header, including
# `Authorization: Bearer <token>`, at whatever host the Location points to.
# A compromised or misconfigured dashboard endpoint (or anything sitting in
# front of it) could turn that into a silent credential leak to a third
# party. `_NoRedirectHandler.redirect_request` returning None makes
# `HTTPRedirectHandler` decline to build a follow-up request; with no
# handler resolving the redirect, `OpenerDirector.error()` falls through to
# `HTTPDefaultErrorHandler`, which raises `HTTPError` -- surfacing the 3xx
# as a normal, visible failure through `publish_scan_status`'s existing
# `except urllib.error.HTTPError` branch instead of silently chasing it.
# ---------------------------------------------------------------------------


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirectHandler)
# Installed as the process-wide default opener so ordinary
# `urllib.request.urlopen(...)` calls -- here and anywhere else in this
# process -- never follow a redirect. Existing tests that patch
# `urllib.request.urlopen` directly bypass the opener machinery entirely and
# are unaffected.
urllib.request.install_opener(_OPENER)


def _cli_version() -> str:
    """Installed ``opencomplai`` version, falling back to the bundled default.

    Mirrors ``main.py``'s ``_resolve_version`` without importing ``main``
    (which pulls in typer/rich for a one-line lookup).
    """
    try:
        return importlib.metadata.version("opencomplai")
    except importlib.metadata.PackageNotFoundError:
        from opencomplai_cli import __version__

        return __version__


def _resolve_commit_ref(
    value: Any, commit_env: Mapping[str, str], *, repo_dir: Path | str | None = None
) -> str:
    """Resolve a schema-valid (``minLength: 7``) commit ref.

    1. Keep the artifact's own ``commit_ref`` if it is already usable --
       at least 7 characters and not the CLI's literal ``"HEAD"`` default
       (``main.py``'s ``init``/``checker --write-manifest`` both default
       ``commit_ref`` to that literal string, which is never a real SHA).
    2. Else, a CI platform's own env var for the real commit SHA.
    3. Else, ask git directly (``git rev-parse HEAD``); any failure
       (not a git repo, git not installed, timeout) is swallowed.
    4. Else, the self-describing literal ``"unresolved"`` -- 10 characters,
       so it passes ``minLength: 7`` while being unmistakably not a real
       commit, rather than fabricating one.

    ``repo_dir``, when given, is passed as ``cwd=`` to the ``git`` fallback
    so step 3 resolves the repo the *artifact* lives in rather than
    whatever the calling process's own working directory happens to be --
    ``opencomplai push`` can run from anywhere and be pointed at an
    artifact file that lives elsewhere. ``None`` (the default) preserves
    the previous behaviour of inheriting the caller's own cwd, which is
    correct for the CI connectors: their artifact and their checkout are
    the same directory.
    """
    if (
        isinstance(value, str)
        and len(value) >= _MIN_COMMIT_REF_LENGTH
        and value != "HEAD"
    ):
        return value

    for var in _CI_COMMIT_SHA_ENV_VARS:
        candidate = commit_env.get(var, "")
        if len(candidate) >= _MIN_COMMIT_REF_LENGTH:
            return candidate

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=repo_dir,
        )
        sha = result.stdout.strip()
        if result.returncode == 0 and len(sha) >= _MIN_COMMIT_REF_LENGTH:
            return sha
    except (OSError, subprocess.SubprocessError):
        pass

    return _UNRESOLVED_COMMIT_REF


def prepare_scan_status_artifact(
    artifact: dict[str, Any],
    *,
    commit_env: Mapping[str, str] | None = None,
    repo_dir: Path | str | None = None,
) -> dict[str, Any]:
    """
    Map an OSS ``ScanStatusArtifact`` dict onto a schema-valid
    ``first_scan_status`` payload, honestly.

    Every field the OSS model produces (``install_id``, ``system_id``,
    ``commit_ref``, ``result``, ``failed_controls``, ``evidence_hashes``,
    ``rationale_hash``, ``duration_ms``, ``pending_verifications_count``,
    ``signature``, ``eval_summary``, ``scan_summary``, ``gap_report``)
    passes through unchanged -- the widened schema (G-4) now accepts all of
    them. Only the fields the OSS model has no concept of at all are
    synthesized here, and each synthesis is documented:

    * ``policy_bundle_version`` -- required by the schema; the OSS CLI has
      no policy-bundle concept (open product question, GX-1(a)). Stand-in:
      ``"cli-<opencomplai package version>"``, e.g. ``"cli-0.3.1"`` --
      self-describing, never confusable with a real dashboard-issued
      bundle version, and stable across scans from the same CLI install.
    * ``timestamp`` -- required by the schema; ``ScanStatusArtifact`` has
      no generation timestamp. Stand-in: push-time UTC ``now``, ISO 8601
      with a ``Z`` suffix. This is the *publish* time, not the *scan*
      time -- the two can differ when an artifact is pushed after the fact
      (e.g. ``opencomplai push`` run against a stale ``compliance-artifact
      .json``).
    * ``commit_ref`` -- resolved via ``_resolve_commit_ref`` above; the
      schema's ``minLength: 7`` rejects the CLI's literal ``"HEAD"``
      default outright.

    ``commit_env`` defaults to ``os.environ`` and exists purely so callers
    (and this module's own tests) can pass a synthetic environment without
    monkeypatching process-global state. ``repo_dir`` is forwarded to
    ``_resolve_commit_ref``'s ``git`` fallback -- see that function's
    docstring.
    """
    if commit_env is None:
        import os

        commit_env = os.environ

    prepared = dict(artifact)

    if not prepared.get("policy_bundle_version"):
        prepared["policy_bundle_version"] = f"cli-{_cli_version()}"

    if not prepared.get("timestamp"):
        prepared["timestamp"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    prepared["commit_ref"] = _resolve_commit_ref(
        prepared.get("commit_ref"), commit_env, repo_dir=repo_dir
    )

    return prepared


def envelope_signature(original: dict[str, Any], prepared: dict[str, Any]) -> str:
    """
    Decide whether an OSS-embedded artifact signature is safe to forward in
    the ingest envelope (GO-LIVE decision G-5).

    WHY this is not just ``prepared.get("signature") or ""``: the OSS CLI
    signs the canonical bytes of the artifact exactly as ``opencomplai
    check --sign`` produced it (``packages/core``'s
    ``signing.sign_artifact``). ``prepare_scan_status_artifact`` above then
    *mutates* that artifact -- filling in ``policy_bundle_version``/
    ``timestamp``, fields the OSS model has no concept of, and
    re-resolving ``commit_ref`` whenever the OSS value is unusable (e.g.
    the literal ``"HEAD"``). ``dashboard_ingest`` verifies a signature
    against the artifact **as received** (see
    ``dashboard_ingest.verify.verify_envelope`` /
    ``canonical.artifact_signing_payload``), so a signature computed over
    the pre-mapping bytes can never verify against the post-mapping
    artifact whenever the mapper changed anything. Forwarding it anyway
    would not "sort of" work -- it would deterministically fail closed
    with ``SIGNATURE_INVALID`` on every push that needed any mapping at
    all, which is nearly all of them (a bare CLI artifact almost never
    already carries ``policy_bundle_version``/``timestamp``/a usable
    ``commit_ref``).

    So: the signature is forwarded only when ``prepared`` is byte-for-byte
    identical to ``original`` -- the mapper had nothing to add or change --
    and the original signature is a non-empty string. In every other case
    the envelope signature is ``""``, and it is the caller's own
    authentication (an ``ock_`` API key or a tenant JWT) that the
    dashboard is left attesting the request with, not a signature that is
    guaranteed to be rejected. Map-before-sign (making the OSS CLI sign
    the *mapped* payload so a forwarded signature always verifies) is
    deferred to GX-1(d) rather than solved here.
    """
    signature = original.get("signature")
    if not isinstance(signature, str) or signature == "":
        return ""
    if prepared != original:
        return ""
    return signature


def publish_scan_status(
    base_url: str, token: str, envelope: dict[str, Any], timeout: int = 30
) -> tuple[int, dict[str, Any]]:
    """
    POST an ingest envelope to ``{base_url}/v1/ingest/scan-status``.

    Transport extracted from ``github_actions._publish_to_dashboard``'s
    urllib block (URL, method, headers, and JSON body construction are
    unchanged) and broadened to return the response rather than discard
    it, matching the ``(status, data)`` contract already used by
    ``main.py``'s ``_call_service`` and ``commands/dashboard.py``'s
    ``_post``.

    Returns ``(status_code, response_body)``. A response body that fails
    to parse as JSON (including an empty body on success, or a non-JSON
    error page from an intermediary proxy) is reported as an empty dict
    rather than raising, since every caller here already treats a non-2xx
    status as the failure signal.

    Raises nothing itself for network-level failures (DNS, connection
    refused, timeout) -- these come back as status ``0`` with an
    ``"error"`` key, so a caller can log/exit on that consistently with an
    HTTP-level failure instead of needing a second exception-handling
    path.
    """
    data = json.dumps(envelope).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/ingest/scan-status",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, _parse_json_body(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _parse_json_body(exc.read())
    except (
        Exception
    ) as exc:  # network failure (DNS/connection/timeout) -- reported, not raised
        return 0, {"error": str(exc)}


def _parse_json_body(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


# ---------------------------------------------------------------------------
# Dossier-envelope producer (DG-10)
#
# Unlike prepare_scan_status_artifact above -- which is mostly a passthrough
# because the OSS ScanStatusArtifact model and the ingest schema were
# reconciled field-for-field (G-4) -- the dossier_envelope schema
# (schemas/dossier_envelope.schema.json) is a deliberately narrow *metadata*
# envelope, structurally unrelated to opencomplai_core.dossier.AnnexIVDossier
# (which carries the full nine Annex IV sections). The bundle itself never
# crosses the egress boundary at C0; only its checksum, size, and a handful
# of provenance fields do. So this is a genuine reshape, not a passthrough:
# every dossier_envelope field is either read off the dossier under a
# different name or synthesized outright, and no Annex IV section content
# is ever forwarded.
# ---------------------------------------------------------------------------


def prepare_dossier_envelope(
    dossier: dict[str, Any],
    *,
    commit_env: Mapping[str, str] | None = None,
    repo_dir: Path | str | None = None,
) -> dict[str, Any]:
    """
    Map a locally-generated Annex IV dossier onto a schema-valid
    ``dossier_envelope`` payload for ``POST /v1/ingest/dossier-envelope``.

    ``dossier`` is the dict ``opencomplai docs generate``'s local fallback
    already has in hand -- ``AnnexIVDossier.model_dump(mode="json")``, the
    same object it serializes to ``dossier_<id>.json`` on disk (``main.py``,
    ``docs_generate_cmd``'s local-fallback branch). Field derivation,
    mirroring ``prepare_scan_status_artifact``'s doc comment style:

    * ``system_id``, ``bundle_checksum``, ``compliance_target`` -- read
      straight off the dossier; the two models happen to name these
      identically.
    * ``commit_ref`` -- resolved via ``_resolve_commit_ref`` (the same
      helper scan status uses, for the same reason): ``docs generate``'s
      own ``commit_ref`` default is the literal ``"HEAD"``, 4 characters,
      well under the schema's ``minLength: 7``.
    * ``timestamp`` -- the dossier's own ``generated_at`` when present,
      else push-time UTC ``now`` (ISO 8601, ``Z`` suffix) -- same fallback
      ``prepare_scan_status_artifact`` uses for its own ``timestamp``.
    * ``size_bytes`` -- byte length of ``dossier`` re-serialized as
      compact, key-sorted JSON. Computed here (not by the caller) so two
      callers handed the same dossier content always report the same size,
      the same way ``bundle_checksum`` is already deterministic over the
      dossier's content. Deliberately independent of whatever indentation
      ``docs generate`` used to write the sibling ``dossier_<id>.json`` to
      disk -- that's a presentation choice, not part of the bundle's
      identity.
    * ``signed_by`` -- self-describing ``"cli:<signature_status>"`` (e.g.
      ``cli:unsigned`` in OSS default mode, ``cli:hmac-local`` /
      ``cli:ed25519`` when a local signing key is configured via
      ``generate_dossier``) rather than a fabricated key id. Mirrors
      ``dashboard_ingest.routes``'s own ``"api-key:{key_id}"`` stamping
      convention for a non-cryptographic attestation of provenance.
    * ``policy_bundle_version`` -- same ``"cli-<version>"`` stand-in as
      scan status. Schema-optional here; included for producer parity.
    * ``result`` -- always ``"generated"`` (schema enum: ``generated`` /
      ``cached`` / ``failed``) -- this function is only ever called after
      a dossier was actually produced; ``cached``/``failed`` have no local
      OSS-CLI equivalent to report honestly, so they are never emitted.

    The returned dict carries *only* the fields the schema defines
    (``additionalProperties: false``) -- no Annex IV section content,
    ``dossier_id``, or ``evidence_hashes`` is ever included, unlike
    ``prepare_scan_status_artifact``'s passthrough of every OSS field.
    """
    if commit_env is None:
        import os

        commit_env = os.environ

    canonical = json.dumps(dossier, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    bundle_checksum = dossier.get("bundle_checksum") or (
        f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    )
    signature_status = dossier.get("signature_status") or "unsigned"
    timestamp = dossier.get("generated_at") or (
        datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )

    return {
        "system_id": dossier.get("system_id", "unknown"),
        "commit_ref": _resolve_commit_ref(
            dossier.get("commit_ref"), commit_env, repo_dir=repo_dir
        ),
        "bundle_checksum": bundle_checksum,
        "size_bytes": len(canonical),
        "signed_by": f"cli:{signature_status}",
        "timestamp": timestamp,
        "compliance_target": dossier.get("compliance_target", "EU_AI_ACT"),
        "policy_bundle_version": f"cli-{_cli_version()}",
        "result": "generated",
    }


def publish_dossier_envelope(
    base_url: str, token: str, envelope: dict[str, Any], timeout: int = 30
) -> tuple[int, dict[str, Any]]:
    """
    POST an ingest envelope to ``{base_url}/v1/ingest/dossier-envelope``.

    Transliterated from ``publish_scan_status`` above -- identical headers,
    identical redirect-blocking opener (installed process-wide at import
    time, see ``_NoRedirectHandler``), identical ``(status, response_body)``
    contract, identical swallow-network-failure-as-status-0 behaviour. Only
    the URL path differs.
    """
    data = json.dumps(envelope).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/ingest/dossier-envelope",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, _parse_json_body(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _parse_json_body(exc.read())
    except (
        Exception
    ) as exc:  # network failure (DNS/connection/timeout) -- reported, not raised
        return 0, {"error": str(exc)}


__all__ = [
    "envelope_signature",
    "prepare_dossier_envelope",
    "prepare_scan_status_artifact",
    "publish_dossier_envelope",
    "publish_scan_status",
]
