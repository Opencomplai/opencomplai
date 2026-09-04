"""
Tests for GO-LIVE CORE-4's shared publish layer
(``opencomplai_cli.publish``).

Covers the mapper (``prepare_scan_status_artifact``) field-by-field, the
transport helper (``publish_scan_status``) against mocked HTTP, and --
where the vendored dashboard schema is importable from this test
environment -- an end-to-end structural check that a real repo-root
``compliance-artifact.json`` run through the mapper actually validates
against the widened ``first_scan_status.schema.json`` (G-4). This last
check is deliberately soft (skips rather than fails) when the schema file
or ``jsonschema`` isn't reachable from wherever this suite happens to run,
since packages/cli's own dependency surface intentionally excludes
``jsonschema`` -- the real, hard proof of schema-validity lives in the
cross-package ingest-api test instead
(``dashboard-saas/services/ingest-api/tests/test_core_loop_e2e.py``).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from opencomplai_cli.publish import (
    _resolve_commit_ref,
    envelope_signature,
    prepare_dossier_envelope,
    prepare_scan_status_artifact,
    publish_dossier_envelope,
    publish_scan_status,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# prepare_scan_status_artifact -- pass-through
# ---------------------------------------------------------------------------


class TestPrepareScanStatusArtifactPassThrough:
    def test_evidentiary_fields_pass_through_untouched(self):
        artifact = {
            "install_id": "install-1",
            "system_id": "sys-1",
            "commit_ref": "a" * 40,
            "result": "pass",
            "failed_controls": ["ctrl-1"],
            "evidence_hashes": ["sha256:aaa", "sha256:bbb"],
            "rationale_hash": "sha256:ccc",
            "duration_ms": 42,
            "pending_verifications_count": 1,
            "signature": "base64sig==",
            "scan_summary": {
                "scan_id": "scan1",
                "scanner_version": "1.0.0",
                "severity": "major",
                "report_hash": "sha256:ddd",
            },
            "gap_report": {
                "system_id": "sys-1",
                "commit_ref": "a" * 40,
                "generated_at": "2026-08-06T00:00:00Z",
                "articles": [],
            },
            "eval_summary": {
                "eval_set_id": "es1",
                "eval_set_version": "1",
                "threshold_policy_hash": "sha256:eee",
                "overall_outcome": "pass",
            },
        }
        prepared = prepare_scan_status_artifact(artifact, commit_env={})
        for key, value in artifact.items():
            assert prepared[key] == value, f"{key} was altered by the mapper"

    def test_original_dict_is_not_mutated(self):
        artifact = {"system_id": "s1", "commit_ref": "a" * 40}
        original = dict(artifact)
        prepare_scan_status_artifact(artifact, commit_env={})
        assert artifact == original


# ---------------------------------------------------------------------------
# prepare_scan_status_artifact -- policy_bundle_version synthesis
# ---------------------------------------------------------------------------


class TestPolicyBundleVersion:
    def test_synthesized_when_absent(self):
        prepared = prepare_scan_status_artifact({"system_id": "s1"}, commit_env={})
        assert prepared["policy_bundle_version"].startswith("cli-")

    def test_synthesized_when_empty_string(self):
        prepared = prepare_scan_status_artifact(
            {"system_id": "s1", "policy_bundle_version": ""}, commit_env={}
        )
        assert prepared["policy_bundle_version"].startswith("cli-")

    def test_kept_when_already_present(self):
        prepared = prepare_scan_status_artifact(
            {"system_id": "s1", "policy_bundle_version": "custom-1.2.3"},
            commit_env={},
        )
        assert prepared["policy_bundle_version"] == "custom-1.2.3"


# ---------------------------------------------------------------------------
# prepare_scan_status_artifact -- timestamp synthesis
# ---------------------------------------------------------------------------


class TestTimestamp:
    def test_synthesized_when_absent_is_iso8601_z(self):
        prepared = prepare_scan_status_artifact({"system_id": "s1"}, commit_env={})
        ts = prepared["timestamp"]
        assert ts.endswith("Z")
        # Must round-trip through fromisoformat once the trailing Z is
        # normalised back to +00:00 (the form Python's stdlib accepts).
        from datetime import datetime

        datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def test_kept_when_already_present(self):
        prepared = prepare_scan_status_artifact(
            {"system_id": "s1", "timestamp": "2026-01-01T00:00:00Z"}, commit_env={}
        )
        assert prepared["timestamp"] == "2026-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# _resolve_commit_ref / commit_ref synthesis
# ---------------------------------------------------------------------------


class TestCommitRefResolution:
    def test_kept_when_already_a_real_length_sha(self):
        sha = "abc1234"
        assert _resolve_commit_ref(sha, {}) == sha

    def test_head_literal_is_replaced(self):
        assert _resolve_commit_ref("HEAD", {"GITHUB_SHA": "b" * 40}) == "b" * 40

    def test_too_short_non_head_is_also_replaced(self):
        assert _resolve_commit_ref("abc12", {"GITHUB_SHA": "c" * 40}) == "c" * 40

    def test_github_sha_env_used_when_artifact_commit_ref_unusable(self):
        assert _resolve_commit_ref(None, {"GITHUB_SHA": "d" * 40}) == "d" * 40

    def test_ci_commit_sha_env_used_when_github_sha_absent(self):
        assert _resolve_commit_ref(None, {"CI_COMMIT_SHA": "e" * 40}) == "e" * 40

    def test_github_sha_takes_precedence_over_ci_commit_sha(self):
        env = {"GITHUB_SHA": "f" * 40, "CI_COMMIT_SHA": "g" * 40}
        assert _resolve_commit_ref(None, env) == "f" * 40

    def test_falls_back_to_git_rev_parse_head(self):
        fake_result = MagicMock(returncode=0, stdout="h" * 40 + "\n")
        with patch("subprocess.run", return_value=fake_result) as mock_run:
            resolved = _resolve_commit_ref(None, {})
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["git", "rev-parse", "HEAD"]
        assert resolved == "h" * 40

    def test_falls_back_to_unresolved_when_git_fails(self):
        with patch("subprocess.run", side_effect=OSError("git not found")):
            assert _resolve_commit_ref(None, {}) == "unresolved"

    def test_falls_back_to_unresolved_when_git_returns_nonzero(self):
        fake_result = MagicMock(returncode=128, stdout="")
        with patch("subprocess.run", return_value=fake_result):
            assert _resolve_commit_ref(None, {}) == "unresolved"

    def test_unresolved_literal_passes_min_length_7(self):
        with patch("subprocess.run", side_effect=OSError):
            resolved = _resolve_commit_ref(None, {})
        assert resolved == "unresolved"
        assert len(resolved) >= 7

    def test_repo_dir_is_forwarded_as_cwd_to_git_rev_parse(self):
        """F3: the git fallback must resolve the repo the ARTIFACT lives
        in, not the invoker's own cwd -- opencomplai push can run from
        anywhere and be pointed at an artifact file that lives elsewhere."""
        fake_result = MagicMock(returncode=0, stdout="j" * 40 + "\n")
        with patch("subprocess.run", return_value=fake_result) as mock_run:
            resolved = _resolve_commit_ref(None, {}, repo_dir="/some/other/repo")
        assert mock_run.call_args.kwargs["cwd"] == "/some/other/repo"
        assert resolved == "j" * 40

    def test_repo_dir_defaults_to_none_cwd_when_not_given(self):
        """Preserves pre-F3 behaviour for callers (the CI connectors) that
        never pass repo_dir -- git inherits the caller's own cwd."""
        fake_result = MagicMock(returncode=0, stdout="k" * 40 + "\n")
        with patch("subprocess.run", return_value=fake_result) as mock_run:
            _resolve_commit_ref(None, {})
        assert mock_run.call_args.kwargs["cwd"] is None


