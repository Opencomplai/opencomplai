"""Tests for CTRL-ASSESS's CLI->vault control register sync (`_sync_controls_to_vault`).

Exercises `gaps` end to end via CliRunner:

* vault-less OSS mode (D11): OPENCOMPLAI_VAULT_URL unset -> no vault traffic
  at all, no "Control register" output.
* vault-configured mode: `_vault_request` is monkeypatched to a fake
  in-memory vault honouring the same GET/PUT semantics as the real
  evidence-vault CTRL-STORE endpoints, and running `gaps` twice is an
  idempotency probe on the control count/ids in that store.
"""

from __future__ import annotations

import json
from pathlib import Path

import opencomplai_cli.main as main_module
from opencomplai_cli.main import app
from opencomplai_core.control_identity import make_control_id
from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack
from typer.testing import CliRunner

runner = CliRunner()

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


def _write_manifest(tmp_path: Path, system_id: str, intended_purpose: str) -> Path:
    manifest_file = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            system_id,
            "--intended-purpose",
            intended_purpose,
            "--output",
            str(manifest_file),
        ],
    )
    assert result.exit_code == 0, f"init failed: {result.output}"
    return manifest_file


class _FakeVault:
    """In-memory stand-in for the evidence-vault CTRL-STORE endpoints.

    Mirrors the real PUT /v1/controls presence-based upsert semantics closely
    enough for an idempotency probe: items are keyed by `control_id` within a
    system's bucket, and a PUT of a previously-seen id overwrites in place
    rather than duplicating.
    """

    def __init__(self) -> None:
        self.controls: dict[str, dict[str, dict]] = {}
        self.fingerprints: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, path: str, body: dict | None = None) -> dict:
        self.calls.append((method, path))

        if method == "GET" and path.startswith("/v1/controls/"):
            system_id = path.rsplit("/", 1)[-1]
            return {"items": list(self.controls.get(system_id, {}).values())}

        if method == "PUT" and path == "/v1/controls":
            assert body is not None
            items = []
            for item in body["items"]:
                bucket = self.controls.setdefault(item["system_id"], {})
                bucket[item["control_id"]] = item
                items.append(item)
            return {"items": items}

        if method == "PUT" and path.startswith("/v1/fingerprints/"):
            assert body is not None
            system_id = path.rsplit("/", 1)[-1]
            self.fingerprints[system_id] = body["fingerprint"]
            return {"fingerprint": body["fingerprint"]}

        raise AssertionError(f"unexpected vault call: {method} {path}")


