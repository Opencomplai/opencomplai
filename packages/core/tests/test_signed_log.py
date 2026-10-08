"""Tests for the shared signed hash-chain log (no clock: fixed ts strings)."""

import base64
import json
from pathlib import Path

import pytest
from opencomplai_core import signed_log
from opencomplai_core.signed_log import GENESIS_HASH, SignedLog, entry_hash, verify_log
from opencomplai_core.signing import SigningDomain, generate_keypair

OV = SigningDomain.OVERSIGHT_LOG
AG = SigningDomain.AGENT_LOG
TS = ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", "2026-01-03T00:00:00Z"]


@pytest.fixture
def keys(tmp_path: Path) -> tuple[bytes, bytes]:
    generate_keypair(tmp_path / "k")
    return (tmp_path / "k" / "signing.key").read_bytes(), (
        tmp_path / "k" / "signing.pub"
    ).read_bytes()


def _write(
    path: Path, domain=OV, n: int = 3, private_pem: bytes | None = None
) -> SignedLog:
    log = SignedLog(path, domain)
    for i in range(n):
        log.append({"event": f"e{i}", "n": i}, ts=TS[i], private_pem=private_pem)
    return log


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _put(path: Path, lines: list[str]) -> None:
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def test_unsigned_chain_verifies(tmp_path: Path):
    log = _write(tmp_path / "l.jsonl")
    v = verify_log(log.path, OV)
    assert (v.ok, v.count, v.head, v.signed_count) == (True, 3, log.head(), 0)
    assert len(log) == 3
    assert v.error is None


def test_signed_chain_verifies_with_public_key(tmp_path: Path, keys):
    priv, pub = keys
    log = _write(tmp_path / "l.jsonl", private_pem=priv)
    v = verify_log(log.path, OV, public_pem=pub, require_signed=True)
    assert (v.ok, v.signed_count, v.verified_signatures) == (True, 3, True)
    # Without a public key only the chain is checked.
    v = verify_log(log.path, OV)
    assert (v.ok, v.verified_signatures) == (True, False)


def test_require_signed_rejects_unsigned_entry(tmp_path: Path, keys):
    priv, pub = keys
    log = SignedLog(tmp_path / "l.jsonl", OV)
    log.append({"a": 1}, ts=TS[0], private_pem=priv)
    log.append({"a": 2}, ts=TS[1])
    v = verify_log(log.path, OV, public_pem=pub, require_signed=True)
    assert (v.ok, v.error, v.bad_seq) == (False, "unsigned", 2)


def test_mixed_chain_verifies_without_require_signed(tmp_path: Path, keys):
    priv, pub = keys
    log = SignedLog(tmp_path / "l.jsonl", OV)
    log.append({"a": 1}, ts=TS[0], private_pem=priv)
    log.append({"a": 2}, ts=TS[1])
    v = verify_log(log.path, OV, public_pem=pub)
    assert (v.ok, v.signed_count, v.verified_signatures) == (True, 1, True)


def test_edit_is_detected(tmp_path: Path):
    log = _write(tmp_path / "l.jsonl")
    lines = _lines(log.path)
    e = json.loads(lines[1])
    e["payload"]["n"] = 99
    lines[1] = json.dumps(e)
    _put(log.path, lines)
    v = verify_log(log.path, OV)
    assert (v.ok, v.error, v.bad_seq) == (False, "hash", 2)


def test_edit_with_rehash_is_detected(tmp_path: Path):
    log = _write(tmp_path / "l.jsonl")
    lines = _lines(log.path)
    e = json.loads(lines[1])
    e["payload"]["n"] = 99
    e["hash"] = entry_hash(OV, e["seq"], e["ts"], e["payload"], e["prev_hash"])
    lines[1] = json.dumps(e)
    _put(log.path, lines)
    v = verify_log(log.path, OV)
    assert (v.ok, v.error, v.bad_seq) == (False, "prev_hash", 3)


def test_delete_middle_is_detected(tmp_path: Path):
    log = _write(tmp_path / "l.jsonl")
    lines = _lines(log.path)
    _put(log.path, [lines[0], lines[2]])
    v = verify_log(log.path, OV)
    assert (v.ok, v.error) == (False, "seq")


def test_reorder_is_detected(tmp_path: Path):
    log = _write(tmp_path / "l.jsonl")
    lines = _lines(log.path)
    _put(log.path, [lines[0], lines[2], lines[1]])
    v = verify_log(log.path, OV)
    assert (v.ok, v.error) == (False, "seq")