class TestPrepareScanStatusArtifactRepoDir:
    def test_repo_dir_forwarded_to_resolve_commit_ref(self):
        fake_result = MagicMock(returncode=0, stdout="m" * 40 + "\n")
        with patch("subprocess.run", return_value=fake_result) as mock_run:
            prepared = prepare_scan_status_artifact(
                {"system_id": "s1"}, commit_env={}, repo_dir="/artifact/dir"
            )
        assert mock_run.call_args.kwargs["cwd"] == "/artifact/dir"
        assert prepared["commit_ref"] == "m" * 40


# ---------------------------------------------------------------------------
# publish_scan_status -- transport
# ---------------------------------------------------------------------------


class TestPublishScanStatus:
    def test_success_returns_status_and_parsed_body(self):
        response = MagicMock()
        response.status = 201
        response.read.return_value = b'{"outcome": "accepted", "content_hash": "abc"}'
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = response
            status, data = publish_scan_status("http://dash.test", "tok", {"a": 1})
        assert status == 201
        assert data == {"outcome": "accepted", "content_hash": "abc"}

    def test_request_shape_matches_original_connector_block(self):
        response = MagicMock(status=201)
        response.read.return_value = b"{}"
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = response
            publish_scan_status("http://dash.test/", "tok", {"system_id": "s1"})
        sent_request = mock_urlopen.call_args[0][0]
        assert sent_request.full_url == "http://dash.test/v1/ingest/scan-status"
        assert sent_request.get_header("Authorization") == "Bearer tok"
        assert sent_request.get_header("Content-type") == "application/json"
        assert json.loads(sent_request.data) == {"system_id": "s1"}
        assert mock_urlopen.call_args.kwargs["timeout"] == 30

    def test_http_error_returns_status_and_parsed_body(self):
        import urllib.error

        exc = urllib.error.HTTPError(
            url="http://dash.test/v1/ingest/scan-status",
            code=422,
            msg="Unprocessable",
            hdrs=None,
            fp=None,
        )
        exc.read = MagicMock(return_value=b'{"error_code": "SCHEMA_VIOLATION"}')
        with patch("urllib.request.urlopen", side_effect=exc):
            status, data = publish_scan_status("http://dash.test", "tok", {})
        assert status == 422
        assert data == {"error_code": "SCHEMA_VIOLATION"}

    def test_network_failure_returns_zero_status_and_error_key(self):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            status, data = publish_scan_status("http://dash.test", "tok", {})
        assert status == 0
        assert "error" in data

    def test_non_json_body_returns_empty_dict_not_a_crash(self):
        response = MagicMock(status=201)
        response.read.return_value = b"not json"
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = response
            status, data = publish_scan_status("http://dash.test", "tok", {})
        assert status == 201
        assert data == {}

    def test_empty_body_returns_empty_dict(self):
        response = MagicMock(status=200)
        response.read.return_value = b""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = response
            status, data = publish_scan_status("http://dash.test", "tok", {})
        assert status == 200
        assert data == {}


