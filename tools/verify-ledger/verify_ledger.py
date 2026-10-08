#!/usr/bin/env python3
"""
verify_ledger.py — OpenComplAI evidence ledger integrity verifier.

Performs two independent checks:

  1. Chain integrity  — calls /v1/evidence/verify-chain and confirms the
     Merkle-linked ledger is intact (no event has been modified in place).

  2. Dossier anchor   — when --dossier is supplied, walks the chain history
     (a page at a time) via /v1/evidence/ledger-history-tips and confirms the
     dossier's recorded record_keeping.ledger_root_hash appears at some
     historical point in the chain (dossiers generated before the Art. 12
     record-keeping split still carry this hash at the legacy
     section4.ledger_root_hash location, which is read as a fallback). This
     catches the threat that Gap #4 was designed to address: an attacker who
     truncates the ledger, removes an inconvenient event, and then recomputes
     all subsequent prev_hash values so verify-chain still returns True.
     verify-chain alone cannot detect that attack; the anchor check can.

Usage:
    python3 verify_ledger.py
    python3 verify_ledger.py --gateway-url https://opencomplai.example.com
    python3 verify_ledger.py --evidence-vault-url http://localhost:8002
    python3 verify_ledger.py --dossier dossier.json
    python3 verify_ledger.py --dossier dossier.json --gateway-url http://localhost:3000

Zero runtime dependencies — uses only the Python standard library.

Exit codes:
    0  — all checks pass (ledger valid; anchor matched if --dossier supplied)
    1  — chain integrity check failed (tampering or corruption detected)
    2  — connectivity / configuration error, rate limited (HTTP 429), or a
         malformed vault response
    3  — dossier anchor mismatch (the dossier's root hash is not in chain history)
    4  — dossier anchor is null (anchoring failed at generation time)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import NoReturn

# Tips requested per page of /v1/evidence/ledger-history-tips: the vault's
# maximum, so the fewest requests (the gateway rate-limits at 300 a minute by
# default, and the walk can cover the whole chain).
_TIPS_PAGE_SIZE = 5000


class RateLimitedError(RuntimeError):
    """The server answered HTTP 429."""

    kind = "rate limited"


class VaultProtocolError(RuntimeError):
    """The vault's response broke the paging contract."""

    kind = "vault protocol error"


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------


