"""Attestation bundles in the CLI: reading one, merging it, and the commands around it.

A bundle is opt-in (`--attestations-file`, `--attestations-remote` or an
`attestations` section in opencomplai.yaml). Without one `check` and `gaps` make no
network call. A file that cannot be used exits 2; an endpoint that cannot be used
warns, the run goes on with the manifest alone, and the artifact records why.
"""

from __future__ import annotations

import base64
import http.server
import json
import re
import threading
import urllib.error
import urllib.request
from datetime import date
from email.message import Message
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from opencomplai_cli import attestations as att
from opencomplai_cli import main
from opencomplai_cli.commands.attestations import (
    EXIT_OK,
    EXIT_PULL_FAILED,
    run_pull,
)
from opencomplai_core.attestation_bundle import (
    AttestationBundle,
    bundle_sha256,
    bundle_signing_bytes,
)
from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack
from opencomplai_core.models import (
    Attestation,
    FrameworkInputs,
    SystemManifest,
)
from opencomplai_core.project_config import ProjectConfig, load_project_config
from typer.testing import CliRunner

FIXTURE_PACK = FrameworkPack(
    "FIXTURE",
    "Fixture framework",
    requirements=Path(__file__).resolve().parents[2]
    / "core"
    / "tests"
    / "fixtures"
    / "framework_pack"
    / "requirements.json",
)
ISO = "ISO_IEC_27001"
ROW = f"{ISO}:A.6.3"
ENV_URL = "http://127.0.0.1:8099/api/ingest"
ARTIFACT = Path("compliance-artifact.json")


# --- bundles ------------------------------------------------------------------


def _record(record_id: str, **over: Any) -> dict[str, Any]:
    return {
        "statement": "Training runs every year.",
        "attested_by": "Jane Doe",
        "attested_at": "2026-06-01",
        "valid_until": "2099-01-01",
        "record_id": record_id,
        **over,
    }


def make_bundle(
    attestations: dict[str, dict[str, dict[str, Any]]] | None = None,
    excluded: dict[str, dict[str, str]] | None = None,
    system_id: str | None = None,
) -> dict[str, Any]:
    """A bundle signed the way an issuer signs it: Ed25519 over the hex digest."""
    raw: dict[str, Any] = {
        "schema_version": "attestation_bundle/v1",
        "system_id": system_id,
        "issued_at": "2026-11-03T09:30:00+00:00",
        "attestations": attestations or {},
        "excluded": excluded or {},
        "key_id": "test-key",
        "signature": "AAAA",
    }
    digest = bundle_sha256(AttestationBundle.model_validate(raw))
    signature = Ed25519PrivateKey.generate().sign(bundle_signing_bytes(digest))
    return {**raw, "signature": base64.b64encode(signature).decode()}


def _write(path: Path, bundle: dict[str, Any]) -> Path:
    path.write_text(json.dumps(bundle), encoding="utf-8")
    return path


def _manifest(**inputs: FrameworkInputs) -> SystemManifest:
    return SystemManifest(
        system_id="sys-1", intended_purpose="credit scoring", framework_inputs=inputs
    )


def _att(**over: Any) -> Attestation:
    base = {
        "statement": "Own statement.",
        "attested_by": "Own Name",
        "attested_at": "2026-01-01",
    }
    return Attestation.model_validate({**base, **over})


# --- a fake endpoint ------------------------------------------------------------


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class Endpoint:
    """Replaces urlopen: serves one body, or fails, and remembers every request."""

    def __init__(self, body: bytes | None = None, error: Exception | None = None):
        self.body, self.error = body, error
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout: float = 0) -> Any:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        assert self.body is not None
        return _Response(self.body)


def serve(monkeypatch: pytest.MonkeyPatch, bundle: dict[str, Any]) -> Endpoint:
    endpoint = Endpoint(body=json.dumps(bundle).encode())
    monkeypatch.setattr(urllib.request, "urlopen", endpoint)
    return endpoint


def fail_with(monkeypatch: pytest.MonkeyPatch, error: Exception) -> Endpoint:
    endpoint = Endpoint(error=error)
    monkeypatch.setattr(urllib.request, "urlopen", endpoint)
    return endpoint


class NetworkUsed(BaseException):
    """Not an Exception, so no `except Exception` in the code under test hides it."""


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any request fails the test."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise NetworkUsed("an attestation run made a network call")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)


# --- load, size caps, urls ------------------------------------------------------


def test_a_bundle_file_loads_and_validates(tmp_path: Path) -> None:
    path = _write(tmp_path / "b.json", make_bundle({ISO: {ROW: _record("r1")}}))
    bundle = att.load_bundle_file(path)
    assert bundle.attestations[ISO][ROW].record_id == "r1"


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"{not json", "invalid_bundle"),
        (b'{"schema_version": "attestation_bundle/v1"}', "invalid_bundle"),
        (b"\xff\xfe\x00", "invalid_bundle"),
    ],
)
def test_a_bad_bundle_file_is_refused_with_a_machine_code(
    tmp_path: Path, content: bytes, code: str
) -> None:
    path = tmp_path / "b.json"
    path.write_bytes(content)
    with pytest.raises(att.AttestationError) as exc:
        att.load_bundle_file(path)
    assert exc.value.code == code
    assert re.fullmatch(r"[a-z0-9_]{1,64}", exc.value.code)


def test_an_email_as_attester_makes_the_bundle_invalid(tmp_path: Path) -> None:
    bundle = make_bundle({ISO: {ROW: _record("r1")}})
    bundle["attestations"][ISO][ROW]["attested_by"] = "jane@example.com"
    with pytest.raises(att.AttestationError, match="attested_by"):
        att.load_bundle_file(_write(tmp_path / "b.json", bundle))


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(att.AttestationError) as exc:
        att.load_bundle_file(tmp_path / "nope.json")
    assert exc.value.code == "read_failed"


def test_a_bundle_file_over_the_cap_is_refused_before_parsing(tmp_path: Path) -> None:
    path = tmp_path / "big.json"
    path.write_bytes(b" " * (att.MAX_BUNDLE_BYTES + 1))
    with pytest.raises(att.AttestationError) as exc:
        att.load_bundle_file(path)
    assert exc.value.code == "bundle_too_large"


def test_a_response_over_the_cap_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Endpoint(body=b" " * (att.MAX_BUNDLE_BYTES + 10))
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    with pytest.raises(att.AttestationError) as exc:
        att.fetch_bundle(ENV_URL, "ock_k", "sys-1")
    assert exc.value.code == "bundle_too_large"