# ---------------------------------------------------------------------------
# publish_scan_status -- redirect hardening (F1)
# ---------------------------------------------------------------------------


class TestRedirectHardening:
    def test_no_redirect_handler_declines_every_redirect(self):
        """Unit-level proof of the handler itself: redirect_request always
        returns None, for every 3xx code urllib.request.HTTPRedirectHandler
        dispatches to it, regardless of the Location header offered."""
        from opencomplai_cli.publish import _NoRedirectHandler

        handler = _NoRedirectHandler()
        req = MagicMock()
        req.full_url = "http://dash.test/v1/ingest/scan-status"
        req.get_method.return_value = "POST"
        for code in (301, 302, 303, 307, 308):
            result = handler.redirect_request(
                req,
                fp=MagicMock(),
                code=code,
                msg="Redirect",
                headers={"location": "http://attacker.test/steal"},
                newurl="http://attacker.test/steal",
            )
            assert result is None, f"redirect_request must decline code {code}"

    def test_redirect_surfaces_as_http_error_status_and_transport_not_reinvoked(self):
        """Integration-level proof: with the real installed opener wired
        in (module import time), a 302 response from the underlying HTTP
        transport must come back through publish_scan_status as (302, ...)
        -- exactly like any other error status -- and the transport must
        be invoked exactly once (never a second time against the
        redirect's Location, which is where a stale Authorization header
        would otherwise leak to a different host)."""
        import email.message

        headers = email.message.Message()
        headers["Location"] = "http://attacker.test/steal"

        fake_response = MagicMock()
        fake_response.status = 302
        fake_response.code = 302
        fake_response.reason = "Found"
        fake_response.msg = "Found"
        fake_response.headers = headers
        fake_response.read.return_value = b""

        with patch(
            "urllib.request.AbstractHTTPHandler.do_open", return_value=fake_response
        ) as mock_do_open:
            status, _data = publish_scan_status("http://dash.test", "tok", {"a": 1})

        assert status == 302
        # Exactly one transport call -- no follow-up request was ever made
        # to http://attacker.test.
        mock_do_open.assert_called_once()


# ---------------------------------------------------------------------------
# envelope_signature (F2 / GO-LIVE decision G-5)
# ---------------------------------------------------------------------------