def _get_json(url: str, timeout: int = 10) -> dict:
    """Fetch a JSON URL and return the parsed dict. Raises on HTTP errors."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 429:
            raise RateLimitedError(
                f"HTTP 429 from {url}: {body} -- too many requests. Wait for "
                "the rate-limit window to pass (the gateway's default is 60 "
                "seconds) and run the check again; on a very large ledger "
                "raise OPENCOMPLAI_RATE_LIMIT_MAX on the gateway."
            ) from exc
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot connect to {url}: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Check 1 — chain integrity
# ---------------------------------------------------------------------------


def check_chain_integrity(base_url: str, timeout: int = 10) -> bool:
    """
    Call the verify-chain endpoint and return True if the chain is valid.

    Tries the gateway path first; callers pass the fully-resolved base URL.
    Returns True if valid, False if invalid.
    Raises RuntimeError on connectivity problems.
    """
    url = base_url.rstrip("/") + "/v1/evidence/verify-chain"
    print(f"[INFO]  Check 1 — chain integrity at: {url}")
    result = _get_json(url, timeout=timeout)
    return bool(result.get("valid", False))


# ---------------------------------------------------------------------------
# Check 2 — dossier anchor verification
# ---------------------------------------------------------------------------


def _extract_ledger_anchor(dossier: dict) -> str | None:
    """
    Read the dossier's ledger anchor hash.

    `record_keeping.ledger_root_hash` is the current location (Art. 12
    record-keeping was split out of Annex IV point 4 into its own
    `ArticleTwelveRecordKeeping` model — see packages/core/dossier.py).
    `section4.ledger_root_hash` is the legacy pre-split location, kept here
    as a fallback so dossiers generated before the split still verify.
    """
    record_keeping = dossier.get("record_keeping")
    if isinstance(record_keeping, dict):
        anchor = record_keeping.get("ledger_root_hash")
        if anchor:
            return anchor

    legacy_section4 = dossier.get("section4")
    if isinstance(legacy_section4, dict):
        return legacy_section4.get("ledger_root_hash")

    return None


def check_dossier_anchor(
    base_url: str, dossier_path: str, timeout: int = 10
) -> tuple[bool, str]:
    """
    Verify that the dossier's ledger anchor hash appears in the chain's
    historical rolling tips.

    Returns (True, "") on success or (False, reason) on failure.
    """
    # Load and parse the dossier
    try:
        with open(dossier_path) as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read dossier file {dossier_path!r}: {exc}") from exc

    # Support both flat dossier JSON and envelope {"dossier": {...}}
    dossier = raw.get("dossier", raw)
    anchor: str | None = (
        _extract_ledger_anchor(dossier) if isinstance(dossier, dict) else None
    )

    if not anchor:
        return False, (
            "record_keeping.ledger_root_hash (and legacy section4."
            "ledger_root_hash) is null — anchoring failed at dossier "
            "generation time (check EVIDENCE_VAULT_URL on the doc-generator)."
        )

    # Fetch the rolling chain tips from the evidence vault a page at a time,
    # stopping as soon as the anchor turns up.
    tips_url = base_url.rstrip("/") + "/v1/evidence/ledger-history-tips"
    print(f"[INFO]  Check 2 — fetching chain history from: {tips_url}")
    examined = 0
    after_seq = 0
    while True:
        data = _get_json(
            f"{tips_url}?limit={_TIPS_PAGE_SIZE}&after_seq={after_seq}",
            timeout=timeout,
        )
        tips: list[str] = data.get("tips", [])
        # A paged response lists the genesis hash separately from the per-event
        # tips; the unpaged shape carries it at tips[0].
        if after_seq == 0 and data.get("genesis"):
            tips = [data["genesis"], *tips]
        examined += len(tips)
        if anchor in tips:
            return True, ""

        # No cursor means the last page, or a vault that predates paging and
        # ignored the parameters: either way the response was the whole chain.
        next_after_seq = data.get("next_after_seq")
        if next_after_seq is None:
            break
        if not isinstance(next_after_seq, int) or next_after_seq <= after_seq:
            raise VaultProtocolError(
                f"malformed cursor from the vault: {tips_url} returned "
                f"next_after_seq={next_after_seq!r} after after_seq={after_seq} "
                "(it must be an integer greater than the previous cursor)"
            )
        after_seq = next_after_seq

    return False, (
        f"Dossier anchor '{anchor}' does not appear in {examined} historical "
        "chain tips — the ledger may have been truncated or events deleted since "
        "this dossier was generated."
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def check_health(base_url: str) -> bool:
    """Return True if the service health endpoint reports ok."""
    try:
        health_url = base_url.rstrip("/") + "/health"
        data = _get_json(health_url, timeout=5)
        return data.get("status") == "ok"
    except RuntimeError:
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify OpenComplAI evidence ledger chain integrity and (optionally) "
            "confirm that a dossier's anchor hash is still present in the chain."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--gateway-url",
        default=os.environ.get("OPENCOMPLAI_GATEWAY_URL", "http://localhost:3000"),
        help="OpenComplAI gateway URL (default: $OPENCOMPLAI_GATEWAY_URL or http://localhost:3000)",
    )
    parser.add_argument(
        "--evidence-vault-url",
        default=os.environ.get("EVIDENCE_VAULT_URL", ""),
        help="Direct evidence-vault URL — bypasses gateway (optional)",
    )
    parser.add_argument(
        "--dossier",
        metavar="PATH",
        default=None,
        help=(
            "Path to a dossier JSON file. When supplied, performs the anchor check "
            "(Check 2): confirms that the dossier's record_keeping.ledger_root_hash "
            "(or the legacy section4.ledger_root_hash) appears in the chain's "
            "rolling history (detects ledger truncation)."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP request timeout in seconds (default: 10)",
    )
    return parser.parse_args()


def _exit_on_error(check: str, exc: RuntimeError) -> NoReturn:
    """Report a failed check and exit 2, naming the kind of failure."""
    kind = getattr(exc, "kind", "connectivity error")
    print(f"[ERROR] {check} {kind}: {exc}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    args = _parse_args()

    gateway_url: str = args.gateway_url
    vault_url: str = args.evidence_vault_url or ""

    # Resolve the base URL: direct vault beats gateway
    base_url = vault_url.rstrip("/") if vault_url else gateway_url.rstrip("/")

    # Health check (non-fatal)
    if not check_health(base_url):
        print(f"[WARN]  Health check failed for {base_url} — attempting checks anyway")

    # ---------------------------------------------------------------------------
    # Check 1 — chain integrity
    # ---------------------------------------------------------------------------
    try:
        chain_valid = check_chain_integrity(base_url, timeout=args.timeout)
    except RuntimeError as exc:
        _exit_on_error("Check 1", exc)

    if chain_valid:
        print("[PASS]  Check 1 — chain integrity: valid (no tampering detected)")
    else:
        print(
            "[FAIL]  Check 1 — chain integrity: INVALID — tampering or corruption "
            "detected!",
            file=sys.stderr,
        )
        sys.exit(1)

    # ---------------------------------------------------------------------------
    # Check 2 — dossier anchor (optional, only when --dossier is supplied)
    # ---------------------------------------------------------------------------
    if args.dossier:
        try:
            anchor_ok, reason = check_dossier_anchor(
                base_url, args.dossier, timeout=args.timeout
            )
        except RuntimeError as exc:
            _exit_on_error("Check 2", exc)

        if anchor_ok:
            print(
                "[PASS]  Check 2 — dossier anchor: found in chain history "
                f"(dossier: {args.dossier})"
            )
        else:
            # Distinguish null anchor (exit 4) from mismatch (exit 3)
            if "null" in reason:
                print(
                    f"[WARN]  Check 2 — dossier anchor null: {reason}", file=sys.stderr
                )
                sys.exit(4)
            else:
                print(
                    f"[FAIL]  Check 2 — dossier anchor mismatch: {reason}",
                    file=sys.stderr,
                )
                sys.exit(3)

    sys.exit(0)


if __name__ == "__main__":
    main()