@pytest.mark.parametrize(
    "base",
    [
        "http://dash.example.com/api",
        "http://10.0.0.5/api",
        "http://localhost.evil.test/api",
    ],
)
def test_plain_http_to_a_remote_host_is_refused(base: str) -> None:
    with pytest.raises(att.AttestationError) as exc:
        att.bundle_url(base, "sys-1")
    assert exc.value.code == "http_refused"


@pytest.mark.parametrize(
    "base",
    ["http://localhost:3000/api", "http://127.0.0.1/api", "http://[::1]:8080/api"],
)
def test_plain_http_to_this_machine_is_allowed(base: str) -> None:
    assert att.bundle_url(base, "sys-1").endswith("/v1/attestations?system_id=sys-1")


@pytest.mark.parametrize("base", ["file:///etc/passwd", "ftp://host/x", "no-scheme"])
def test_only_http_and_https_urls_are_fetched(base: str) -> None:
    with pytest.raises(att.AttestationError) as exc:
        att.bundle_url(base, "sys-1")
    assert exc.value.code == "invalid_url"


def test_the_url_names_the_system_and_quotes_it() -> None:
    url = att.bundle_url("https://dash.example.com/api/", "a b/c")
    assert url == "https://dash.example.com/api/v1/attestations?system_id=a%20b%2Fc"
    assert att.bundle_url("https://dash.example.com/api", None) == (
        "https://dash.example.com/api/v1/attestations"
    )