class TestEnvelopeSignature:
    def test_identity_mapping_with_real_signature_is_forwarded(self):
        """The mapper had nothing to add -- the signed bytes are exactly
        what's being sent -- so the signature is safe to forward."""
        artifact = {
            "system_id": "s1",
            "commit_ref": "a" * 40,
            "policy_bundle_version": "cli-0.0.0-test",
            "timestamp": "2026-01-01T00:00:00Z",
            "signature": "base64sig==",
        }
        prepared = prepare_scan_status_artifact(artifact, commit_env={})
        assert prepared == artifact  # sanity: truly an identity mapping
        assert envelope_signature(artifact, prepared) == "base64sig=="

    def test_mutated_mapping_with_real_signature_is_dropped(self):
        """The mapper added policy_bundle_version/timestamp -- the signed
        bytes no longer match what's being sent, so forwarding the
        signature would guarantee a SIGNATURE_INVALID rejection."""
        artifact = {
            "system_id": "s1",
            "commit_ref": "a" * 40,
            "signature": "base64sig==",
        }
        prepared = prepare_scan_status_artifact(artifact, commit_env={})
        assert prepared != artifact  # sanity: the mapper did change something
        assert envelope_signature(artifact, prepared) == ""

    def test_null_signature_is_dropped(self):
        artifact = {"system_id": "s1", "commit_ref": "a" * 40, "signature": None}
        prepared = prepare_scan_status_artifact(artifact, commit_env={})
        assert envelope_signature(artifact, prepared) == ""

    def test_absent_signature_is_dropped(self):
        artifact = {"system_id": "s1", "commit_ref": "a" * 40}
        prepared = prepare_scan_status_artifact(artifact, commit_env={})
        assert envelope_signature(artifact, prepared) == ""

    def test_empty_string_signature_is_dropped(self):
        artifact = {"system_id": "s1", "commit_ref": "a" * 40, "signature": ""}
        prepared = prepare_scan_status_artifact(artifact, commit_env={})
        assert envelope_signature(artifact, prepared) == ""


# ---------------------------------------------------------------------------
# End-to-end structural proof: the real repo-root artifact, prepared,
# validates against the widened vendored schema (soft-skips if unreachable
# from this test environment -- the hard proof lives in ingest-api's own
# cross-package test).
# ---------------------------------------------------------------------------


def _load_widened_schema():
    schema_path = (
        REPO_ROOT / "dashboard-saas" / "schemas" / "first_scan_status.schema.json"
    )
    if not schema_path.exists():
        return None
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_real_repo_root_artifact_prepared_validates_against_widened_schema():
    artifact_path = REPO_ROOT / "compliance-artifact.json"
    if not artifact_path.exists():
        pytest.skip("repo-root compliance-artifact.json not present in this checkout")

    schema = _load_widened_schema()
    if schema is None:
        pytest.skip(
            "dashboard-saas/schemas/first_scan_status.schema.json not reachable"
        )

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not importable from this test environment")

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    prepared = prepare_scan_status_artifact(
        artifact, commit_env={"GITHUB_SHA": "i" * 40}
    )

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(prepared), key=lambda e: e.path)
    assert errors == [], (
        f"prepared artifact still fails the widened schema: {[e.message for e in errors]}"
    )
    # And every evidentiary field is still there -- the whole point of G-4.
    assert prepared["gap_report"] == artifact["gap_report"]
    assert prepared["scan_summary"] == artifact["scan_summary"]
    assert prepared["evidence_hashes"] == artifact["evidence_hashes"]


# ---------------------------------------------------------------------------
# prepare_dossier_envelope (DG-10)
# ---------------------------------------------------------------------------

_SAMPLE_DOSSIER: dict = {
    "dossier_id": "doss-1234",
    "system_id": "sys-acme-loan-approval",
    "commit_ref": "a" * 40,
    "generated_at": "2026-05-18T18:46:11Z",
    "compliance_target": "EU_AI_ACT",
    "bundle_checksum": "sha256:" + "9" * 64,
    "signature": None,
    "signature_status": "unsigned",
    "section1": {"risk_class": "minimal"},
}


