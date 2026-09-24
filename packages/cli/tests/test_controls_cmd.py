"""Tests for CTRL-CLI's `opencomplai controls` command group.

Fixture style copied from `test_controls_sync.py`: `_vault_request` is
monkeypatched with a fake in-memory vault honouring the same GET/PUT/POST
semantics as the real evidence-vault CTRL-STORE + evidence-objects
endpoints, and `OPENCOMPLAI_VAULT_URL` is set so `_vault_configured()` is
True for every test except the vault-less-mode probe.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import opencomplai_cli.main as main_module
from opencomplai_cli.main import app
from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack
from typer.testing import CliRunner

runner = CliRunner()

SYSTEM_ID = "sys-controls"
TENANT_ID = "oss-default"

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


def _control(
    control_id: str,
    *,
    article_ref: str = "Art. 9",
    state: str = "evidence_missing",
    owner: str | None = None,
    evidence_refs: list[str] | None = None,
    ttl_days: int | None = None,
    last_evidence_at: str | None = None,
    due_at: str | None = None,
    waiver_rationale: str | None = None,
) -> dict:
    return {
        "control_id": control_id,
        "tenant_id": TENANT_ID,
        "system_id": SYSTEM_ID,
        "obligation_id": article_ref,
        "article_ref": article_ref,
        "owner": owner,
        "state": state,
        "evidence_refs": evidence_refs or [],
        "ttl_days": ttl_days,
        "last_assessed_at": "2026-01-01T00:00:00+00:00",
        "last_evidence_at": last_evidence_at,
        "due_at": due_at,
        "waiver_rationale": waiver_rationale,
    }


class _FakeVault:
    """In-memory stand-in for the evidence-vault CTRL-STORE + evidence-objects
    endpoints. Controls are keyed by (system_id, control_id); evidence
    objects are keyed by their computed content hash."""

    def __init__(self) -> None:
        self.controls: dict[str, dict[str, dict]] = {}
        self.evidence: dict[str, bytes] = {}
        self.calls: list[tuple[str, str]] = []

    def seed(self, *controls: dict) -> None:
        for control in controls:
            bucket = self.controls.setdefault(control["system_id"], {})
            bucket[control["control_id"]] = dict(control)

    def __call__(self, method: str, path: str, body: dict | None = None) -> dict:
        self.calls.append((method, path))

        if method == "GET" and path.startswith("/v1/controls/"):
            system_id = path.split("/v1/controls/", 1)[1]
            state_filter = None
            if "?state=" in system_id:
                system_id, _, state_filter = system_id.partition("?state=")
            items = list(self.controls.get(system_id, {}).values())
            if state_filter is not None:
                items = [i for i in items if i["state"] == state_filter]
            return {"items": items}

        if method == "PUT" and path == "/v1/controls":
            assert body is not None
            items = []
            for patch in body["items"]:
                system_bucket = None
                for bucket in self.controls.values():
                    if patch["control_id"] in bucket:
                        system_bucket = bucket
                        break
                assert system_bucket is not None, (
                    f"unknown control {patch['control_id']}"
                )
                existing = system_bucket[patch["control_id"]]
                existing.update(patch)
                items.append(existing)
            return {"items": items}

        if method == "POST" and path == "/v1/evidence/objects":
            assert body is not None
            content = base64.b64decode(body["content_base64"])
            content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
            self.evidence[content_hash] = content
            return {
                "content_hash": content_hash,
                "storage_uri": f"cas://{content_hash}",
                "source": body.get("source"),
                "source_version": body.get("source_version"),
                "collected_at": body.get("collected_at"),
                "valid_until": body.get("valid_until"),
            }

        raise AssertionError(f"unexpected vault call: {method} {path}")


def test_vault_less_mode_exits_2_with_message(monkeypatch):
    monkeypatch.delenv("OPENCOMPLAI_VAULT_URL", raising=False)

    result = runner.invoke(app, ["controls", "status", "--system-id", SYSTEM_ID])

    assert result.exit_code == 2
    assert "OPENCOMPLAI_VAULT_URL" in result.output


def test_list_human_and_json_flag_ttl_stale_control(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)

    stale_due = "2020-01-01T00:00:00+00:00"
    fake_vault.seed(
        _control(
            "ctrl-stale",
            state="satisfied",
            evidence_refs=["sha256:aaaa"],
            last_evidence_at=stale_due,
            due_at=stale_due,
        ),
        _control("ctrl-missing", article_ref="Art. 10"),
    )

    result = runner.invoke(app, ["controls", "list", "--system-id", SYSTEM_ID])
    assert result.exit_code == 0, result.output
    assert "ctrl-stale"[:12] in result.output
    # The narrow test terminal wraps/truncates the "yes (ttl_expired)" cell
    # across lines — the exact unwrapped string is asserted precisely via
    # the JSON payload below, so here just confirm the fragments render.
    assert "yes" in result.output
    assert "ttl_expire" in result.output

    json_result = runner.invoke(
        app, ["controls", "list", "--system-id", SYSTEM_ID, "--output", "json"]
    )
    assert json_result.exit_code == 0, json_result.output
    payload = json.loads(json_result.stdout)
    assert payload["system_id"] == SYSTEM_ID
    assert payload["stale_count"] == 1
    by_id = {c["control_id"]: c for c in payload["controls"]}
    assert by_id["ctrl-stale"]["stale"] is True
    assert by_id["ctrl-stale"]["stale_reason"] == "ttl_expired"
    assert by_id["ctrl-missing"]["stale"] is False
    assert by_id["ctrl-missing"]["stale_reason"] is None
    assert payload["summary"]["evidence_missing"] == 1
    assert payload["summary"]["satisfied"] == 1


def test_assign_patches_owner_and_ttl_only(monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    fake_vault.seed(_control("ctrl-assign"))

    result = runner.invoke(
        app,
        [
            "controls",
            "assign",
            "ctrl-assign",
            "--system-id",
            SYSTEM_ID,
            "--owner",
            "alice@example.com",
            "--ttl-days",
            "30",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "alice@example.com" in result.output

    stored = fake_vault.controls[SYSTEM_ID]["ctrl-assign"]
    assert stored["owner"] == "alice@example.com"
    assert stored["ttl_days"] == 30
    # state/evidence_refs untouched by a partial patch
    assert stored["state"] == "evidence_missing"
    assert stored["evidence_refs"] == []

    put_calls = [c for c in fake_vault.calls if c == ("PUT", "/v1/controls")]
    assert len(put_calls) == 1


def test_assign_unknown_control_exits_2(monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    fake_vault.seed(_control("ctrl-real"))

    result = runner.invoke(
        app,
        [
            "controls",
            "assign",
            "ctrl-ghost",
            "--system-id",
            SYSTEM_ID,
            "--owner",
            "alice@example.com",
        ],
    )

    assert result.exit_code == 2
    assert "not found" in result.output


def test_attach_evidence_binds_hash_and_flips_to_satisfied(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    fake_vault.seed(_control("ctrl-attach", article_ref="Art. 9"))

    evidence_file = tmp_path / "policy.pdf"
    evidence_file.write_bytes(b"risk management policy v1")

    result = runner.invoke(
        app,
        [
            "controls",
            "attach-evidence",
            "ctrl-attach",
            str(evidence_file),
            "--system-id",
            SYSTEM_ID,
            "--source",
            "manual-upload",
            "--source-version",
            "1.0",
        ],
    )

    assert result.exit_code == 0, result.output

    expected_hash = f"sha256:{hashlib.sha256(evidence_file.read_bytes()).hexdigest()}"
    assert expected_hash[:19] in result.output
    assert "state satisfied" in result.output

    stored = fake_vault.controls[SYSTEM_ID]["ctrl-attach"]
    assert stored["evidence_refs"] == [expected_hash]
    assert stored["state"] == "satisfied"
    assert stored["last_evidence_at"]
    # Art. 9 has a catalog TTL, so due_at must be computed.
    assert stored["due_at"]

    assert expected_hash in fake_vault.evidence
    post_calls = [c for c in fake_vault.calls if c == ("POST", "/v1/evidence/objects")]
    assert len(post_calls) == 1


def test_attach_evidence_missing_file_exits_2(monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    fake_vault.seed(_control("ctrl-attach"))

    result = runner.invoke(
        app,
        [
            "controls",
            "attach-evidence",
            "ctrl-attach",
            "no-such-file.pdf",
            "--system-id",
            SYSTEM_ID,
        ],
    )

    assert result.exit_code == 2
    assert "not found" in result.output


def test_attach_evidence_on_waived_control_leaves_state_waived(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    fake_vault.seed(
        _control(
            "ctrl-waived",
            state="waived",
            waiver_rationale="Accepted residual risk.",
        )
    )

    evidence_file = tmp_path / "note.txt"
    evidence_file.write_text("informational only")

    result = runner.invoke(
        app,
        [
            "controls",
            "attach-evidence",
            "ctrl-waived",
            str(evidence_file),
            "--system-id",
            SYSTEM_ID,
        ],
    )

    assert result.exit_code == 0, result.output
    assert "state waived" in result.output

    stored = fake_vault.controls[SYSTEM_ID]["ctrl-waived"]
    assert stored["state"] == "waived"
    # evidence still bound, even though state wasn't flipped
    assert stored["evidence_refs"]
    assert stored["last_evidence_at"]


def test_status_exit_1_with_a_missing_control(monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    fake_vault.seed(_control("ctrl-missing"))

    result = runner.invoke(app, ["controls", "status", "--system-id", SYSTEM_ID])

    assert result.exit_code == 1
    assert "1 evidence_missing" in result.output


def test_status_exit_0_when_all_satisfied(monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    fresh_due = "2099-01-01T00:00:00+00:00"
    fake_vault.seed(
        _control(
            "ctrl-good",
            state="satisfied",
            evidence_refs=["sha256:aaaa"],
            last_evidence_at="2026-01-01T00:00:00+00:00",
            due_at=fresh_due,
        )
    )

    result = runner.invoke(app, ["controls", "status", "--system-id", SYSTEM_ID])

    assert result.exit_code == 0, result.output
    assert "controls: 1 total" in result.output


def test_status_no_fail_on_missing_semantics(monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    fake_vault.seed(_control("ctrl-missing"))

    result = runner.invoke(
        app,
        ["controls", "status", "--system-id", SYSTEM_ID, "--no-fail-on-missing"],
    )

    assert result.exit_code == 0, result.output

    # a stale-by-ttl control still gates even with --no-fail-on-missing
    stale_due = "2020-01-01T00:00:00+00:00"
    fake_vault.seed(
        _control(
            "ctrl-stale",
            state="satisfied",
            evidence_refs=["sha256:aaaa"],
            last_evidence_at=stale_due,
            due_at=stale_due,
        )
    )
    stale_result = runner.invoke(
        app,
        ["controls", "status", "--system-id", SYSTEM_ID, "--no-fail-on-missing"],
    )
    assert stale_result.exit_code == 1


def test_status_json_output_parses(monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    fake_vault.seed(_control("ctrl-missing"))

    result = runner.invoke(
        app,
        ["controls", "status", "--system-id", SYSTEM_ID, "--output", "json"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["system_id"] == SYSTEM_ID
    assert payload["exit_code"] == 1
    assert payload["summary"]["evidence_missing"] == 1


def _seed_eu_satisfied_and_fixture_missing(monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)
    fake_vault = _FakeVault()
    monkeypatch.setattr(main_module, "_vault_request", fake_vault)
    fake_vault.seed(
        _control(
            "ctrl-eu",
            state="satisfied",
            evidence_refs=["sha256:aaaa"],
            last_evidence_at="2026-01-01T00:00:00+00:00",
            due_at="2099-01-01T00:00:00+00:00",
        ),
        _control("ctrl-fixture", article_ref="FIXTURE:REQ-1"),
    )


def test_status_counts_only_eu_ai_act_controls_by_default(monkeypatch):
    _seed_eu_satisfied_and_fixture_missing(monkeypatch)

    result = runner.invoke(app, ["controls", "status", "--system-id", SYSTEM_ID])

    assert result.exit_code == 0, result.output
    assert "controls: 1 total · 1 satisfied · 0 evidence_missing" in result.output


def test_status_framework_flag_selects_the_frameworks_counted(monkeypatch):
    _seed_eu_satisfied_and_fixture_missing(monkeypatch)
    base = ["controls", "status", "--system-id", SYSTEM_ID]

    fixture_only = runner.invoke(app, [*base, "--framework", "FIXTURE"])
    assert fixture_only.exit_code == 1
    assert "controls: 1 total · 0 satisfied · 1 evidence_missing" in (
        fixture_only.output
    )

    both = runner.invoke(
        app,
        [*base, "--framework", "EU_AI_ACT", "--framework", "FIXTURE", "-o", "json"],
    )
    assert both.exit_code == 1
    payload = json.loads(both.stdout)
    assert set(payload) == {"system_id", "summary", "stale_count", "exit_code"}
    assert payload["summary"] == {"satisfied": 1, "evidence_missing": 1}


def test_status_unknown_framework_exits_2(monkeypatch):
    _seed_eu_satisfied_and_fixture_missing(monkeypatch)

    result = runner.invoke(
        app,
        ["controls", "status", "--system-id", SYSTEM_ID, "--framework", "ISO_42001"],
    )

    assert result.exit_code == 2
    assert "ISO_42001" in result.output


def test_status_counts_gated_frameworks_by_default(monkeypatch, tmp_path):
    _seed_eu_satisfied_and_fixture_missing(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "opencomplai.yaml").write_text(
        "gate:\n  frameworks: [FIXTURE]\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["controls", "status", "--system-id", SYSTEM_ID])

    assert result.exit_code == 1, result.output
    assert "controls: 2 total · 1 satisfied · 1 evidence_missing" in result.output
