"""Attestation bundles in the CLI: read one, merge it into the manifest, say what happened.

A bundle is a signed document of attestations and exclusions (see
`opencomplai_core.attestation_bundle`). It comes from a file, or from the endpoint
configured in `OPENCOMPLAI_DASHBOARD_URL` with the same `OPENCOMPLAI_API_KEY` that
`opencomplai push` uses. Both are opt-in: with neither a flag nor an
`opencomplai.yaml` `attestations` section, nothing is read and nothing is fetched.

The merge writes into a COPY of the manifest's `framework_inputs`, once, before
the first evaluation, so every command that evaluates frameworks sees it. The
manifest wins on the same requirement id. The CLI does not check the bundle's
signature (it holds no issuer key); it copies the hash and signature into the scan
artifact unchanged, and whoever receives the artifact can verify them.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlparse

from opencomplai_core.attestation_bundle import AttestationBundle, bundle_ref
from opencomplai_core.frameworks import (
    EU_AI_ACT,
    FRAMEWORKS,
    attestable_ids,
    attestation_only_ids,
    load_requirements_map,
)
from opencomplai_core.gap_report import stale_attestation_warnings
from opencomplai_core.models import (
    AttestationBundleRef,
    AttestationBundleUnavailable,
    FrameworkInputs,
    SystemManifest,
)
from opencomplai_core.project_config import ProjectConfig
from pydantic import ValidationError

# Importing publish installs the process-wide opener that never follows a
# redirect, so the API key is never replayed at another host.
from opencomplai_cli.publish import LOCAL_HOSTNAMES

#: The most a bundle may weigh, in a file and in an HTTP response, before it is parsed.
MAX_BUNDLE_BYTES = 2 * 1024 * 1024

_EU_PREFIX = f"{EU_AI_ACT}:"

# What can travel in an Authorization header: printable ASCII, no whitespace.
_SENDABLE_KEY = re.compile(r"[\x21-\x7e]+")

BundleStatus = AttestationBundleRef | AttestationBundleUnavailable


class AttestationError(ValueError):
    """A bundle that cannot be used. `code` is the machine reason the scan artifact
    records when the bundle was fetched (`^[a-z0-9_]{1,64}$`)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Source:
    """Where a run reads its bundle from: a file, or the configured endpoint."""

    remote: bool
    path: Path | None = None


def resolve_source(
    file_flag: Path | None, remote_flag: bool, config: ProjectConfig
) -> Source | None:
    """The bundle source for a run, or None for the default offline run.

    A flag beats `opencomplai.yaml`; the two flags together are a usage error.
    """
    if file_flag is not None and remote_flag:
        raise ValueError("use --attestations-file or --attestations-remote, not both")
    if file_flag is not None:
        return Source(remote=False, path=file_flag)
    if remote_flag:
        return Source(remote=True)
    if config.attestations_source == "remote":
        return Source(remote=True)
    if config.attestations_source == "file":
        return Source(remote=False, path=config.attestations_path)
    return None


def _parse_bundle(raw: bytes, origin: str) -> AttestationBundle:
    if len(raw) > MAX_BUNDLE_BYTES:
        raise AttestationError(
            "bundle_too_large",
            f"{origin} is larger than {MAX_BUNDLE_BYTES // 1024} KiB",
        )
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, RecursionError) as exc:
        # JSONDecodeError and UnicodeDecodeError; RecursionError is a payload nested
        # deeper than the parser allows, which the size cap does not bound.
        raise AttestationError(
            "invalid_bundle", f"{origin} is not valid JSON: {exc}"
        ) from exc
    try:
        return AttestationBundle.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(part) for part in first["loc"]) or "bundle"
        # `loc` and `msg` can quote text the bundle chose (a key, a bad date);
        # ascii() keeps control characters out of the terminal.
        detail = ascii(f"{where}: {first['msg']}")[1:-1]
        raise AttestationError(
            "invalid_bundle", f"{origin} is not a valid attestation bundle: {detail}"
        ) from exc


def load_bundle_file(path: Path) -> AttestationBundle:
    """Read and validate a bundle file. Raises AttestationError."""
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_BUNDLE_BYTES + 1)
    except OSError as exc:
        raise AttestationError(
            "read_failed", f"could not read {path}: {exc.strerror or exc}"
        ) from exc
    return _parse_bundle(raw, str(path))


