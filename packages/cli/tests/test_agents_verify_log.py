"""`opencomplai agents verify-log` and `opencomplai verify --kind agent-log` (SU-28a2)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import opencomplai_cli.main as main_module
import pytest
from opencomplai_cli.main import app
from opencomplai_core.agent_inventory import (
    AgentInventory,
    AgentMandate,
    AgentSpec,
    AgentTool,
)
from opencomplai_core.agent_log_verify import entry_content_hash
from opencomplai_core.signed_log import SignedLog
from opencomplai_core.signing import SigningDomain, generate_keypair
from typer.testing import CliRunner

runner = CliRunner()
TS = "2026-03-01T10:00:00+00:00"
SECRET_INTENT = "intent-text-that-must-not-leak"


@pytest.fixture(autouse=True)
def keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    monkeypatch.delenv("OPENCOMPLAI_VAULT_URL", raising=False)
    monkeypatch.setattr(main_module, "_SIGNING_PUB", tmp_path / "none" / "signing.pub")
    keys = tmp_path / "keys"
    generate_keypair(keys)
    return keys


def _payload(tool="search", outside=False) -> dict:
    return {
        "agent_id": "a1",
        "mandate_ref": None,
        "intent": SECRET_INTENT,
        "tool": tool,
        "input_hash": "sha256:" + "11" * 32,
        "outcome": "success",
        "outside_mandate": outside,
    }


def _log(
    tmp_path: Path,
    payloads: list[dict],
    key: Path | None = None,
    name="agent-log.jsonl",
) -> Path:
    path = tmp_path / name
    pem = key.read_bytes() if key else None
    log = SignedLog(path, SigningDomain.AGENT_LOG)
    for p in payloads:
        log.append(p, ts=TS, private_pem=pem)
    return path


def _manifest(tmp_path: Path, mandate: AgentMandate | None = None) -> Path:
    path = tmp_path / "system-manifest.json"
    res = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "log-sys",
            "--intended-purpose",
            "bot",
            "--output",
            str(path),
        ],
    )
    assert res.exit_code == 0, res.output
    data = json.loads(path.read_text(encoding="utf-8"))
    inv = AgentInventory(
        agents=[
            AgentSpec(
                id="a1",
                name="One",
                tools=[AgentTool(name=t, kind="function") for t in ("search", "send")],
                mandate=mandate or AgentMandate(prohibited_actions=["tool:send"]),
            )
        ]
    )
    data["agent_inventory"] = inv.model_dump(mode="json", exclude_none=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _run(*args: str):
    return runner.invoke(app, ["agents", "verify-log", *args])


def _rewrite(path: Path, edit) -> None:
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    path.write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in edit(rows)),
        encoding="utf-8",
    )


class _FakeVault:
    def __init__(self, fail_on_call: int | None = None, bad_hash=False) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.fail_on_call, self.bad_hash = fail_on_call, bad_hash

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if self.fail_on_call == len(self.calls):
            raise OSError("down")
        if path == "/v1/evidence/objects":
            if self.bad_hash:
                return {"content_hash": "sha256:" + "00" * 32}
            raw = base64.b64decode(body["content_base64"])
            import hashlib

            return {"content_hash": "sha256:" + hashlib.sha256(raw).hexdigest()}
        return {"event_id": "e", "payload_hash": "h", "prev_hash": "p"}


def _vault(monkeypatch, **kw) -> _FakeVault:
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    fake = _FakeVault(**kw)
    monkeypatch.setattr(main_module, "_vault_request", fake)
    return fake


def test_clean_log_exits_0_json_status_verified(tmp_path):
    log = _log(tmp_path, [_payload(), _payload()])
    res = _run(str(log), "--manifest", str(_manifest(tmp_path)), "-o", "json")
    assert res.exit_code == 0, res.output
    out = json.loads(res.output)
    assert out["status"] == "verified"
    assert out["chain"]["count"] == 2
    assert out["mandate_checked"] is True
    assert out["out_of_mandate"] == []
    assert out["vault"] is None


def test_tamper_exits_1(tmp_path):
    log = _log(tmp_path, [_payload(), _payload()])
    _rewrite(log, lambda r: [r[0], {**r[1], "payload": _payload("other")}])
    res = _run(str(log), "-o", "json")
    out = json.loads(res.output)
    assert res.exit_code == 1
    assert out["status"] == "invalid"
    assert out["chain"]["error"] == "hash"


def test_sequence_gap_exits_1(tmp_path):
    log = _log(tmp_path, [_payload(), _payload(), _payload()])
    _rewrite(log, lambda r: [r[0], r[2]])
    res = _run(str(log))
    assert res.exit_code == 1
    assert "INVALID" in res.output


def test_out_of_mandate_listed_and_exits_1(tmp_path):
    log = _log(tmp_path, [_payload("search"), _payload("send")])
    res = _run(str(log), "--manifest", str(_manifest(tmp_path)))
    assert res.exit_code == 1
    assert "seq=2" in res.output
    assert "agent=a1" in res.output
    assert "tool=send" in res.output
    assert "prohibited_action" in res.output
    assert SECRET_INTENT not in res.output


def test_no_manifest_checks_chain_only_and_says_so(tmp_path):
    log = _log(tmp_path, [_payload("send", outside=True)])
    res = _run(str(log))
    assert res.exit_code == 0
    assert "mandate not checked: no manifest or no agent_inventory" in res.output
    assert "head=sha256:" in res.output
    assert "count=1" in res.output


def test_invalid_manifest_exits_2(tmp_path):
    log = _log(tmp_path, [_payload()])
    bad = tmp_path / "system-manifest.json"
    bad.write_text("{not json", encoding="utf-8")
    assert _run(str(log)).exit_code == 2
    assert _run(str(log), "--manifest", str(tmp_path / "gone.json")).exit_code == 2


def test_missing_log_exits_2(tmp_path):
    assert _run(str(tmp_path / "nope.jsonl")).exit_code == 2


def test_require_signed_flags_unsigned_log(tmp_path):
    log = _log(tmp_path, [_payload()])
    assert _run(str(log), "--require-signed").exit_code == 1
    assert _run(str(log)).exit_code == 0


def test_signed_log_needs_pub_key_or_reports_it(tmp_path, keys):
    log = _log(tmp_path, [_payload()], key=keys / "signing.key")
    res = _run(str(log), "-o", "json")
    chain = json.loads(res.output)["chain"]
    assert chain["signed_count"] == 1
    assert chain["verified_signatures"] is False
    assert (
        _run(str(log), "--require-signed").exit_code == 1
    )  # cannot be satisfied unchecked
    ok = _run(
        str(log),
        "--pub-key",
        str(keys / "signing.pub"),
        "--require-signed",
        "-o",
        "json",
    )
    assert ok.exit_code == 0
    assert json.loads(ok.output)["chain"]["verified_signatures"]
    other = tmp_path / "other"
    generate_keypair(other)
    wrong = _run(str(log), "--pub-key", str(other / "signing.pub"))
    assert wrong.exit_code == 1
    assert "signature" in wrong.output


def test_vault_without_url_exits_2_and_sends_nothing(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(main_module, "_vault_request", lambda *a, **k: calls.append(a))
    log = _log(tmp_path, [_payload()])
    assert _run(str(log), "--vault", "--system-id", "s").exit_code == 2
    assert calls == []


def test_vault_append_posts_object_then_event(tmp_path, monkeypatch):
    fake = _vault(monkeypatch)
    log = _log(tmp_path, [_payload("search"), _payload("send")])
    res = _run(
        str(log), "--vault", "--manifest", str(_manifest(tmp_path)), "-o", "json"
    )
    assert res.exit_code == 1  # one entry out of mandate, still appended
    assert json.loads(res.output)["vault"] == {"appended": 2}
    assert [(m, p) for m, p, _ in fake.calls] == [
        ("POST", "/v1/evidence/objects"),
        ("POST", "/v1/evidence/events"),
    ] * 2
    entries = SignedLog(log, SigningDomain.AGENT_LOG).entries()
    for i, entry in enumerate(entries):
        obj, ev = fake.calls[2 * i][2], fake.calls[2 * i + 1][2]
        assert obj["source"] == "agent-log"
        assert ev["event_type"] == "agent_action"
        assert ev["payload"]["content_hash"] == entry_content_hash(entry)
        assert ev["payload"]["system_id"] == "log-sys"
        assert SECRET_INTENT not in json.dumps(ev)
    assert fake.calls[3][2]["payload"]["findings"] == ["prohibited_action"]
    assert fake.calls[1][2]["payload"]["outside_mandate"] is False


def test_vault_not_called_for_tampered_log(tmp_path, monkeypatch):
    fake = _vault(monkeypatch)
    log = _log(tmp_path, [_payload(), _payload()])
    _rewrite(log, lambda r: [r[0], {**r[1], "payload": _payload("other")}])
    res = _run(str(log), "--vault", "--system-id", "s")
    assert res.exit_code == 1
    assert fake.calls == []


def test_vault_failure_midway_reports_progress_and_exits_2(tmp_path, monkeypatch):
    fake = _vault(monkeypatch, fail_on_call=3)  # object for entry 2
    log = _log(tmp_path, [_payload(), _payload(), _payload()])
    res = _run(str(log), "--vault", "--system-id", "s")
    assert res.exit_code == 2
    assert "1 appended" in res.output
    assert "--vault-from-seq 2" in res.output
    assert len(fake.calls) == 3


def test_vault_from_seq_skips_earlier_entries(tmp_path, monkeypatch):
    fake = _vault(monkeypatch)
    log = _log(tmp_path, [_payload(), _payload(), _payload()])
    res = _run(
        str(log), "--vault", "--system-id", "s", "--vault-from-seq", "3", "-o", "json"
    )
    assert res.exit_code == 0
    assert json.loads(res.output)["vault"] == {"appended": 1}
    assert [
        c[2]["payload"]["seq"] for c in fake.calls if "payload" in (c[2] or {})
    ] == [3]


def test_vault_hash_mismatch_exits_2(tmp_path, monkeypatch):
    fake = _vault(monkeypatch, bad_hash=True)
    log = _log(tmp_path, [_payload()])
    res = _run(str(log), "--vault", "--system-id", "s")
    assert res.exit_code == 2
    assert "different content hash" in res.output
    assert len(fake.calls) == 1  # no event after a mismatch


def test_vault_needs_a_system_id(tmp_path, monkeypatch):
    fake = _vault(monkeypatch)
    res = _run(str(_log(tmp_path, [_payload()])), "--vault")
    assert res.exit_code == 2
    assert "--system-id" in res.output
    assert fake.calls == []


def test_verify_kind_agent_log_dispatches(tmp_path, keys):
    log = _log(tmp_path, [_payload()], key=keys / "signing.key")
    pub = str(keys / "signing.pub")
    ok = runner.invoke(
        app, ["verify", str(log), "--kind", "agent-log", "--pub-key", pub]
    )
    assert ok.exit_code == 0
    assert "verified" in ok.output
    assert "head=sha256:" in ok.output

    _rewrite(log, lambda r: [{**r[0], "payload": _payload("other")}])
    bad = runner.invoke(
        app, ["verify", str(log), "--kind", "agent-log", "--pub-key", pub]
    )
    assert bad.exit_code == 1
    assert "INVALID" in bad.output

    _manifest(tmp_path)
    log2 = _log(
        tmp_path, [_payload("send")], key=keys / "signing.key", name="second.jsonl"
    )
    oom = runner.invoke(
        app, ["verify", str(log2), "--kind", "agent-log", "--pub-key", pub]
    )
    assert oom.exit_code == 1
    assert "out_of_mandate=1" in oom.output

    unsigned = _log(tmp_path, [_payload()], name="u.jsonl")
    res = runner.invoke(app, ["verify", str(unsigned), "--kind", "agent-log"])
    assert res.exit_code == 1
    assert "unsigned" in res.output

    (tmp_path / "system-manifest.json").write_text("{bad", encoding="utf-8")
    res = runner.invoke(
        app, ["verify", str(log2), "--kind", "agent-log", "--pub-key", pub]
    )
    assert res.exit_code == 1
    assert "manifest unreadable" in res.output


def test_output_never_contains_intent_or_pem(tmp_path, keys):
    log = _log(tmp_path, [_payload("send")], key=keys / "signing.key")
    pub = keys / "signing.pub"
    for fmt in ("human", "json"):
        res = _run(
            str(log),
            "--manifest",
            str(_manifest(tmp_path)),
            "--pub-key",
            str(pub),
            "-o",
            fmt,
        )
        assert SECRET_INTENT not in res.output
        assert "BEGIN" not in res.output
