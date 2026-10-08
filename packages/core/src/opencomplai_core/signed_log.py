"""
Append-only, hash-chained, optionally Ed25519-signed JSONL log.

One shared primitive for the oversight, agent and incident logs. Each line is
``{"seq", "ts", "payload", "prev_hash", "hash", "signature"}``. ``hash`` commits
to the signing domain, ``seq``, ``ts``, ``payload`` and ``prev_hash``, so editing,
deleting or reordering an entry breaks the chain, and a log copied under another
domain fails the chain as well as the signature.

Honest ceiling: a chain alone cannot detect removal of the *newest* entries.
Truncation is detected only against an anchor (``expected_head`` /
``expected_count``) that the consumer stores elsewhere (the ingest
``evidence_hashes``). Without public key material, ``verify_log`` checks chain
integrity only and reports ``verified_signatures=False``: that is not a
signature check.

No clock, no network, no CLI: callers pass ``ts`` and, to sign, key PEM bytes
from ``signing.resolve_key``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from opencomplai_core.signing import (
    SigningDomain,
    canonical_json_bytes,
    domain_separated,
)

GENESIS_HASH = "sha256:" + "0" * 64
_HASH_PREFIX = b"opencomplai.log.v1\x00"
_KEYS = ("seq", "ts", "payload", "prev_hash", "hash", "signature")


def entry_hash(
    domain: SigningDomain, seq: int, ts: str, payload: dict, prev_hash: str
) -> str:
    body = canonical_json_bytes(
        {"seq": seq, "ts": ts, "payload": payload, "prev_hash": prev_hash}
    )
    digest = hashlib.sha256(
        _HASH_PREFIX + domain.value.encode("ascii") + b"\x00" + body
    )
    return "sha256:" + digest.hexdigest()


class SignedLog:
    # ponytail: single writer, whole-file read on append, no lock; add file
    # locking and a tail index if a log exceeds ~10k entries or has concurrent
    # writers.
    def __init__(self, path: Path, domain: SigningDomain) -> None:
        self.path = Path(path)
        self.domain = domain

    def entries(self) -> list[dict]:
        if not self.path.is_file():
            return []
        text = self.path.read_text(encoding="utf-8")
        return [json.loads(line) for line in text.split("\n") if line.strip()]

    def head(self) -> str:
        entries = self.entries()
        return entries[-1]["hash"] if entries else GENESIS_HASH

    def __len__(self) -> int:
        return len(self.entries())

    def append(
        self, payload: dict, *, ts: str, private_pem: bytes | None = None
    ) -> dict:
        if not isinstance(ts, str) or not ts:
            raise ValueError("ts must be a non-empty string")
        # Round-trip so the hashed payload is exactly what is stored on disk.
        payload = json.loads(canonical_json_bytes(payload))
        existing = self.entries()
        seq = len(existing) + 1
        prev = existing[-1]["hash"] if existing else GENESIS_HASH
        digest = entry_hash(self.domain, seq, ts, payload, prev)
        signature = None
        if private_pem is not None:
            from cryptography.hazmat.primitives import serialization

            key = serialization.load_pem_private_key(private_pem, password=None)
            sig = key.sign(domain_separated(self.domain, digest.encode("ascii")))
            signature = base64.b64encode(sig).decode("ascii")
        entry = {
            "seq": seq,
            "ts": ts,
            "payload": payload,
            "prev_hash": prev,
            "hash": digest,
            "signature": signature,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, sort_keys=True).encode("utf-8") + b"\n"
        with open(self.path, "ab") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        return entry


@dataclass(frozen=True)
class LogVerification:
    ok: bool
    count: int
    head: str
    signed_count: int
    verified_signatures: bool
    error: str | None = None
    bad_seq: int | None = None


def _sig_ok(public_key, domain: SigningDomain, digest: str, sig_b64: str) -> bool:
    from cryptography.exceptions import InvalidSignature

    try:
        public_key.verify(
            base64.b64decode(sig_b64, validate=True),
            domain_separated(domain, digest.encode("ascii")),
        )
        return True
    except (InvalidSignature, ValueError):
        return False


def verify_log(
    path: Path,
    domain: SigningDomain,
    *,
    public_pem: bytes | None = None,
    require_signed: bool = False,
    expected_head: str | None = None,
    expected_count: int | None = None,
) -> LogVerification:
    """Verify chain (and signatures when ``public_pem`` is given). Never raises on bad content."""
    public_key = None
    if public_pem is not None:
        from cryptography.hazmat.primitives import serialization

        public_key = serialization.load_pem_public_key(public_pem)

    prev = GENESIS_HASH
    count = signed = verified = 0

    def fail(code: str, seq: int | None) -> LogVerification:
        return LogVerification(False, count, prev, signed, all_verified(), code, seq)

    def all_verified() -> bool:
        return public_key is not None and signed > 0 and verified == signed

    p = Path(path)
    lines = (
        [
            x
            for x in p.read_text(encoding="utf-8", errors="replace").split("\n")
            if x.strip()
        ]
        if p.is_file()
        else []
    )
    for index, line in enumerate(lines, start=1):
        try:
            e = json.loads(line)
            if not isinstance(e, dict) or any(k not in e for k in _KEYS):
                raise ValueError
            seq, ts, payload = e["seq"], e["ts"], e["payload"]
            h, sig = e["hash"], e["signature"]
            if (
                type(seq) is not int
                or not isinstance(ts, str)
                or not isinstance(payload, dict)
                or not isinstance(e["prev_hash"], str)
                or not isinstance(h, str)
                or not (sig is None or isinstance(sig, str))
            ):
                raise ValueError
        except ValueError:
            return fail("parse", index)
        if seq != index:
            return fail("seq", index)
        if e["prev_hash"] != prev:
            return fail("prev_hash", seq)
        if h != entry_hash(domain, seq, ts, payload, prev):
            return fail("hash", seq)
        if sig is None:
            if require_signed:
                return fail("unsigned", seq)
        else:
            signed += 1
            if public_key is not None:
                if not _sig_ok(public_key, domain, h, sig):
                    return fail("signature", seq)
                verified += 1
        prev = h
        count = index

    if expected_head is not None and prev != expected_head:
        return fail("head", None)
    if expected_count is not None and count != expected_count:
        return fail("count", None)
    return LogVerification(True, count, prev, signed, all_verified())
