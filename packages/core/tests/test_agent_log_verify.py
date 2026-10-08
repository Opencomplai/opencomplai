"""Agent decision log read-back: chain, signatures, mandate compliance (SU-28a2)."""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

from opencomplai_core import agent_log_verify as alv
from opencomplai_core.agent_inventory import (
    AgentInventory,
    AgentMandate,
    AgentSpec,
    AgentTool,
)
from opencomplai_core.agent_log_verify import (
    MANDATE_RULES,
    check_mandate,
    entry_bytes,
    entry_content_hash,
    vault_event_payload,
    verify_agent_log,
)
from opencomplai_core.gap_probes import artifact_gap_status
from opencomplai_core.gap_report import build_gap_report, load_gap_article_map
from opencomplai_core.models import GapStatus
from opencomplai_core.signed_log import SignedLog
from opencomplai_core.signing import SigningDomain, generate_keypair

TS = "2026-03-01T10:00:00+00:00"


def _inv(
    mandate: AgentMandate | None = None, tools=("search", "send")
) -> AgentInventory:
    return AgentInventory(
        agents=[
            AgentSpec(
                id="a1",
                name="Agent One",
                tools=[AgentTool(name=t, kind="function") for t in tools],
                mandate=mandate,
            )
        ]
    )


def _payload(tool="search", agent_id="a1", outside=False) -> dict:
    return {
        "agent_id": agent_id,
        "mandate_ref": None,
        "intent": "secret free text",
        "tool": tool,
        "input_hash": "sha256:" + "11" * 32,
        "outcome": "success",
        "outside_mandate": outside,
    }


def _log(tmp_path: Path, payloads: list[dict], key: bytes | None = None, ts=TS) -> Path:
    path = tmp_path / "agent-log.jsonl"
    log = SignedLog(path, SigningDomain.AGENT_LOG)
    for p in payloads:
        log.append(p, ts=ts, private_pem=key)
    return path


def _keys(tmp_path: Path) -> tuple[bytes, bytes]:
    generate_keypair(tmp_path / "keys")
    return (
        (tmp_path / "keys" / "signing.key").read_bytes(),
        (tmp_path / "keys" / "signing.pub").read_bytes(),
    )


def _rewrite(path: Path, edit) -> None:
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    lines = edit(lines)
    path.write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in lines), encoding="utf-8"
    )


def _reasons(report) -> list[tuple[int, tuple[str, ...]]]:
    return [(o.seq, o.reasons) for o in report.out_of_mandate]


def test_clean_signed_log_verifies(tmp_path):
    priv, pub = _keys(tmp_path)
    path = _log(tmp_path, [_payload(), _payload("send")], key=priv)
    r = verify_agent_log(path, public_pem=pub, require_signed=True, inventory=_inv())
    assert r.ok
    assert r.mandate_checked
    assert r.chain.verified_signatures
    assert r.chain.count == 2


def test_clean_unsigned_log_verifies_unless_required(tmp_path):
    path = _log(tmp_path, [_payload()])
    assert verify_agent_log(path).ok
    r = verify_agent_log(path, require_signed=True)
    assert not r.ok
    assert r.chain.error == "unsigned"


def test_tampered_entry_is_flagged(tmp_path):
    path = _log(tmp_path, [_payload(), _payload("send")])
    _rewrite(path, lambda rows: [rows[0], {**rows[1], "payload": _payload("other")}])
    r = verify_agent_log(path, inventory=_inv())
    assert not r.ok
    assert r.chain.error == "hash"
    assert r.chain.bad_seq == 2


def test_sequence_gap_is_flagged(tmp_path):
    path = _log(tmp_path, [_payload(), _payload(), _payload()])
    _rewrite(path, lambda rows: [rows[0], rows[2]])
    r = verify_agent_log(path)
    assert not r.ok
    assert r.chain.error in ("seq", "prev_hash")


def test_truncation_needs_anchor(tmp_path):
    path = _log(tmp_path, [_payload(), _payload(), _payload()])
    _rewrite(path, lambda rows: rows[:-1])
    assert verify_agent_log(path).ok  # documented limit of a bare chain
    r = verify_agent_log(path, expected_count=3)
    assert not r.ok
    assert r.chain.error == "count"


def test_prohibited_tool_is_out_of_mandate(tmp_path):
    inv = _inv(AgentMandate(prohibited_actions=["tool:send"]))
    path = _log(tmp_path, [_payload("search"), _payload("send")])
    r = verify_agent_log(path, inventory=inv)
    assert not r.ok
    assert _reasons(r) == [(2, ("prohibited_action",))]