class TestPrepareDossierEnvelopeFieldMapping:
    def test_system_id_and_bundle_checksum_and_compliance_target_pass_through(self):
        prepared = prepare_dossier_envelope(_SAMPLE_DOSSIER, commit_env={})
        assert prepared["system_id"] == _SAMPLE_DOSSIER["system_id"]
        assert prepared["bundle_checksum"] == _SAMPLE_DOSSIER["bundle_checksum"]
        assert prepared["compliance_target"] == _SAMPLE_DOSSIER["compliance_target"]

    def test_commit_ref_resolved_like_scan_status(self):
        prepared = prepare_dossier_envelope(
            {**_SAMPLE_DOSSIER, "commit_ref": "HEAD"},
            commit_env={"GITHUB_SHA": "b" * 40},
        )
        assert prepared["commit_ref"] == "b" * 40

    def test_timestamp_uses_generated_at_when_present(self):
        prepared = prepare_dossier_envelope(_SAMPLE_DOSSIER, commit_env={})
        assert prepared["timestamp"] == "2026-05-18T18:46:11Z"

    def test_timestamp_synthesized_when_generated_at_absent(self):
        dossier = {k: v for k, v in _SAMPLE_DOSSIER.items() if k != "generated_at"}
        prepared = prepare_dossier_envelope(dossier, commit_env={})
        ts = prepared["timestamp"]
        assert ts.endswith("Z")
        from datetime import datetime

        datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def test_bundle_checksum_synthesized_when_absent(self):
        dossier = {k: v for k, v in _SAMPLE_DOSSIER.items() if k != "bundle_checksum"}
        prepared = prepare_dossier_envelope(dossier, commit_env={})
        assert prepared["bundle_checksum"].startswith("sha256:")
        assert len(prepared["bundle_checksum"]) == len("sha256:") + 64

    def test_policy_bundle_version_synthesized(self):
        prepared = prepare_dossier_envelope(_SAMPLE_DOSSIER, commit_env={})
        assert prepared["policy_bundle_version"].startswith("cli-")

    def test_result_is_always_generated(self):
        prepared = prepare_dossier_envelope(_SAMPLE_DOSSIER, commit_env={})
        assert prepared["result"] == "generated"

    def test_signed_by_reflects_unsigned_status(self):
        prepared = prepare_dossier_envelope(_SAMPLE_DOSSIER, commit_env={})
        assert prepared["signed_by"] == "cli:unsigned"

    def test_signed_by_reflects_hmac_local_status(self):
        dossier = {**_SAMPLE_DOSSIER, "signature_status": "hmac-local"}
        prepared = prepare_dossier_envelope(dossier, commit_env={})
        assert prepared["signed_by"] == "cli:hmac-local"

    def test_signed_by_defaults_to_unsigned_when_status_absent(self):
        dossier = {k: v for k, v in _SAMPLE_DOSSIER.items() if k != "signature_status"}
        prepared = prepare_dossier_envelope(dossier, commit_env={})
        assert prepared["signed_by"] == "cli:unsigned"

    def test_size_bytes_is_positive_int_and_deterministic(self):
        p1 = prepare_dossier_envelope(_SAMPLE_DOSSIER, commit_env={})
        p2 = prepare_dossier_envelope(_SAMPLE_DOSSIER, commit_env={})
        assert isinstance(p1["size_bytes"], int)
        assert p1["size_bytes"] > 0
        assert p1["size_bytes"] == p2["size_bytes"]

    def test_no_annex_iv_section_content_leaks_into_envelope(self):
        """Unlike prepare_scan_status_artifact's passthrough, the dossier
        envelope must carry ONLY the schema's own fields -- no section1-9
        content, dossier_id, or evidence_hashes (additionalProperties:
        false on the receiving schema would reject any of those)."""
        prepared = prepare_dossier_envelope(_SAMPLE_DOSSIER, commit_env={})
        allowed = {
            "system_id",
            "commit_ref",
            "bundle_checksum",
            "size_bytes",
            "signed_by",
            "timestamp",
            "compliance_target",
            "policy_bundle_version",
            "result",
        }
        assert set(prepared.keys()) <= allowed
        assert "section1" not in prepared
        assert "dossier_id" not in prepared

    def test_original_dict_is_not_mutated(self):
        original = dict(_SAMPLE_DOSSIER)
        prepare_dossier_envelope(_SAMPLE_DOSSIER, commit_env={})
        assert _SAMPLE_DOSSIER == original


# ---------------------------------------------------------------------------
# publish_dossier_envelope -- transport
# ---------------------------------------------------------------------------