def bundle_url(base_url: str, system_id: str | None) -> str:
    """`<base>/v1/attestations`, with `?system_id=` when a system is named.

    Raises AttestationError for a scheme other than https, or http to a host that
    is not this machine (push only warns about that; here the API key would
    travel in clear, so it is an error).
    """
    base = base_url.rstrip("/")
    invalid = AttestationError(
        "invalid_url", "OPENCOMPLAI_DASHBOARD_URL must be an http(s) URL"
    )
    try:
        parsed = urlparse(base)
        hostname = parsed.hostname
    except ValueError as exc:  # e.g. an unterminated IPv6 bracket
        raise invalid from exc
    if parsed.scheme not in ("http", "https") or not hostname:
        raise invalid
    if parsed.scheme == "http" and hostname not in LOCAL_HOSTNAMES:
        raise AttestationError(
            "http_refused",
            "OPENCOMPLAI_DASHBOARD_URL uses plain http to a remote host: the API key "
            "would be sent unencrypted. Use https (plain http is accepted only for "
            "localhost, 127.0.0.1 and ::1).",
        )
    query = f"?system_id={quote(system_id, safe='')}" if system_id else ""
    return f"{base}/v1/attestations{query}"


def fetch_bundle(
    base_url: str, api_key: str, system_id: str | None, *, timeout: int = 30
) -> AttestationBundle:
    """GET the bundle from `<base_url>/v1/attestations?system_id=<id>`.

    Raises AttestationError. Nothing foreign is echoed: not the response body, and
    not the text of an exception that could quote the key (a key with a newline in
    it makes http.client put the whole header into its error).
    """
    if not _SENDABLE_KEY.fullmatch(api_key):
        raise AttestationError(
            "not_configured",
            "OPENCOMPLAI_API_KEY contains characters that cannot be sent "
            "(whitespace, a newline or non-ASCII); check how it is set",
        )
    request = urllib.request.Request(
        bundle_url(base_url, system_id),
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_BUNDLE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise AttestationError(
            "fetch_failed", f"the endpoint answered HTTP {exc.code}"
        ) from exc
    except OSError as exc:  # URLError, DNS, refused connection, timeout, TLS
        raise AttestationError(
            "fetch_failed", f"could not reach the endpoint: {exc}"
        ) from exc
    except Exception as exc:  # anything else: name the type only
        raise AttestationError(
            "fetch_failed",
            f"could not reach the endpoint ({type(exc).__name__})",
        ) from exc
    return _parse_bundle(raw, "the endpoint's response")


def _check_system(bundle: AttestationBundle, system_id: str) -> None:
    if bundle.system_id not in (None, system_id):
        raise AttestationError(
            "system_mismatch",
            f"the bundle is for system {bundle.system_id!r}, not {system_id!r}",
        )


def _engine_key(framework: str, requirement_id: str) -> str:
    """The key `framework_inputs.<fw>.attested` uses. The EU AI Act spells its ids
    without a prefix ("Art. 4"); a bundle may carry either form."""
    if framework == EU_AI_ACT and requirement_id.startswith(_EU_PREFIX):
        return requirement_id[len(_EU_PREFIX) :]
    return requirement_id


def merge_into_manifest(
    manifest: SystemManifest,
    bundle: AttestationBundle,
    targets: Sequence[str] | None = None,
) -> tuple[SystemManifest, list[str], AttestationBundleRef]:
    """A copy of `manifest` with the bundle's records in `framework_inputs`.

    Returns (copy, warnings, the reference the scan artifact records). The manifest
    wins on the same requirement id, with a warning for each bundle record or
    exclusion it shadows. A framework the CLI does not know, and an id
    that is not a requirement taking an attestation, is dropped with a warning; an
    exclusion applies only to a row that an attestation alone decides, so the EU
    AI Act (which takes no exclusions) and NIST AI RMF never get one. Frameworks the
    run does not target are ignored (the EU AI Act is always evaluated). `targets`
    None means every framework.
    """
    warnings: list[str] = []
    wanted = None if targets is None else {*targets, EU_AI_ACT}
    merged: dict[str, FrameworkInputs] = dict(manifest.framework_inputs)

    for fw in sorted({*bundle.attestations, *bundle.excluded}):
        if fw not in FRAMEWORKS:
            warnings.append(f"the bundle names an unknown framework {fw!r}; ignored")
            continue
        if wanted is not None and fw not in wanted:
            continue
        own = manifest.framework_inputs.get(fw, FrameworkInputs())
        attested = dict(own.attested)
        excluded = dict(own.excluded)
        decided = {*own.attested, *own.excluded}  # the manifest wins on these
        from_bundle: set[str] = set()

        attestable = attestable_ids(fw)
        for rid, record in sorted(bundle.attestations.get(fw, {}).items()):
            key = _engine_key(fw, rid)
            if key not in attestable:
                warnings.append(
                    f"{rid!r} is not a {fw} requirement that takes an attestation; ignored"
                )
            elif key in from_bundle:
                warnings.append(
                    f"{rid!r}: the bundle already has a record for {key!r}; "
                    "the first is kept"
                )
            elif key in decided:
                warnings.append(
                    f"{rid!r}: the manifest already records {key!r}; "
                    f"the bundle's record {record.record_id} is not used"
                )
            else:
                attested[key] = record.to_attestation()
                from_bundle.add(key)

        only = attestation_only_ids(fw)
        for rid, reason in sorted(bundle.excluded.get(fw, {}).items()):
            if fw == EU_AI_ACT:
                warnings.append(f"{rid!r}: the EU AI Act takes no exclusions; ignored")
            elif rid not in only:
                warnings.append(
                    f"{rid!r} is not a {fw} row that only an attestation decides; "
                    "the exclusion is ignored"
                )
            elif rid in attested and rid not in own.attested:
                warnings.append(
                    f"{rid!r} is both attested and excluded in the bundle; "
                    "the exclusion is ignored"
                )
            elif rid in decided:
                warnings.append(
                    f"{rid!r}: the manifest already records this requirement; "
                    "the bundle's exclusion is not used"
                )
            else:
                excluded[rid] = reason

        if attested != own.attested or excluded != own.excluded:
            merged[fw] = own.model_copy(
                update={"attested": attested, "excluded": excluded}
            )
    return (
        manifest.model_copy(update={"framework_inputs": merged}),
        warnings,
        bundle_ref(bundle),
    )


def _requirements(framework: str) -> Mapping[str, object]:
    pack = FRAMEWORKS.get(framework)
    if pack is None or pack.requirements is None:
        return {}
    return load_requirements_map(pack.requirements)


def staleness_warnings(
    manifest: SystemManifest, targets: Sequence[str], today: date
) -> list[str]:
    """Undated attestations older than their row's review period, for the
    frameworks the run evaluates."""
    out: list[str] = []
    for fw in sorted({*targets, EU_AI_ACT}):
        inputs = manifest.framework_inputs.get(fw)
        if inputs is not None:
            out.extend(
                stale_attestation_warnings(inputs.attested, _requirements(fw), today)
            )
    return out


def load_for_run(
    manifest: SystemManifest,
    targets: Sequence[str],
    *,
    file_flag: Path | None,
    remote_flag: bool,
    config: ProjectConfig,
    today: date,
    warn: Callable[[str], None],
    env: Mapping[str, str] | None = None,
) -> tuple[SystemManifest, BundleStatus | None]:
    """The manifest a run evaluates and what to record in the artifact.

    Without a configured source this makes no network call and returns the manifest
    untouched with None. A bundle file that cannot be used raises AttestationError
    (the run should exit 2); an endpoint that cannot be used warns and the run goes
    on with the manifest alone, recorded as `unavailable`.
    """
    source = resolve_source(file_flag, remote_flag, config)
    status: BundleStatus | None = None
    if source is not None:
        try:
            if source.remote:
                bundle = fetch_from_env(manifest.system_id, env)
            else:
                if source.path is None:
                    raise AttestationError(
                        "read_failed", "attestations: source file needs a path"
                    )
                bundle = load_bundle_file(source.path)
                _check_system(bundle, manifest.system_id)
        except AttestationError as exc:
            if not source.remote:
                raise
            warn(f"attestation bundle unavailable ({exc.code}): {exc}")
            status = AttestationBundleUnavailable(status="unavailable", reason=exc.code)
        else:
            manifest, merge_warnings, status = merge_into_manifest(
                manifest, bundle, targets
            )
            for message in merge_warnings:
                warn(message)
    for message in staleness_warnings(manifest, targets, today):
        warn(message)
    return manifest, status


def fetch_from_env(
    system_id: str | None, env: Mapping[str, str] | None = None
) -> AttestationBundle:
    """Fetch the bundle with the environment pair `push` uses (`os.environ` when `env`
    is None). A bundle for another system than `system_id` is refused; with no
    `system_id` the organisation-wide bundle is asked for and taken as it comes."""
    environ = os.environ if env is None else env
    api_key = environ.get("OPENCOMPLAI_API_KEY", "")
    base_url = environ.get("OPENCOMPLAI_DASHBOARD_URL", "")
    if not api_key or not base_url:
        raise AttestationError(
            "not_configured",
            "OPENCOMPLAI_API_KEY and OPENCOMPLAI_DASHBOARD_URL must both be set",
        )
    bundle = fetch_bundle(base_url, api_key, system_id)
    if system_id is not None:
        _check_system(bundle, system_id)
    return bundle