def test_vault_less_mode_makes_no_vault_calls_and_prints_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENCOMPLAI_VAULT_URL", raising=False)

    def _raise_if_called(*args, **kwargs):
        raise AssertionError("_vault_request must not be called in vault-less mode")

    monkeypatch.setattr(main_module, "_vault_request", _raise_if_called)

    manifest_file = _write_manifest(
        tmp_path, "sys-vaultless", "customer support chatbot"
    )
    result = runner.invoke(
        app,
        ["gaps", "--manifest", str(manifest_file), "--repo-root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Control register" not in result.output


def test_vault_configured_mode_syncs_and_is_idempotent_across_two_runs(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)

    manifest_file = _write_manifest(tmp_path, "sys-vaulted", "customer support chatbot")
    gaps_args = [
        "gaps",
        "--manifest",
        str(manifest_file),
        "--repo-root",
        str(tmp_path),
    ]

    result1 = runner.invoke(app, gaps_args)
    assert result1.exit_code == 0, result1.output
    assert "Control register synced to vault" in result1.output

    bucket_after_first = dict(fake_vault.controls.get("sys-vaulted", {}))
    ids_after_first = set(bucket_after_first.keys())
    assert ids_after_first, "expected at least one control to be derived"

    result2 = runner.invoke(app, gaps_args)
    assert result2.exit_code == 0, result2.output
    assert "Control register synced to vault" in result2.output

    bucket_after_second = fake_vault.controls.get("sys-vaulted", {})
    ids_after_second = set(bucket_after_second.keys())

    assert ids_after_second == ids_after_first
    assert len(bucket_after_second) == len(bucket_after_first)

    assert "sys-vaulted" in fake_vault.fingerprints
    assert fake_vault.fingerprints["sys-vaulted"]


class _FakeRiskEngine:
    """In-memory stand-in for the risk-engine `POST /v1/controls/reassess` call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None]] = []

    def __call__(self, method: str, path: str, body: dict | None = None) -> dict:
        self.calls.append((method, path, body))
        assert method == "POST"
        assert path == "/v1/controls/reassess"
        return {
            "system_id": body["system_id"],
            "stored_fingerprint": None,
            "current_fingerprint": body["current_fingerprint"],
            "manifest_changed": False,
            "stale_controls": [],
            "review_items_enqueued": [],
            "controls_updated": 0,
        }


def test_risk_engine_configured_posts_reassess_and_skips_cli_fingerprint_put(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    monkeypatch.setenv("OPENCOMPLAI_RISK_ENGINE_URL", "http://fake-risk-engine.invalid")
    fake_vault = _FakeVault()
    fake_risk_engine = _FakeRiskEngine()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    monkeypatch.setattr(main_module, "_risk_engine_request", fake_risk_engine)

    manifest_file = _write_manifest(
        tmp_path, "sys-reassess", "customer support chatbot"
    )
    result = runner.invoke(
        app,
        ["gaps", "--manifest", str(manifest_file), "--repo-root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Control register synced to vault" in result.output
    assert "Reassessment: manifest changed=False" in result.output
    assert "Reassessment skipped" not in result.output

    assert len(fake_risk_engine.calls) == 1
    _, _, body = fake_risk_engine.calls[0]
    assert body["system_id"] == "sys-reassess"
    assert body["current_fingerprint"]

    # the CLI must not PUT the fingerprint itself — the reassess endpoint owns that.
    fingerprint_puts = [
        call
        for call in fake_vault.calls
        if call == ("PUT", "/v1/fingerprints/sys-reassess")
    ]
    assert fingerprint_puts == []
    assert "sys-reassess" not in fake_vault.fingerprints


def test_risk_engine_not_configured_cli_puts_fingerprint_and_notes_skip(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    monkeypatch.delenv("OPENCOMPLAI_RISK_ENGINE_URL", raising=False)
    fake_vault = _FakeVault()

    def _raise_if_called(*args, **kwargs):
        raise AssertionError(
            "_risk_engine_request must not be called when unconfigured"
        )

    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    monkeypatch.setattr(main_module, "_risk_engine_request", _raise_if_called)

    manifest_file = _write_manifest(
        tmp_path, "sys-no-reassess", "customer support chatbot"
    )
    result = runner.invoke(
        app,
        ["gaps", "--manifest", str(manifest_file), "--repo-root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Control register synced to vault" in result.output
    assert "Reassessment skipped: OPENCOMPLAI_RISK_ENGINE_URL not set" in result.output

    # existing behaviour preserved: the CLI PUTs the fingerprint itself.
    assert "sys-no-reassess" in fake_vault.fingerprints
    assert fake_vault.fingerprints["sys-no-reassess"]


def test_json_output_is_quiet_but_still_syncs(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)

    manifest_file = _write_manifest(tmp_path, "sys-json", "customer support chatbot")
    result = runner.invoke(
        app,
        [
            "gaps",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(tmp_path),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Control register" not in result.output
    # stdout must still be valid JSON (the dim sync line must not leak into it)
    json.loads(result.stdout)
    assert fake_vault.controls.get("sys-json")


# ---------------------------------------------------------------------------
# CTRL-ARTIFACT: `check --with-gaps` attaches (or omits) the artifact's
# optional `controls` block, sourced from the same derived list synced above.
# ---------------------------------------------------------------------------


def test_check_with_gaps_and_vault_configured_attaches_controls_block(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)

    manifest_file = _write_manifest(
        tmp_path, "sys-check-vault", "customer support chatbot"
    )
    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(tmp_path),
            "--with-gaps",
        ],
    )
    assert result.exit_code == 0, result.output

    artifact = json.loads((tmp_path / "compliance-artifact.json").read_text())
    assert artifact["controls"] is not None

    derived_items = fake_vault.controls.get("sys-check-vault", {})
    assert derived_items, "expected at least one derived control synced to the vault"

    block = artifact["controls"]
    assert set(block["summary"].keys()) == {
        "satisfied",
        "evidence_missing",
        "evidence_stale",
        "pending_review",
        "waived",
    }
    assert sum(block["summary"].values()) == len(derived_items)
    assert {row["control_id"] for row in block["items"]} == set(derived_items.keys())


def test_check_with_gaps_and_no_vault_omits_controls_block(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_VAULT_URL", raising=False)

    manifest_file = _write_manifest(
        tmp_path, "sys-check-novault", "customer support chatbot"
    )
    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(tmp_path),
            "--with-gaps",
        ],
    )
    assert result.exit_code == 0, result.output

    artifact = json.loads((tmp_path / "compliance-artifact.json").read_text())
    assert artifact["controls"] is None


def test_check_without_with_gaps_never_calls_sync_and_omits_controls_block(
    tmp_path, monkeypatch
):
    """No --with-gaps means no gap_report is computed at all, so there is
    nothing to derive controls from — the sync helper must not be invoked and
    the artifact must not fabricate a controls block."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")

    def _raise_if_called(*args, **kwargs):
        raise AssertionError("_sync_controls_to_vault must not run without --with-gaps")

    monkeypatch.setattr(main_module, "_sync_controls_to_vault", _raise_if_called)

    manifest_file = _write_manifest(
        tmp_path, "sys-check-nogaps", "customer support chatbot"
    )
    result = runner.invoke(
        app,
        ["check", "--manifest", str(manifest_file), "--repo-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output

    artifact = json.loads((tmp_path / "compliance-artifact.json").read_text())
    assert artifact["controls"] is None


# ---------------------------------------------------------------------------
# Other frameworks: a native pack adds its own controls (exclusions waived);
# a derived one (NIST AI RMF) adds none.
# ---------------------------------------------------------------------------


def _fixture_manifest(tmp_path: Path, system_id: str, monkeypatch) -> Path:
    monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)
    manifest_file = _write_manifest(tmp_path, system_id, "customer support chatbot")
    manifest = json.loads(manifest_file.read_text())
    manifest["compliance_targets"] = ["EU_AI_ACT", "FIXTURE"]
    manifest["framework_inputs"] = {
        "FIXTURE": {"excluded": {"FIXTURE:REQ-3": "No deployers: internal tool only."}}
    }
    manifest_file.write_text(json.dumps(manifest))
    return manifest_file


def _fixture_ids(system_id: str) -> dict[str, str]:
    return {
        make_control_id("oss-default", system_id, rid): rid
        for rid in ("FIXTURE:REQ-1", "FIXTURE:REQ-2", "FIXTURE:REQ-3")
    }


def test_gaps_syncs_native_framework_controls_and_waives_exclusions(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    manifest_file = _fixture_manifest(tmp_path, "sys-fixture", monkeypatch)
    gaps_args = ["gaps", "--manifest", str(manifest_file), "--repo-root", str(tmp_path)]

    result = runner.invoke(app, [*gaps_args, "--target", "EU_AI_ACT"])
    assert result.exit_code == 0, result.output
    eu_ids = set(fake_vault.controls["sys-fixture"])

    result = runner.invoke(app, gaps_args)
    assert result.exit_code == 0, result.output
    bucket = fake_vault.controls["sys-fixture"]
    fixture_ids = _fixture_ids("sys-fixture")
    assert set(bucket) == eu_ids | set(fixture_ids)
    states = {fixture_ids[cid]: bucket[cid]["state"] for cid in fixture_ids}
    assert states == {
        "FIXTURE:REQ-1": "evidence_missing",
        "FIXTURE:REQ-2": "evidence_missing",
        "FIXTURE:REQ-3": "waived",
    }
    waived = bucket[make_control_id("oss-default", "sys-fixture", "FIXTURE:REQ-3")]
    assert waived["waiver_rationale"] == "No deployers: internal tool only."
    assert waived["article_ref"] == "FIXTURE:REQ-3"


def test_derived_nist_target_adds_no_controls(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    manifest_file = _write_manifest(tmp_path, "sys-nist", "customer support chatbot")
    gaps_args = ["gaps", "--manifest", str(manifest_file), "--repo-root", str(tmp_path)]

    assert runner.invoke(app, gaps_args).exit_code == 0
    eu_ids = set(fake_vault.controls["sys-nist"])
    fake_vault.controls.clear()

    result = runner.invoke(
        app, [*gaps_args, "--target", "EU_AI_ACT", "--target", "NIST_AI_RMF"]
    )
    assert result.exit_code == 0, result.output
    assert set(fake_vault.controls["sys-nist"]) == eu_ids


def test_check_with_gaps_controls_block_includes_native_framework_controls(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    manifest_file = _fixture_manifest(tmp_path, "sys-check-fixture", monkeypatch)

    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(tmp_path),
            "--with-gaps",
        ],
    )
    assert result.exit_code == 0, result.output

    artifact = json.loads((tmp_path / "compliance-artifact.json").read_text())
    items = {row["control_id"]: row for row in artifact["controls"]["items"]}
    assert set(items) == set(fake_vault.controls["sys-check-fixture"])
    fixture_ids = _fixture_ids("sys-check-fixture")
    assert set(fixture_ids) <= set(items)
    waived = make_control_id("oss-default", "sys-check-fixture", "FIXTURE:REQ-3")
    assert items[waived]["state"] == "waived"
    assert artifact["controls"]["summary"]["waived"] == 1
