#!/usr/bin/env python3
"""
verify_ledger.py — OpenComplAI evidence ledger integrity verifier.

Performs two independent checks:

  1. Chain integrity  — calls /v1/evidence/verify-chain and confirms the
     Merkle-linked ledger is intact (no event has been modified in place).

  2. Dossier anchor   — when --dossier is supplied, walks the chain history
     via /v1/evidence/ledger-history-tips and confirms the dossier's recorded
     section4.ledger_root_hash appears at some historical point in the chain.
     This catches the threat that Gap #4 was designed to address: an attacker
     who truncates the ledger, removes an inconvenient event, and then
     recomputes all subsequent prev_hash values so verify-chain still returns
     True.  verify-chain alone cannot detect that attack; the anchor check can.

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
    2  — connectivity / configuration error
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


def check_dossier_anchor(
    base_url: str, dossier_path: str, timeout: int = 10
) -> tuple[bool, str]:
    """
    Verify that the dossier's section4.ledger_root_hash appears in the chain's
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
        dossier.get("section4", {}).get("ledger_root_hash")
        if isinstance(dossier, dict)
        else None
    )

    if not anchor:
        return False, (
            "section4.ledger_root_hash is null — anchoring failed at dossier "
            "generation time (check EVIDENCE_VAULT_URL on the doc-generator)."
        )

    # Fetch the rolling chain tips from the evidence vault
    tips_url = base_url.rstrip("/") + "/v1/evidence/ledger-history-tips"
    print(f"[INFO]  Check 2 — fetching chain history from: {tips_url}")
    data = _get_json(tips_url, timeout=timeout)
    tips: list[str] = data.get("tips", [])

    if anchor in tips:
        return True, ""

    return False, (
        f"Dossier anchor '{anchor}' does not appear in {len(tips)} historical "
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
            "(Check 2): confirms that the dossier's section4.ledger_root_hash "
            "appears in the chain's rolling history (detects ledger truncation)."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP request timeout in seconds (default: 10)",
    )
    return parser.parse_args()


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
        print(f"[ERROR] Check 1 connectivity error: {exc}", file=sys.stderr)
        sys.exit(2)

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
            print(f"[ERROR] Check 2 connectivity error: {exc}", file=sys.stderr)
            sys.exit(2)

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