def test_fetch_sends_the_key_like_push_does(monkeypatch: pytest.MonkeyPatch) -> None:
    endpoint = serve(monkeypatch, make_bundle({ISO: {ROW: _record("r1")}}))
    bundle = att.fetch_bundle(ENV_URL, "ock_secret", "sys-1")
    (request,) = endpoint.requests
    assert request.full_url == f"{ENV_URL}/v1/attestations?system_id=sys-1"
    assert request.get_method() == "GET"
    assert request.get_header("Authorization") == "Bearer ock_secret"
    assert bundle.attestations[ISO][ROW].record_id == "r1"


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.HTTPError(ENV_URL, 503, "unavailable", Message(), None),
        urllib.error.URLError("connection refused"),
        TimeoutError("timed out"),
    ],
)
def test_a_failed_request_is_a_fetch_failure(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    fail_with(monkeypatch, error)
    with pytest.raises(att.AttestationError) as exc:
        att.fetch_bundle(ENV_URL, "ock_k", "sys-1")
    assert exc.value.code == "fetch_failed"


@pytest.mark.parametrize(
    "key",
    ["ock_SECRETVALUE\n", "ock_SECRETVALUE\r\n", "ock_SECRET VALUE", "ock_SECRÉTVALUE"],
)
def test_a_key_that_cannot_be_sent_is_refused_and_never_echoed(
    no_network, key: str
) -> None:
    """A newline in the key (a common CI slip) makes http.client quote the whole
    header in its error, so the key is checked before anything is built."""
    with pytest.raises(att.AttestationError) as exc:
        att.fetch_bundle(ENV_URL, key, "sys-1")
    assert exc.value.code == "not_configured"
    assert "VALUE" not in str(exc.value)


def test_an_exception_that_quotes_the_key_is_not_echoed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fail_with(monkeypatch, ValueError("Invalid header value b'Bearer ock_SECRETVALUE'"))
    with pytest.raises(att.AttestationError) as exc:
        att.fetch_bundle(ENV_URL, "ock_k", "sys-1")
    assert exc.value.code == "fetch_failed"
    assert "SECRETVALUE" not in str(exc.value)
    assert "ValueError" in str(exc.value)


def test_a_malformed_url_is_an_invalid_url() -> None:
    with pytest.raises(att.AttestationError) as exc:
        att.bundle_url("https://[bad", "sys-1")
    assert exc.value.code == "invalid_url"


def test_a_redirect_is_not_followed_and_the_key_is_not_replayed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two real local servers: the first answers 302 to the second, which must
    never see a request, let alone the Authorization header."""
    # A proxy in the environment would take the request to 127.0.0.1 and the servers
    # below would never be reached: keep this machine out of its way.
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    seen: list[dict[str, str]] = []

    class Quiet(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            return None

    class Target(Quiet):
        def do_GET(self) -> None:
            seen.append(dict(self.headers))
            self.send_response(200)
            self.end_headers()

    target = http.server.HTTPServer(("127.0.0.1", 0), Target)

    class Redirect(Quiet):
        def do_GET(self) -> None:
            self.send_response(302)
            self.send_header(
                "Location", f"http://127.0.0.1:{target.server_port}/v1/attestations"
            )
            self.end_headers()

    first = http.server.HTTPServer(("127.0.0.1", 0), Redirect)
    servers = (first, target)
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with pytest.raises(att.AttestationError) as exc:
            att.fetch_bundle(
                f"http://127.0.0.1:{first.server_port}/api", "ock_secret", "sys-1"
            )
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
    assert exc.value.code == "fetch_failed"
    assert "302" in str(exc.value)
    assert seen == []


# A payload nested far deeper than the JSON parser allows, well under the size cap.
DEEP = b"[" * 200_000


def test_a_deeply_nested_file_is_refused_with_a_machine_code(tmp_path: Path) -> None:
    assert len(DEEP) < att.MAX_BUNDLE_BYTES
    path = tmp_path / "deep.json"
    path.write_bytes(DEEP)
    with pytest.raises(att.AttestationError) as exc:
        att.load_bundle_file(path)
    assert exc.value.code == "invalid_bundle"


def test_a_deeply_nested_response_is_refused_with_a_machine_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", Endpoint(body=DEEP))
    with pytest.raises(att.AttestationError) as exc:
        att.fetch_bundle(ENV_URL, "ock_k", "sys-1")
    assert exc.value.code == "invalid_bundle"


def test_text_the_bundle_chose_cannot_put_control_characters_in_the_error(
    tmp_path: Path,
) -> None:
    """The validation message quotes a key from the bundle; a hostile endpoint
    must not reach the terminal through it."""
    raw = make_bundle()
    raw["excluded"] = {"SOC_2": {"\x1b[31mSOC_2:CC1.1": " "}}
    with pytest.raises(att.AttestationError) as exc:
        att.load_bundle_file(_write(tmp_path / "b.json", raw))
    assert exc.value.code == "invalid_bundle"
    assert "\x1b" not in str(exc.value)
    assert "\\x1b[31m" in str(exc.value)


# --- merge ------------------------------------------------------------------------


def test_merge_adds_records_to_a_copy_and_returns_the_artifact_ref() -> None:
    manifest = _manifest()
    bundle = AttestationBundle.model_validate(
        make_bundle(
            {ISO: {ROW: _record("r1")}}, {"SOC_2": {"SOC_2:CC1.1": "No office."}}
        )
    )
    merged, warnings, ref = att.merge_into_manifest(manifest, bundle)
    assert warnings == []
    assert merged.framework_inputs[ISO].attested[ROW].record_id == "r1"
    assert merged.framework_inputs["SOC_2"].excluded == {"SOC_2:CC1.1": "No office."}
    assert manifest.framework_inputs == {}  # the original is untouched
    assert ref.sha256 == bundle_sha256(bundle)
    assert ref.signature == bundle.signature
    assert ref.count == 2


def test_the_manifest_wins_on_the_same_id() -> None:
    own = _att()
    manifest = _manifest(
        **{
            ISO: FrameworkInputs(
                attested={ROW: own},
                excluded={f"{ISO}:A.5.1": "Out of scope."},
            )
        }
    )
    bundle = AttestationBundle.model_validate(
        make_bundle(
            {ISO: {ROW: _record("r1"), f"{ISO}:A.5.1": _record("r2")}},
            {ISO: {ROW: "Not for us."}},
        )
    )
    merged, warnings, _ = att.merge_into_manifest(manifest, bundle)
    inputs = merged.framework_inputs[ISO]
    assert inputs.attested[ROW] == own
    assert f"{ISO}:A.5.1" not in inputs.attested
    assert inputs.excluded == {f"{ISO}:A.5.1": "Out of scope."}
    # each bundle record or exclusion the manifest shadows is named, not dropped in silence
    assert warnings == [
        f"'{ISO}:A.5.1': the manifest already records '{ISO}:A.5.1'; "
        "the bundle's record r2 is not used",
        f"'{ROW}': the manifest already records '{ROW}'; the bundle's record r1 is not used",
        f"'{ROW}': the manifest already records this requirement; "
        "the bundle's exclusion is not used",
    ]


def test_a_manifest_that_shadows_nothing_adds_no_warning() -> None:
    manifest = _manifest(**{ISO: FrameworkInputs(attested={ROW: _att()})})
    bundle = AttestationBundle.model_validate(
        make_bundle(
            {ISO: {f"{ISO}:A.5.1": _record("r2")}}, {ISO: {f"{ISO}:A.5.2": "N/A."}}
        )
    )
    merged, warnings, _ = att.merge_into_manifest(manifest, bundle)
    assert warnings == []
    assert set(merged.framework_inputs[ISO].attested) == {ROW, f"{ISO}:A.5.1"}
    assert merged.framework_inputs[ISO].excluded == {f"{ISO}:A.5.2": "N/A."}


def test_unknown_and_non_attestable_ids_are_dropped_with_a_warning() -> None:
    bundle = AttestationBundle.model_validate(
        make_bundle(
            {
                ISO: {ROW: _record("r1"), f"{ISO}:NOPE": _record("r2")},
                "EU_AI_ACT": {"Art. 9": _record("r3")},
                "MADE_UP": {"MADE_UP:1": _record("r4")},
            }
        )
    )
    merged, warnings, _ = att.merge_into_manifest(_manifest(), bundle)
    assert list(merged.framework_inputs[ISO].attested) == [ROW]
    assert "EU_AI_ACT" not in merged.framework_inputs
    assert any("NOPE" in w and "takes an attestation" in w for w in warnings)
    assert any("'Art. 9'" in w for w in warnings)
    assert any("MADE_UP" in w and "unknown framework" in w for w in warnings)


def test_exclusions_apply_only_to_rows_an_attestation_alone_decides() -> None:
    from opencomplai_core.frameworks import attestation_only_ids

    mixed = next(
        rid
        for rid in att.attestable_ids("ISO_IEC_27090")
        if rid not in attestation_only_ids("ISO_IEC_27090")
    )
    assert mixed.startswith("ISO_IEC_27090:")
    bundle = AttestationBundle.model_validate(
        make_bundle(
            excluded={
                "ISO_IEC_27090": {mixed: "Not for us."},
                "EU_AI_ACT": {"Art. 4": "Not for us."},
                "NIST_AI_RMF": {"NIST_AI_RMF:GOVERN 2.2": "Not for us."},
                ISO: {ROW: "Not for us."},
            }
        )
    )
    merged, warnings, _ = att.merge_into_manifest(_manifest(), bundle)
    assert set(merged.framework_inputs) == {ISO}
    assert merged.framework_inputs[ISO].excluded == {ROW: "Not for us."}
    assert len(warnings) == 3
    assert any("EU AI Act takes no exclusions" in w for w in warnings)


def test_a_row_both_attested_and_excluded_in_the_bundle_keeps_the_attestation() -> None:
    bundle = AttestationBundle.model_validate(
        make_bundle({ISO: {ROW: _record("r1")}}, {ISO: {ROW: "Not for us."}})
    )
    merged, warnings, _ = att.merge_into_manifest(_manifest(), bundle)
    assert merged.framework_inputs[ISO].excluded == {}
    assert len(merged.framework_inputs[ISO].attested) == 1
    assert any("both attested and excluded" in w for w in warnings)


@pytest.mark.parametrize("key", ["Art. 4", "EU_AI_ACT:Art. 4"])
def test_eu_art_4_merges_under_the_engines_unprefixed_key(key: str) -> None:
    bundle = AttestationBundle.model_validate(
        make_bundle({"EU_AI_ACT": {key: _record("r1")}})
    )
    merged, warnings, _ = att.merge_into_manifest(_manifest(), bundle)
    assert list(merged.framework_inputs["EU_AI_ACT"].attested) == ["Art. 4"]
    assert warnings == []


def test_two_records_for_one_requirement_keep_the_first_and_say_so() -> None:
    """`Art. 4` and `EU_AI_ACT:Art. 4` are one engine key; the merge must not pick
    the later one silently."""
    bundle = AttestationBundle.model_validate(
        make_bundle(
            {
                "EU_AI_ACT": {
                    "Art. 4": _record("first"),
                    "EU_AI_ACT:Art. 4": _record("second"),
                }
            }
        )
    )
    merged, warnings, _ = att.merge_into_manifest(_manifest(), bundle)
    kept = merged.framework_inputs["EU_AI_ACT"].attested
    assert list(kept) == ["Art. 4"]
    assert kept["Art. 4"].record_id == "first"
    assert len(warnings) == 1
    assert "'EU_AI_ACT:Art. 4'" in warnings[0]
    assert "first is kept" in warnings[0]


def test_a_file_source_without_a_path_is_an_error_not_an_assertion() -> None:
    config = ProjectConfig(attestations_source="file")
    with pytest.raises(att.AttestationError):
        att.load_for_run(
            _manifest(),
            [],
            file_flag=None,
            remote_flag=False,
            config=config,
            today=date(2026, 11, 4),
            warn=lambda message: None,
        )


def test_frameworks_the_run_does_not_target_are_ignored() -> None:
    bundle = AttestationBundle.model_validate(
        make_bundle(
            {
                ISO: {ROW: _record("r1")},
                "SOC_2": {"SOC_2:CC1.1": _record("r2")},
                "EU_AI_ACT": {"Art. 4": _record("r3")},
            }
        )
    )
    merged, warnings, _ = att.merge_into_manifest(_manifest(), bundle, [ISO])
    # The EU AI Act is always evaluated, so its records always apply.
    assert set(merged.framework_inputs) == {ISO, "EU_AI_ACT"}
    assert warnings == []


def test_the_merged_manifest_evaluates_with_the_bundle() -> None:
    from datetime import date

    from opencomplai_core.frameworks import evaluate_targets
    from opencomplai_core.models import GapStatus

    bundle = AttestationBundle.model_validate(
        make_bundle({ISO: {ROW: _record("r1")}, "EU_AI_ACT": {"Art. 4": _record("r2")}})
    )
    merged, _, _ = att.merge_into_manifest(_manifest(), bundle, [ISO])
    reports = evaluate_targets(merged, [ISO], commit_ref="abc", today=date(2026, 11, 4))
    rows = {r.article: r for r in reports[ISO].report.articles}
    assert rows[ROW].status is GapStatus.MET
    assert rows[ROW].evidence_ref == "attestation:Jane Doe@2026-06-01#r1"
    eu = {r.article: r for r in reports["EU_AI_ACT"].report.articles}
    assert eu["Art. 4"].status is GapStatus.MET


# --- sources and flag precedence ----------------------------------------------------


def test_resolve_source_precedence(tmp_path: Path) -> None:
    yaml_remote = tmp_path / "opencomplai.yaml"
    yaml_remote.write_text("attestations:\n  source: remote\n", encoding="utf-8")
    remote_cfg = load_project_config(yaml_remote)
    yaml_file = tmp_path / "other.yaml"
    yaml_file.write_text(
        "attestations:\n  source: file\n  path: bundles/b.json\n", encoding="utf-8"
    )
    file_cfg = load_project_config(yaml_file)
    none_cfg = load_project_config(_write_text(tmp_path / "n.yaml", "scan: {}\n"))

    assert att.resolve_source(None, False, none_cfg) is None
    assert att.resolve_source(None, False, remote_cfg) == att.Source(remote=True)
    assert att.resolve_source(None, False, file_cfg) == att.Source(
        remote=False, path=tmp_path / "bundles" / "b.json"
    )
    flag = Path("mine.json")
    # A flag beats the config, whichever way the config points.
    assert att.resolve_source(flag, False, remote_cfg) == att.Source(False, flag)
    assert att.resolve_source(None, True, file_cfg) == att.Source(remote=True)
    with pytest.raises(ValueError, match="not both"):
        att.resolve_source(flag, True, none_cfg)


def _write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("attestations:\n  source: cloud\n", "remote or file"),
        ("attestations:\n  source: file\n", "path is required"),
        ("attestations:\n  source: remote\n  path: b.json\n", "only to source: file"),
        ("attestations: yes\n", "must be a mapping"),
    ],
)
def test_a_bad_attestations_section_is_refused(
    tmp_path: Path, text: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        load_project_config(_write_text(tmp_path / "opencomplai.yaml", text))


# --- the commands ---------------------------------------------------------------------


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """A temp repo with a chatbot manifest; returns a runner giving the result."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)
    for var in (
        "OPENCOMPLAI_API_URL",
        "OPENCOMPLAI_VAULT_URL",
        "OPENCOMPLAI_RISK_ENGINE_URL",
        "SIGNING_KEY_PRIVATE",
        "OPENCOMPLAI_API_KEY",
        "OPENCOMPLAI_DASHBOARD_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    home = tmp_path / "home"
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", home)
    monkeypatch.setattr(main, "_CONFIG_FILE", home / "config.yaml")
    monkeypatch.setattr(main, "_SIGNING_KEY", home / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", home / "signing.pub")

    def run(*args: str):
        return CliRunner().invoke(main.app, list(args))

    result = run(
        "init",
        "--system-id",
        "att-sys",
        "--intended-purpose",
        "customer support chatbot for an online shop",
    )
    assert result.exit_code == 0, result.output
    return run


def _set_manifest(**fields: object) -> None:
    path = Path("system-manifest.json")
    manifest = json.loads(path.read_text())
    manifest.update(fields)
    path.write_text(json.dumps(manifest, indent=2))


def _artifact() -> dict[str, Any]:
    return json.loads(ARTIFACT.read_text())


def _flat(text: str) -> str:
    return " ".join(text.split())


def _art4_rows(artifact: dict[str, Any]) -> dict[str, Any]:
    return {r["article"]: r for r in artifact["gap_report"]["articles"]}


def _set_env(monkeypatch: pytest.MonkeyPatch, url: str = ENV_URL) -> None:
    monkeypatch.setenv("OPENCOMPLAI_API_KEY", "ock_testkey")
    monkeypatch.setenv("OPENCOMPLAI_DASHBOARD_URL", url)


ART4 = {"EU_AI_ACT": {"Art. 4": _record("rec-art4")}}


def test_by_default_check_and_gaps_make_no_network_call(cli, no_network) -> None:
    _set_manifest(compliance_targets=["EU_AI_ACT", ISO])
    assert cli("check", "--with-gaps").exit_code == 0
    assert "attestation_bundle" not in _artifact()
    assert cli("gaps", "--target", ISO).exit_code == 0
    assert cli("recommend", "--output", "fixes").exit_code == 0


def test_by_default_even_with_credentials_set_nothing_is_fetched(
    cli, no_network, monkeypatch
) -> None:
    _set_env(monkeypatch)
    assert cli("check", "--with-gaps").exit_code == 0
    assert "attestation_bundle" not in _artifact()


def test_check_with_a_bundle_file_merges_it_and_records_it(cli, no_network) -> None:
    path = _write(Path("bundle.json"), make_bundle(ART4))
    bundle = AttestationBundle.model_validate_json(path.read_text())

    result = cli("check", "--with-gaps", "--attestations-file", str(path))

    assert result.exit_code == 0, result.output
    artifact = _artifact()
    row = _art4_rows(artifact)["Art. 4"]
    assert row["status"] == "met"
    assert row["evidence_ref"] == "attestation:Jane Doe@2026-06-01#rec-art4"
    assert artifact["attestation_bundle"] == {
        "sha256": bundle_sha256(bundle),
        "signature": bundle.signature,
        "key_id": "test-key",
        "issued_at": "2026-11-03T09:30:00+00:00",
        "count": 1,
    }


def test_the_artifact_field_is_covered_by_the_artifact_signature(
    cli, no_network
) -> None:
    from opencomplai_core.models import ScanStatusArtifact
    from opencomplai_core.signing import verify_artifact

    path = _write(Path("bundle.json"), make_bundle(ART4))
    result = cli("check", "--attestations-file", str(path), "--sign")
    assert result.exit_code == 0, result.output
    artifact = ScanStatusArtifact.model_validate(_artifact())
    assert artifact.attestation_bundle is not None
    assert verify_artifact(artifact, main._SIGNING_PUB) is True
    tampered = artifact.model_copy(
        update={
            "attestation_bundle": artifact.attestation_bundle.model_copy(
                update={"count": 99}
            )
        }
    )
    assert verify_artifact(tampered, main._SIGNING_PUB) is False


def _without_run_noise(artifact: dict[str, Any]) -> dict[str, Any]:
    """The artifact minus what differs between any two runs (clock and timing)."""
    out = {k: v for k, v in artifact.items() if k not in ("timestamp", "duration_ms")}
    out["gap_report"] = {
        k: v for k, v in artifact["gap_report"].items() if k != "generated_at"
    }
    return out


def test_a_run_with_a_bundle_differs_only_in_the_field_and_the_row_it_attests(
    cli, no_network
) -> None:
    """The whole artifact, not just the gap rows: the bundle adds its block and
    changes the Art. 4 row, and nothing else moves."""
    assert cli("check", "--with-gaps").exit_code == 0
    before = _without_run_noise(_artifact())
    path = _write(Path("bundle.json"), make_bundle(ART4))
    assert cli("check", "--with-gaps", "--attestations-file", str(path)).exit_code == 0
    after = _without_run_noise(_artifact())

    assert "attestation_bundle" not in before
    assert after.pop("attestation_bundle")["count"] == 1
    assert _art4_rows(before)["Art. 4"]["status"] == "unverified"
    assert _art4_rows(after)["Art. 4"]["status"] == "met"
    for artifact in (before, after):
        artifact["gap_report"]["articles"] = [
            row
            for row in artifact["gap_report"]["articles"]
            if row["article"] != "Art. 4"
        ]
    assert before == after


def test_gaps_reads_the_bundle_too(cli, no_network) -> None:
    path = _write(Path("bundle.json"), make_bundle(ART4))
    result = cli("gaps", "--attestations-file", str(path), "--output", "json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)["payload"]
    rows = {r["article"]: r for r in payload["articles"]}
    assert rows["Art. 4"]["status"] == "met"


def test_gaps_hands_a_nist_attestation_from_the_bundle_to_the_nist_report(
    cli, no_network
) -> None:
    def govern_2_2(*extra: str) -> str:
        result = cli("gaps", "--target", "NIST_AI_RMF", "--output", "json", *extra)
        assert result.exit_code == 0, result.output
        report = json.loads(result.stdout)["payload"]["nist_rmf_report"]
        (row,) = (
            r for r in report["subcategories"] if r["subcategory"] == "GOVERN 2.2"
        )
        return row["status"]

    assert govern_2_2() == "unverified"
    nist = {"NIST_AI_RMF": {"NIST_AI_RMF:GOVERN 2.2": _record("rec-nist")}}
    path = _write(Path("bundle.json"), make_bundle(nist))
    assert govern_2_2("--attestations-file", str(path)) == "met"


def test_a_bundle_for_another_system_exits_2(cli, no_network) -> None:
    path = _write(Path("bundle.json"), make_bundle(ART4, system_id="other-sys"))
    result = cli("check", "--attestations-file", str(path))
    assert result.exit_code == 2
    assert "other-sys" in _flat(result.output)
    assert not ARTIFACT.exists()


def test_an_unusable_bundle_file_exits_2(cli, no_network) -> None:
    missing = cli("check", "--attestations-file", "nope.json")
    assert missing.exit_code == 2
    assert "attestations" in missing.output
    Path("bad.json").write_text("{not json", encoding="utf-8")
    assert cli("gaps", "--attestations-file", "bad.json").exit_code == 2
    assert cli("recommend", "--attestations-file", "bad.json").exit_code == 2


def test_a_deeply_nested_bundle_file_exits_2_not_a_traceback(cli, no_network) -> None:
    Path("deep.json").write_bytes(DEEP)
    result = cli("check", "--attestations-file", "deep.json")
    assert result.exit_code == 2
    assert isinstance(result.exception, SystemExit)  # not a RecursionError
    assert "attestations" in result.output


def test_a_deeply_nested_response_is_recorded_unavailable(cli, monkeypatch) -> None:
    _set_env(monkeypatch)
    monkeypatch.setattr(urllib.request, "urlopen", Endpoint(body=DEEP))

    result = cli("check", "--attestations-remote")

    assert result.exit_code == 0, result.output
    assert _artifact()["attestation_bundle"] == {
        "status": "unavailable",
        "reason": "invalid_bundle",
    }


def test_check_fetches_when_asked_and_merges(cli, monkeypatch) -> None:
    _set_env(monkeypatch)
    endpoint = serve(monkeypatch, make_bundle(ART4))

    result = cli("check", "--with-gaps", "--attestations-remote")

    assert result.exit_code == 0, result.output
    (request,) = endpoint.requests
    assert request.full_url == f"{ENV_URL}/v1/attestations?system_id=att-sys"
    assert request.get_header("Authorization") == "Bearer ock_testkey"
    assert _art4_rows(_artifact())["Art. 4"]["status"] == "met"
    assert _artifact()["attestation_bundle"]["count"] == 1


def test_a_failed_fetch_warns_and_the_run_goes_on(cli, monkeypatch) -> None:
    _set_env(monkeypatch)
    fail_with(monkeypatch, urllib.error.URLError("connection refused"))

    result = cli("check", "--with-gaps", "--attestations-remote")

    assert result.exit_code == 0, result.output
    assert "fetch_failed" in _flat(result.output)
    artifact = _artifact()
    assert artifact["attestation_bundle"] == {
        "status": "unavailable",
        "reason": "fetch_failed",
    }
    assert _art4_rows(artifact)["Art. 4"]["status"] == "unverified"


@pytest.mark.parametrize(
    ("env", "reason"),
    [
        ({}, "not_configured"),
        ({"OPENCOMPLAI_API_KEY": "k"}, "not_configured"),
        (
            {
                "OPENCOMPLAI_API_KEY": "k",
                "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test/a",
            },
            "http_refused",
        ),
    ],
)
def test_a_remote_that_cannot_be_asked_is_recorded_unavailable(
    cli, no_network, monkeypatch, env, reason
) -> None:
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    result = cli("check", "--attestations-remote")

    assert result.exit_code == 0, result.output
    unavailable = _artifact()["attestation_bundle"]
    assert unavailable == {"status": "unavailable", "reason": reason}
    assert re.fullmatch(r"[a-z0-9_]{1,64}", unavailable["reason"])


def test_the_key_is_never_sent_over_plain_http_to_a_remote_host(
    cli, no_network, monkeypatch
) -> None:
    _set_env(monkeypatch, "http://dash.test/api")
    result = cli("check", "--attestations-remote")
    assert result.exit_code == 0
    assert "http_refused" in _flat(result.output)  # and no_network saw no request


def test_a_malformed_key_is_not_printed_by_any_command(
    cli, no_network, monkeypatch
) -> None:
    _set_env(monkeypatch)
    monkeypatch.setenv("OPENCOMPLAI_API_KEY", "ock_SECRETVALUE\n")

    checked = cli("check", "--attestations-remote")
    assert checked.exit_code == 0, checked.output
    assert "SECRETVALUE" not in checked.output
    assert _artifact()["attestation_bundle"] == {
        "status": "unavailable",
        "reason": "not_configured",
    }
    for args in (("gaps",), ("recommend", "--output", "fixes")):
        result = cli(*args, "--attestations-remote")
        assert result.exit_code == 0, result.output
        assert "not_configured" in _flat(result.output)
        assert "SECRETVALUE" not in result.output

    pulled = cli("attestations", "pull", "-o", "b.json", "--system-id", "att-sys")
    assert pulled.exit_code == 3
    assert "SECRETVALUE" not in pulled.output
    assert not Path("b.json").exists()


def test_a_malformed_endpoint_url_never_crashes_a_command(
    cli, no_network, monkeypatch
) -> None:
    _set_env(monkeypatch, "https://[bad")

    result = cli("check", "--attestations-remote")
    assert result.exit_code == 0, result.output
    assert _artifact()["attestation_bundle"] == {
        "status": "unavailable",
        "reason": "invalid_url",
    }

    pulled = cli("attestations", "pull", "-o", "b.json")
    assert pulled.exit_code == 3
    assert isinstance(pulled.exception, SystemExit)  # not a ValueError traceback


def test_gaps_and_recommend_fetch_when_asked_and_merge(cli, monkeypatch) -> None:
    _set_env(monkeypatch)
    endpoint = serve(monkeypatch, make_bundle(ART4))

    gaps = cli("gaps", "--attestations-remote", "--output", "json")
    assert gaps.exit_code == 0, gaps.output
    rows = {r["article"]: r for r in json.loads(gaps.stdout)["payload"]["articles"]}
    assert rows["Art. 4"]["status"] == "met"
    assert len(endpoint.requests) == 1

    recommend = cli("recommend", "--attestations-remote", "--output", "fixes")
    assert recommend.exit_code == 0, recommend.output
    assert len(endpoint.requests) == 2


def test_the_config_can_ask_for_the_remote_and_a_flag_overrides_it(
    cli, monkeypatch
) -> None:
    _set_env(monkeypatch)
    Path("opencomplai.yaml").write_text(
        "attestations:\n  source: remote\n", encoding="utf-8"
    )
    endpoint = serve(monkeypatch, make_bundle(ART4))
    assert cli("check", "--with-gaps").exit_code == 0
    assert len(endpoint.requests) == 1
    assert _art4_rows(_artifact())["Art. 4"]["status"] == "met"

    # --attestations-file beats source: remote: no second request.
    path = _write(Path("mine.json"), make_bundle({}))
    assert cli("check", "--with-gaps", "--attestations-file", str(path)).exit_code == 0
    assert len(endpoint.requests) == 1
    assert _art4_rows(_artifact())["Art. 4"]["status"] == "unverified"
    assert _artifact()["attestation_bundle"]["count"] == 0


def test_the_config_can_name_a_file_relative_to_itself(cli, no_network) -> None:
    Path("bundles").mkdir()
    _write(Path("bundles/b.json"), make_bundle(ART4))
    Path("opencomplai.yaml").write_text(
        "attestations:\n  source: file\n  path: bundles/b.json\n", encoding="utf-8"
    )
    assert cli("check", "--with-gaps").exit_code == 0
    assert _art4_rows(_artifact())["Art. 4"]["status"] == "met"

    # --attestations-remote beats source: file.
    result = cli("check", "--attestations-remote")
    assert result.exit_code == 0
    assert _artifact()["attestation_bundle"]["reason"] == "not_configured"


def test_both_flags_together_are_a_usage_error(cli, no_network) -> None:
    path = _write(Path("bundle.json"), make_bundle({}))
    result = cli("check", "--attestations-file", str(path), "--attestations-remote")
    assert result.exit_code == 2
    assert "not both" in _flat(result.output)


def test_an_old_undated_attestation_prints_a_staleness_warning(cli, no_network) -> None:
    _set_manifest(
        compliance_targets=["EU_AI_ACT", ISO],
        framework_inputs={
            ISO: {
                "attested": {
                    ROW: {
                        "statement": "Training runs every year.",
                        "attested_by": "Jane Doe",
                        "attested_at": "2020-01-01",
                    }
                }
            }
        },
    )
    result = cli("gaps", "--target", ISO)
    assert result.exit_code == 0
    assert f"{ROW}: attested on 2020-01-01" in _flat(result.output)
    # A dated one is not stale.
    dated = json.loads(Path("system-manifest.json").read_text())
    dated["framework_inputs"][ISO]["attested"][ROW]["valid_until"] = "2099-01-01"
    Path("system-manifest.json").write_text(json.dumps(dated))
    assert "attested on" not in cli("gaps", "--target", ISO).output


def test_warnings_from_a_bundle_are_printed_and_never_break_markup(
    cli, no_network
) -> None:
    path = _write(
        Path("bundle.json"),
        make_bundle({ISO: {"ISO_IEC_27001:[red]x[/red]": _record("r1")}}),
    )
    result = cli("gaps", "--target", ISO, "--attestations-file", str(path))
    assert result.exit_code == 0
    assert "[red]x[/red]" in _flat(result.output)


# --- the unverified gate ---------------------------------------------------------------


@pytest.fixture
def gated(cli):
    """EU AI Act + FIXTURE with REQ-1 and REQ-3 excluded, so the only row left that
    can fail the gate is REQ-2, which only an attestation can decide."""
    _set_manifest(
        compliance_targets=["EU_AI_ACT", "FIXTURE"],
        framework_inputs={
            "FIXTURE": {
                "excluded": {
                    "FIXTURE:REQ-1": "No risk register: internal tool.",
                    "FIXTURE:REQ-3": "No deployers: internal tool.",
                }
            }
        },
    )
    return cli


def test_the_unverified_gate_fails_until_the_bundle_attests_the_row(
    gated, no_network
) -> None:
    result = gated("check", "--gate", "FIXTURE", "--gate-fail-on", "unverified")
    assert result.exit_code == 1, result.output
    assert _artifact()["failed_controls"] == ["FIXTURE:REQ-2"]

    # The lower levels never fail an unattested row.
    assert gated("check", "--gate", "FIXTURE").exit_code == 0

    path = _write(
        Path("bundle.json"), make_bundle({"FIXTURE": {"FIXTURE:REQ-2": _record("r2")}})
    )
    result = gated(
        "check",
        "--gate",
        "FIXTURE",
        "--gate-fail-on",
        "unverified",
        "--attestations-file",
        str(path),
    )
    assert result.exit_code == 0, result.output
    assert _artifact()["failed_controls"] == []


def test_the_unverified_gate_follows_the_endpoint_when_it_is_asked_directly(
    gated, monkeypatch
) -> None:
    """Why the docs tell a gated job to pull the bundle in its own step: with
    --attestations-remote an endpoint that is down drops the attested rows."""
    _set_env(monkeypatch)
    bundle = make_bundle({"FIXTURE": {"FIXTURE:REQ-2": _record("r2")}})
    args = (
        "check",
        "--gate",
        "FIXTURE",
        "--gate-fail-on",
        "unverified",
        "--attestations-remote",
    )
    serve(monkeypatch, bundle)
    assert gated(*args).exit_code == 0
    assert _artifact()["failed_controls"] == []

    fail_with(monkeypatch, urllib.error.URLError("down"))
    assert gated(*args).exit_code == 1
    assert _artifact()["failed_controls"] == ["FIXTURE:REQ-2"]


def test_an_expired_bundle_record_fails_the_unverified_gate_again(
    gated, no_network
) -> None:
    path = _write(
        Path("bundle.json"),
        make_bundle(
            {"FIXTURE": {"FIXTURE:REQ-2": _record("r2", valid_until="2026-01-01")}}
        ),
    )
    result = gated(
        "check",
        "--gate",
        "FIXTURE",
        "--gate-fail-on",
        "unverified",
        "--attestations-file",
        str(path),
    )
    assert result.exit_code == 1
    assert _artifact()["failed_controls"] == ["FIXTURE:REQ-2"]


def test_the_gate_level_can_come_from_the_config(gated, no_network) -> None:
    Path("opencomplai.yaml").write_text(
        "gate:\n  frameworks: [FIXTURE]\n  fail_on: unverified\n", encoding="utf-8"
    )
    assert gated("check").exit_code == 1
    result = gated("gaps", "--target", "FIXTURE")
    assert "Missing, Partial or unattested" in _flat(result.output)


def test_the_gate_help_names_the_unverified_level() -> None:
    import typer.main

    check = typer.main.get_command(main.app).commands["check"]
    option = next(p for p in check.params if p.name == "gate_fail_on")
    assert "missing (default), partial or unverified" in option.help


def test_a_bad_gate_level_is_still_refused(gated) -> None:
    result = gated("check", "--gate", "FIXTURE", "--gate-fail-on", "everything")
    assert result.exit_code == 2
    assert "missing, partial, unverified" in _flat(result.output)


# --- recommend and docs generate --------------------------------------------------------


def test_docs_generate_reads_the_bundle_when_it_evaluates_iso_27090(cli) -> None:
    _set_manifest(compliance_targets=["EU_AI_ACT", "ISO_IEC_27090"])
    result = cli(
        "docs",
        "generate",
        "--system-id",
        "att-sys",
        "--manifest",
        "system-manifest.json",
        "--attestations-file",
        "nope.json",
    )
    assert result.exit_code == 2
    assert "attestations" in result.output


def test_docs_generate_puts_the_bundle_into_the_cybersecurity_section(
    cli, no_network
) -> None:
    _set_manifest(compliance_targets=["EU_AI_ACT", "ISO_IEC_27090"])
    row = "ISO_IEC_27090:5.1"
    path = _write(
        Path("bundle.json"),
        make_bundle({"ISO_IEC_27090": {row: _record("rec-sec")}}),
    )

    def status_of_row(out: str, *extra: str) -> str:
        result = cli(
            "docs", "generate", "--system-id", "att-sys",
            "--manifest", "system-manifest.json", "--output-dir", out, *extra,
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        (written,) = Path(out).glob("dossier_*.json")
        entries = json.loads(written.read_text())["cybersecurity"]["entries"]
        return {e["clause_id"]: e for e in entries}[row]["status"]

    assert status_of_row("plain") == "unverified"
    assert status_of_row("merged", "--attestations-file", str(path)) == "met"


def test_a_bundle_flag_the_run_will_not_use_says_so(
    cli, no_network, monkeypatch
) -> None:
    gaps = cli("gaps", "--output", "json")
    assert gaps.exit_code == 0, gaps.output
    Path("gap.json").write_text(gaps.stdout, encoding="utf-8")
    # recommend with a gap report: nothing is evaluated, so no bundle is read.
    result = cli(
        "recommend", "--gap-report", "gap.json", "--attestations-file", "nope.json",
        "--output", "fixes",
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "ignored: a gap report was supplied" in _flat(result.output)

    docs = (
        "docs", "generate", "--system-id", "att-sys", "--manifest",
        "system-manifest.json", "--attestations-file", "nope.json",
        "--output-dir", "out",
    )  # fmt: skip
    # docs generate with no ISO_IEC_27090 target: the flag has nothing to feed.
    result = cli(*docs)
    assert result.exit_code == 0, result.output
    assert "do not include ISO_IEC_27090" in _flat(result.output)

    # docs generate through the service: it evaluates no framework.
    monkeypatch.setenv("OPENCOMPLAI_API_URL", "http://svc.invalid")
    monkeypatch.setattr(
        main, "_call_service", lambda path, payload: (200, {"dossier_id": "d"})
    )
    result = cli(*docs)
    assert result.exit_code == 0, result.output
    assert "routes generation through the service" in _flat(result.output)

    # And a run that gets no flag says nothing about it.
    monkeypatch.delenv("OPENCOMPLAI_API_URL")
    quiet = cli(*docs[:-4], "--output-dir", "out")
    assert "ignored" not in quiet.output


# --- attestations pull ------------------------------------------------------------------


def test_pull_writes_the_fetched_bundle_as_pretty_json(tmp_path, monkeypatch) -> None:
    raw = make_bundle({ISO: {ROW: _record("r1")}})
    endpoint = serve(monkeypatch, raw)
    out = tmp_path / "out" / "bundle.json"
    env = {"OPENCOMPLAI_API_KEY": "ock_k", "OPENCOMPLAI_DASHBOARD_URL": ENV_URL}

    assert run_pull(out, "sys-1", env=env) == EXIT_OK

    (request,) = endpoint.requests
    assert request.full_url.endswith("/v1/attestations?system_id=sys-1")
    text = out.read_text(encoding="utf-8")
    assert text.startswith("{\n  ")
    written = AttestationBundle.model_validate_json(text)
    # The same bundle: hash and signature survive the round trip.
    assert bundle_sha256(written) == bundle_sha256(
        AttestationBundle.model_validate(raw)
    )
    assert written.signature == raw["signature"]
    # And it is what `check --attestations-file` reads.
    assert att.load_bundle_file(out).attestations[ISO][ROW].record_id == "r1"


def test_pull_without_a_system_asks_for_the_organisation_wide_bundle(
    tmp_path, monkeypatch
) -> None:
    endpoint = serve(monkeypatch, make_bundle({}))
    env = {"OPENCOMPLAI_API_KEY": "ock_k", "OPENCOMPLAI_DASHBOARD_URL": ENV_URL}
    assert run_pull(tmp_path / "b.json", env=env) == EXIT_OK
    assert endpoint.requests[0].full_url == f"{ENV_URL}/v1/attestations"


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"OPENCOMPLAI_API_KEY": "k"},
        {"OPENCOMPLAI_API_KEY": "k", "OPENCOMPLAI_DASHBOARD_URL": "http://dash.test/a"},
    ],
)
def test_pull_fails_with_exit_3_and_writes_nothing(tmp_path, no_network, env) -> None:
    out = tmp_path / "b.json"
    assert run_pull(out, "sys-1", env=env) == EXIT_PULL_FAILED
    assert not out.exists()


def test_pull_fails_with_exit_3_when_the_endpoint_does(tmp_path, monkeypatch) -> None:
    fail_with(monkeypatch, urllib.error.URLError("down"))
    env = {"OPENCOMPLAI_API_KEY": "ock_k", "OPENCOMPLAI_DASHBOARD_URL": ENV_URL}
    out = tmp_path / "b.json"
    assert run_pull(out, "sys-1", env=env) == EXIT_PULL_FAILED
    assert not out.exists()


def test_pull_of_a_deeply_nested_response_exits_3(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", Endpoint(body=DEEP))
    env = {"OPENCOMPLAI_API_KEY": "ock_k", "OPENCOMPLAI_DASHBOARD_URL": ENV_URL}
    out = tmp_path / "b.json"
    assert run_pull(out, "sys-1", env=env) == EXIT_PULL_FAILED
    assert not out.exists()


def test_pull_refuses_a_bundle_for_another_system(tmp_path, monkeypatch) -> None:
    serve(monkeypatch, make_bundle({}, system_id="other-sys"))
    env = {"OPENCOMPLAI_API_KEY": "ock_k", "OPENCOMPLAI_DASHBOARD_URL": ENV_URL}
    out = tmp_path / "b.json"
    assert run_pull(out, "sys-1", env=env) == EXIT_PULL_FAILED
    assert not out.exists()
    # The bundle for the system that was asked for is written.
    serve(monkeypatch, make_bundle({}, system_id="sys-1"))
    assert run_pull(out, "sys-1", env=env) == EXIT_OK
    assert out.is_file()


def test_a_portfolio_run_gives_every_system_the_bundle(cli, no_network) -> None:
    for name in ("a", "b"):
        result = cli(
            "init", "--system-id", f"sys-{name}", "--intended-purpose", "chatbot",
            "--output", f"{name}.json",
        )  # fmt: skip
        assert result.exit_code == 0, result.output
    bundle = _write(Path("org.json"), make_bundle(ART4))  # organisation-wide

    result = cli(
        "check", "-m", "a.json", "-m", "b.json", "--output-dir", "out",
        "--attestations-file", str(bundle),
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    for name in ("a", "b"):
        data = json.loads(Path(f"out/sys-{name}/compliance-artifact.json").read_text())
        assert data["attestation_bundle"]["count"] == 1


def test_pull_is_a_registered_command(cli, monkeypatch) -> None:
    _set_env(monkeypatch)
    serve(monkeypatch, make_bundle({}))
    result = cli("attestations", "pull", "-o", "pulled.json", "--system-id", "att-sys")
    assert result.exit_code == 0, result.output
    assert Path("pulled.json").is_file()
    # The run it feeds: a pulled file replays without a network.
    assert cli("check", "--attestations-file", "pulled.json").exit_code == 0