def test_truncation_detected_against_anchor(tmp_path: Path):
    log = _write(tmp_path / "l.jsonl")
    anchor, n = log.head(), len(log)
    full = _write(tmp_path / "full.jsonl")
    assert verify_log(full.path, OV, expected_head=anchor, expected_count=n).ok
    _put(log.path, _lines(log.path)[:-1])
    # The limitation, pinned: a chain alone cannot see a dropped tail.
    assert verify_log(log.path, OV).ok is True
    v = verify_log(log.path, OV, expected_head=anchor)
    assert (v.ok, v.error) == (False, "head")
    v = verify_log(log.path, OV, expected_count=n)
    assert (v.ok, v.error) == (False, "count")


def test_wrong_public_key_fails_signature(tmp_path: Path, keys):
    priv, _ = keys
    generate_keypair(tmp_path / "other")
    other_pub = (tmp_path / "other" / "signing.pub").read_bytes()
    log = _write(tmp_path / "l.jsonl", private_pem=priv)
    v = verify_log(log.path, OV, public_pem=other_pub)
    assert (v.ok, v.error, v.bad_seq) == (False, "signature", 1)


def test_domain_separation_between_logs(tmp_path: Path, keys):
    priv, pub = keys
    for name, pem in (("u", None), ("s", priv)):
        log = _write(tmp_path / f"{name}.jsonl", domain=OV, private_pem=pem)
        assert verify_log(log.path, OV, public_pem=pub).ok
        v = verify_log(log.path, AG, public_pem=pub)
        assert (v.ok, v.error) == (False, "hash")


def test_signature_alone_is_domain_separated(tmp_path: Path, keys):
    """Even with the chain re-hashed for another domain, the old signature fails."""
    priv, pub = keys
    log = _write(tmp_path / "l.jsonl", n=1, private_pem=priv)
    e = json.loads(_lines(log.path)[0])
    e["hash"] = entry_hash(AG, e["seq"], e["ts"], e["payload"], e["prev_hash"])
    _put(log.path, [json.dumps(e)])
    v = verify_log(log.path, AG, public_pem=pub)
    assert (v.ok, v.error) == (False, "signature")


def test_empty_log_verifies(tmp_path: Path):
    v = verify_log(tmp_path / "missing.jsonl", OV)
    assert (v.ok, v.count, v.head) == (True, 0, GENESIS_HASH)
    (tmp_path / "empty.jsonl").write_bytes(b"")
    assert verify_log(tmp_path / "empty.jsonl", OV).ok


def test_garbage_line_returns_parse_error_not_exception(tmp_path: Path):
    log = _write(tmp_path / "l.jsonl", n=2)
    good = _lines(log.path)
    for bad in ("not json", "[1, 2]", '{"seq": 3}'):
        _put(log.path, [*good, bad])
        v = verify_log(log.path, OV)
        assert (v.ok, v.error, v.bad_seq) == (False, "parse", 3)
    log.path.write_bytes(("\n".join(good) + "\n").encode() + b"\xff\xfe\n")
    assert verify_log(log.path, OV).ok is False


def test_append_resumes_chain_from_existing_file(tmp_path: Path):
    path = tmp_path / "sub" / "l.jsonl"
    _write(path, n=2)
    e = SignedLog(path, OV).append({"event": "e2"}, ts=TS[2])
    assert e["seq"] == 3
    v = verify_log(path, OV)
    assert (v.ok, v.count, v.head) == (True, 3, e["hash"])


def test_append_is_deterministic_for_same_inputs_unsigned(tmp_path: Path):
    a, b = _write(tmp_path / "a.jsonl"), _write(tmp_path / "b.jsonl")
    assert a.path.read_bytes() == b.path.read_bytes()
    assert b"\r" not in a.path.read_bytes()


def test_append_rejects_empty_ts(tmp_path: Path):
    with pytest.raises(ValueError, match="ts"):
        SignedLog(tmp_path / "l.jsonl", OV).append({}, ts="")


def test_signed_log_module_never_reads_the_clock():
    src = Path(signed_log.__file__).read_text(encoding="utf-8")
    assert "datetime.now" not in src
    assert "time.time" not in src


def test_signature_field_is_base64_of_ed25519(tmp_path: Path, keys):
    priv, _ = keys
    log = _write(tmp_path / "l.jsonl", n=1, private_pem=priv)
    assert len(base64.b64decode(log.entries()[0]["signature"])) == 64
