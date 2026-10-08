import json

import pytest
from opencomplai import AgentDecisionLog
from opencomplai_core.signed_log import SignedLog
from opencomplai_core.signing import SigningDomain, SigningKeyError, generate_keypair

FIELDS = {
    "agent_id", "mandate_ref", "intent", "tool", "input_hash", "outcome",
    "outside_mandate",
}  # fmt: skip


def _clock():
    n = iter(range(1, 1000))
    return lambda: f"2026-01-01T00:00:{next(n):02d}+00:00"


def _log(tmp_path, **kw):
    return AgentDecisionLog(tmp_path / "agent.jsonl", clock=_clock(), **kw)


def _rec(log, n=1, **kw):
    for i in range(n):
        log.record(
            **{
                "agent_id": "a1",
                "tool": "search",
                "intent": f"step {i}",
                "tool_input": {"q": i},
                "outcome": "success",
                **kw,
            }
        )


@pytest.fixture
def keys(tmp_path, monkeypatch):
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    d = tmp_path / "keys"
    generate_keypair(d)
    return d / "signing.key", d / "signing.pub"


def _lines(log):
    return log._log.path.read_text(encoding="utf-8").splitlines()


def test_record_writes_documented_fields(tmp_path):
    log = _log(tmp_path)
    e = log.record(
        agent_id="a1", tool="t", intent="i", tool_input=1, outcome="blocked",
        mandate_ref="m1", outside_mandate=True,
    )  # fmt: skip
    assert FIELDS <= set(e)
    assert set(json.loads(_lines(log)[0])["payload"]) == FIELDS
    assert e["input_hash"].startswith("sha256:")
    assert (e["seq"], e["mandate_ref"], e["outside_mandate"]) == (1, "m1", True)
    assert log.entries() == [e]


def test_raw_tool_input_is_not_stored(tmp_path):
    log = _log(tmp_path)
    _rec(log, tool_input={"password": "hunter2-secret"})
    assert b"hunter2-secret" not in log._log.path.read_bytes()


def test_input_hash_is_stable_for_equal_inputs(tmp_path):
    log = _log(tmp_path)
    _rec(log, tool_input={"a": 1, "b": 2})
    _rec(log, tool_input={"b": 2, "a": 1})
    _rec(log, tool_input={"a": 1, "b": 3})
    h = [e["input_hash"] for e in log.entries()]
    assert h[0] == h[1] != h[2]


def test_unsigned_log_verifies(tmp_path):
    log = _log(tmp_path)
    _rec(log, 3)
    v = log.verify()
    assert v.ok
    assert v.count == 3
    assert v.signed_count == 0
    assert not v.verified_signatures
    assert "signature" not in log.entries()[0]


def test_signed_log_verifies_with_public_key(tmp_path, keys):
    priv, pub = keys
    log = _log(tmp_path, signing_key=priv)
    _rec(log, 2)
    v = log.verify(public_key=pub.read_bytes(), require_signed=True)
    assert v.ok
    assert v.signed_count == 2
    assert v.verified_signatures
    assert log.verify(public_key=pub).ok
    assert "signature" in log.entries()[0]
    # bytes key works as the private PEM too
    log2 = AgentDecisionLog(
        tmp_path / "b.jsonl", signing_key=priv.read_bytes(), clock=_clock()
    )
    _rec(log2)
    assert log2.verify(public_key=pub, require_signed=True).ok


def test_require_signed_rejects_unsigned_log(tmp_path):
    log = _log(tmp_path)
    _rec(log)
    v = log.verify(require_signed=True)
    assert not v.ok
    assert v.error == "unsigned"


def test_missing_signing_key_raises_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    log = _log(tmp_path, signing_key=tmp_path / "nope.key")
    with pytest.raises(SigningKeyError):
        _rec(log)
    assert not log._log.path.exists()


def test_edited_entry_fails_verification(tmp_path):
    log = _log(tmp_path)
    _rec(log, 3)
    lines = _lines(log)
    e = json.loads(lines[1])
    e["payload"]["outcome"] = "failure"
    lines[1] = json.dumps(e, sort_keys=True)
    log._log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    v = log.verify()
    assert not v.ok
    assert v.error == "hash"
    assert v.bad_seq == 2


def test_deleted_middle_entry_is_a_sequence_gap(tmp_path):
    log = _log(tmp_path)
    _rec(log, 3)
    lines = _lines(log)
    log._log.path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")
    v = log.verify()
    assert not v.ok
    assert v.error in ("seq", "prev_hash")
    assert v.bad_seq == 2


def test_truncation_detected_against_anchor(tmp_path):
    log = _log(tmp_path)
    _rec(log, 3)
    head, count = log.head(), len(log)
    log._log.path.write_text("\n".join(_lines(log)[:2]) + "\n", encoding="utf-8")
    # documented limit: a plain verify cannot see removal of the newest entries
    assert log.verify().ok
    assert not log.verify(expected_head=head).ok
    assert not log.verify(expected_count=count).ok


def test_wrong_public_key_fails_signature(tmp_path, keys):
    priv, _ = keys
    other = tmp_path / "other"
    generate_keypair(other)
    log = _log(tmp_path, signing_key=priv)
    _rec(log)
    v = log.verify(public_key=other / "signing.pub")
    assert not v.ok
    assert v.error == "signature"


def test_log_is_not_valid_under_another_domain(tmp_path):
    path = tmp_path / "agent.jsonl"
    other = SignedLog(path, SigningDomain.OVERSIGHT_LOG)
    other.append(dict.fromkeys(FIELDS, "x"), ts="2026-01-01T00:00:00+00:00")
    assert not AgentDecisionLog(path).verify().ok


@pytest.mark.parametrize(
    "bad",
    [
        {"agent_id": ""},
        {"outcome": "weird"},
        {"outside_mandate": "yes"},
        {"intent": "x" * 1001},
    ],
)
def test_invalid_fields_raise_and_write_nothing(tmp_path, bad):
    log = _log(tmp_path)
    with pytest.raises(ValueError, match="must"):
        _rec(log, **bad)
    assert not log._log.path.exists()


def test_payload_with_extra_field_is_schema_error(tmp_path):
    path = tmp_path / "agent.jsonl"
    SignedLog(path, SigningDomain.AGENT_LOG).append(
        {
            "agent_id": "a", "mandate_ref": None, "intent": "i", "tool": "t",
            "input_hash": "sha256:x", "outcome": "success",
            "outside_mandate": False, "extra": 1,
        },
        ts="2026-01-01T00:00:00+00:00",
    )  # fmt: skip
    v = AgentDecisionLog(path).verify()
    assert not v.ok
    assert v.error == "schema"
    assert v.bad_seq == 1


def test_reopen_resumes_the_chain(tmp_path):
    path = tmp_path / "agent.jsonl"
    _rec(AgentDecisionLog(path, clock=_clock()), 2)
    again = AgentDecisionLog(path, clock=_clock())
    _rec(again)
    assert len(again) == 3
    assert again.entries()[2]["seq"] == 3
    assert again.verify().ok