class TestPublishDossierEnvelope:
    def test_success_returns_status_and_parsed_body(self):
        response = MagicMock()
        response.status = 201
        response.read.return_value = b'{"outcome": "accepted", "content_hash": "abc"}'
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = response
            status, data = publish_dossier_envelope("http://dash.test", "tok", {"a": 1})
        assert status == 201
        assert data == {"outcome": "accepted", "content_hash": "abc"}

    def test_request_shape_targets_dossier_envelope_path(self):
        response = MagicMock(status=201)
        response.read.return_value = b"{}"
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = response
            publish_dossier_envelope("http://dash.test/", "tok", {"system_id": "s1"})
        sent_request = mock_urlopen.call_args[0][0]
        assert sent_request.full_url == "http://dash.test/v1/ingest/dossier-envelope"
        assert sent_request.get_header("Authorization") == "Bearer tok"
        assert sent_request.get_header("Content-type") == "application/json"
        assert json.loads(sent_request.data) == {"system_id": "s1"}

    def test_http_error_returns_status_and_parsed_body(self):
        import urllib.error

        exc = urllib.error.HTTPError(
            url="http://dash.test/v1/ingest/dossier-envelope",
            code=422,
            msg="Unprocessable",
            hdrs=None,
            fp=None,
        )
        exc.read = MagicMock(return_value=b'{"error_code": "SCHEMA_VIOLATION"}')
        with patch("urllib.request.urlopen", side_effect=exc):
            status, data = publish_dossier_envelope("http://dash.test", "tok", {})
        assert status == 422
        assert data == {"error_code": "SCHEMA_VIOLATION"}

    def test_network_failure_returns_zero_status_and_error_key(self):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            status, data = publish_dossier_envelope("http://dash.test", "tok", {})
        assert status == 0
        assert "error" in data


# ---------------------------------------------------------------------------
# End-to-end structural proof (DG-10 task 4): the prepared envelope
# validates against the vendored dashboard-saas dossier_envelope schema,
# loaded by path -- pins the contract. Soft-skips (never fails) when the
# schema file or jsonschema isn't reachable from this test environment.
# ---------------------------------------------------------------------------


def _load_dossier_envelope_schema():
    schema_path = (
        REPO_ROOT / "dashboard-saas" / "schemas" / "dossier_envelope.schema.json"
    )
    if not schema_path.exists():
        return None
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_prepared_dossier_envelope_validates_against_vendored_schema():
    schema = _load_dossier_envelope_schema()
    if schema is None:
        pytest.skip("dashboard-saas/schemas/dossier_envelope.schema.json not reachable")
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not importable from this test environment")

    prepared = prepare_dossier_envelope(
        _SAMPLE_DOSSIER, commit_env={"GITHUB_SHA": "c" * 40}
    )

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(prepared), key=lambda e: e.path)
    assert errors == [], (
        f"prepared dossier envelope fails the vendored schema: "
        f"{[e.message for e in errors]}"
    )


def test_prepared_dossier_envelope_from_real_generated_dossier_validates(tmp_path):
    """Same structural proof, but starting from a real AnnexIVDossier
    produced by opencomplai_doc_generator's own generate_dossier (rather
    than a hand-built sample dict), the same object docs_generate_cmd's
    local fallback feeds prepare_dossier_envelope in production."""
    schema = _load_dossier_envelope_schema()
    if schema is None:
        pytest.skip("dashboard-saas/schemas/dossier_envelope.schema.json not reachable")
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not importable from this test environment")

    try:
        from opencomplai_core.engine import assess
        from opencomplai_core.models import (
            AssessmentInput,
            ModelMetadata,
            SystemManifest,
        )
        from opencomplai_doc_generator.generator import generate_dossier
    except ImportError:
        pytest.skip(
            "opencomplai_doc_generator not importable from this test environment"
        )

    manifest = SystemManifest(
        system_id="sys-dg10-test",
        intended_purpose="Not specified",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=False,
        commit_ref="HEAD",
    )
    risk_result = assess(
        AssessmentInput(
            model=ModelMetadata(
                name="sys-dg10-test",
                version="HEAD",
                modality="text",
                use_case="Not specified",
                deployment_context="production",
            )
        )
    )
    dossier = generate_dossier(manifest, risk_result, provider_name="Unknown Provider")

    prepared = prepare_dossier_envelope(
        dossier.model_dump(mode="json"), commit_env={"GITHUB_SHA": "d" * 40}
    )

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(prepared), key=lambda e: e.path)
    assert errors == [], (
        f"prepared dossier envelope fails the vendored schema: "
        f"{[e.message for e in errors]}"
    )