def test_tool_outside_permitted_actions_is_out_of_mandate(tmp_path):
    inv = _inv(AgentMandate(permitted_actions=["Search"]))
    path = _log(tmp_path, [_payload("search"), _payload("send")])
    assert _reasons(verify_agent_log(path, inventory=inv)) == [(2, ("not_permitted",))]


def test_undeclared_tool_and_unknown_agent_are_flagged(tmp_path):
    path = _log(tmp_path, [_payload("wipe"), _payload(agent_id="ghost")])
    r = verify_agent_log(path, inventory=_inv())
    assert _reasons(r) == [(1, ("tool_not_declared",)), (2, ("unknown_agent",))]


def test_expired_mandate_uses_entry_timestamp_not_clock(tmp_path):
    inv = _inv(AgentMandate(expires_at="2026-03-01T12:00:00+00:00"))
    before = _log(tmp_path, [_payload()], ts="2026-03-01T11:59:59+00:00")
    assert verify_agent_log(before, inventory=inv).ok  # long past "today"
    before.unlink()
    after = _log(tmp_path, [_payload()], ts="2026-03-01T12:00:01+00:00")
    assert _reasons(verify_agent_log(after, inventory=inv)) == [
        (1, ("mandate_expired",))
    ]


def test_unparsable_timestamp_is_bad_timestamp_not_pass(tmp_path):
    inv = _inv(AgentMandate(expires_at="2026-03-01"))
    path = _log(tmp_path, [_payload()], ts="not a time")
    assert _reasons(verify_agent_log(path, inventory=inv)) == [(1, ("bad_timestamp",))]


def test_self_reported_flag_is_not_trusted(tmp_path):
    inv = _inv(AgentMandate(prohibited_actions=["send"]))
    path = _log(
        tmp_path, [_payload("send", outside=False), _payload("search", outside=True)]
    )
    r = verify_agent_log(path, inventory=inv)
    assert _reasons(r) == [(1, ("prohibited_action",)), (2, ("self_reported",))]


def test_no_inventory_means_mandate_not_checked(tmp_path):
    path = _log(tmp_path, [_payload("send", outside=True)])
    r = verify_agent_log(path)
    assert r.ok
    assert not r.mandate_checked
    assert r.out_of_mandate == ()
    assert check_mandate([], None) == []


def test_broken_chain_skips_mandate_check(tmp_path):
    inv = _inv(AgentMandate(prohibited_actions=["send"]))
    path = _log(tmp_path, [_payload("send"), _payload("send")])
    _rewrite(path, lambda rows: [rows[0], {**rows[1], "ts": "x"}])
    r = verify_agent_log(path, inventory=inv)
    assert not r.chain.ok
    assert not r.mandate_checked
    assert r.out_of_mandate == ()


def test_vault_payload_has_no_free_text_fields(tmp_path):
    path = _log(tmp_path, [_payload("send", outside=True)])
    entry = SignedLog(path, SigningDomain.AGENT_LOG).entries()[0]
    p = vault_event_payload("sys", entry, entry_content_hash(entry), ("not_permitted",))
    assert set(p) == {
        "system_id",
        "agent_id",
        "seq",
        "entry_hash",
        "content_hash",
        "tool",
        "outside_mandate",
        "findings",
    }
    assert p["outside_mandate"] is True
    assert p["entry_hash"] == entry["hash"]
    assert "secret free text" not in json.dumps(p)
    assert vault_event_payload("sys", entry, "h", ())["outside_mandate"] is False


def test_entry_content_hash_matches_vault_cas_format(tmp_path):
    entry = SignedLog(_log(tmp_path, [_payload()]), SigningDomain.AGENT_LOG).entries()[
        0
    ]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", entry_content_hash(entry))
    assert entry_bytes(entry) == entry_bytes(json.loads(entry_bytes(entry)))


def test_agent_log_verify_never_reads_the_clock():
    src = inspect.getsource(alv)
    assert "datetime.now" not in src
    assert "time.time" not in src


def test_mandate_rules_are_flagged():
    assert MANDATE_RULES
    for rule in MANDATE_RULES.values():
        assert rule["source"]
        assert rule["confidence"]
        assert rule["needs_founder_review"] is True


def test_agent_log_file_counts_as_event_log_evidence(tmp_path):
    load_gap_article_map.cache_clear()
    _log(tmp_path, [_payload()])
    sources = load_gap_article_map()["Art. 12"]["sources"]
    ref = next(s["ref"] for s in sources if s["kind"] == "artifact")
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.evidence_ref == "agent-log.jsonl"
    art12 = next(
        r
        for r in build_gap_report("s", "HEAD", repo_root=tmp_path).articles
        if r.article == "Art. 12"
    )
    assert art12.status == GapStatus.PARTIAL
    load_gap_article_map.cache_clear()
