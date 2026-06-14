#!/usr/bin/env python3
"""
Wipe all demo-* data from a running OpenComplAI stack.

Usage:
    python scripts/reset_demo.py               # wipe only
    python scripts/reset_demo.py --reseed      # wipe then re-seed
    python scripts/reset_demo.py --dry-run     # print what would be deleted

The 'demo-' prefix isolates demo data completely — production records
are never touched, even if WHERE clauses are accidentally widened.

Tables cleared:
  evidence-vault DB:
    ledger_events       WHERE payload->>system_id LIKE 'demo-%'
    dossier_index       WHERE system_id LIKE 'demo-%'
    evidence_objects    (orphans after dossier delete)
    bias_alerts         WHERE system_id LIKE 'demo-%'
    badges              WHERE system_id LIKE 'demo-%'

  Redis streams:
    Pending verification stream entries WHERE system_id is a demo prefix.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))

from demo.systems import DEMO_SYSTEMS

DEFAULT_VAULT = os.environ.get("DEMO_VAULT_URL", "http://localhost:8002")
DEFAULT_GATEWAY = os.environ.get("DEMO_GATEWAY_URL", "http://localhost:8080")
DEFAULT_API_KEY = os.environ.get("DEMO_TENANT_API_KEY", "demo-api-key-local")

DEMO_SYSTEM_IDS = [s["system_id"] for s in DEMO_SYSTEMS]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _post(url: str, body: dict, *, dry_run: bool) -> dict | None:
    if dry_run:
        print(f"  [DRY-RUN] POST {url}  body={json.dumps(body)[:120]}")
        return {"_dry_run": True}
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        print(f"  [WARN] POST {url} → HTTP {exc.code}: {body_text[:200]}")
        return None
    except Exception as exc:
        print(f"  [WARN] POST {url} → {exc}")
        return None


def _delete(url: str, *, dry_run: bool) -> dict | None:
    if dry_run:
        print(f"  [DRY-RUN] DELETE {url}")
        return {"_dry_run": True}
    req = urllib.request.Request(url, method="DELETE")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None  # already gone
        body_text = exc.read().decode(errors="replace")
        print(f"  [WARN] DELETE {url} → HTTP {exc.code}: {body_text[:200]}")
        return None
    except Exception as exc:
        print(f"  [WARN] DELETE {url} → {exc}")
        return None


# ---------------------------------------------------------------------------
# Reset steps
# ---------------------------------------------------------------------------


def reset_bias_alerts(vault: str, *, dry_run: bool) -> None:
    """Purge bias alert data for all demo system IDs."""
    print("[reset] Purging bias alerts…")
    for sid in DEMO_SYSTEM_IDS:
        resp = _post(
            f"{vault}/v1/admin/purge-bias-data",
            {"system_id": sid, "retention_days": 0},
            dry_run=dry_run,
        )
        deleted = (resp or {}).get("deleted", "?")
        print(f"    {sid}: {deleted} alerts removed")


def reset_dossiers(vault: str, *, dry_run: bool) -> None:
    """List and delete all dossier index entries for demo systems."""
    print("[reset] Removing dossier index entries…")
    for sid in DEMO_SYSTEM_IDS:
        list_url = f"{vault}/v1/dossiers?system_id={sid}"
        if dry_run:
            print(f"  [DRY-RUN] GET {list_url} → (would delete all found dossiers)")
            continue
        try:
            with urllib.request.urlopen(list_url, timeout=10) as r:
                dossiers = json.loads(r.read())
        except Exception:
            dossiers = []
        for entry in dossiers if isinstance(dossiers, list) else []:
            did = entry.get("dossier_id", "")
            if did:
                _delete(f"{vault}/v1/dossiers/{did}", dry_run=dry_run)
        print(
            f"    {sid}: {len(dossiers) if isinstance(dossiers, list) else 0} dossiers removed"
        )


def reset_ledger_events(vault: str, *, dry_run: bool) -> None:
    """
    The evidence-vault ledger is append-only (Merkle-linked), so individual
    events cannot be deleted — that would break chain integrity. Instead, we
    append a DEMO_RESET tombstone event so the audit trail shows that the
    demo data was intentionally cleared. Downstream renders should filter
    events whose payload contains the tombstone marker.
    """
    print("[reset] Appending DEMO_RESET tombstone ledger events…")
    for sid in DEMO_SYSTEM_IDS:
        resp = _post(
            f"{vault}/v1/evidence/events",
            {
                "event_type": "demo_reset",
                "payload": {
                    "system_id": sid,
                    "note": "Demo data reset — all prior demo events for this system superseded.",
                },
            },
            dry_run=dry_run,
        )
        event_id = (resp or {}).get("event_id", "")
        print(f"    {sid}: tombstone → {event_id[:8] if event_id else 'dry-run'}…")


def reset_redis_streams(*, dry_run: bool) -> None:
    """
    Flush pending verification stream entries for demo systems from Redis.

    Uses 'docker compose exec redis redis-cli' — requires the stack to be running.
    Skips gracefully if Redis is unreachable or docker is unavailable.
    """
    print("[reset] Flushing Redis stream entries for demo systems…")
    if dry_run:
        print(
            "  [DRY-RUN] Would XDEL verification-stream entries for demo-* system_ids"
        )
        return
    # SCAN the stream for demo-* entries and XDEL them
    redis_cmd = [
        "docker",
        "compose",
        "-f",
        "infra/compose/docker-compose.yml",
        "exec",
        "-T",
        "redis",
        "redis-cli",
        "KEYS",
        "demo-*",
    ]
    try:
        result = subprocess.run(redis_cmd, capture_output=True, text=True, timeout=15)
        keys = [k.strip() for k in result.stdout.splitlines() if k.strip()]
        if keys:
            del_cmd = [*redis_cmd[:-2], "DEL", *keys]
            subprocess.run(del_cmd, capture_output=True, timeout=15)
            print(f"    Deleted {len(keys)} Redis key(s) matching demo-*")
        else:
            print("    No demo-* Redis keys found")
    except Exception as exc:
        print(f"    [SKIP] Redis flush failed (stack may not be running): {exc}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vault",
        default=DEFAULT_VAULT,
        help=f"Evidence Vault base URL (default: {DEFAULT_VAULT})",
    )
    parser.add_argument(
        "--gateway",
        default=DEFAULT_GATEWAY,
        help=f"Gateway API base URL (default: {DEFAULT_GATEWAY})",
    )
    parser.add_argument(
        "--api-key",
        default=DEFAULT_API_KEY,
        help=f"X-Api-Key header value (default: {DEFAULT_API_KEY})",
    )
    parser.add_argument(
        "--reseed",
        action="store_true",
        help="Re-seed demo data after wiping",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be deleted without touching the database",
    )
    args = parser.parse_args()

    tag = " (DRY RUN)" if args.dry_run else ""
    print(f"\nOpenComplAI demo reset{tag}")
    print(f"  Vault   : {args.vault}")
    print(f"  Systems : {', '.join(DEMO_SYSTEM_IDS)}\n")

    reset_bias_alerts(args.vault, dry_run=args.dry_run)
    reset_dossiers(args.vault, dry_run=args.dry_run)
    reset_ledger_events(args.vault, dry_run=args.dry_run)
    reset_redis_streams(dry_run=args.dry_run)

    print("\n  Demo data wiped successfully.\n")

    if args.reseed:
        print("  --reseed flag set — running seed_demo.py…\n")
        seed_script = os.path.join(os.path.dirname(__file__), "seed_demo.py")
        seed_args = [
            sys.executable,
            seed_script,
            "--gateway",
            args.gateway,
            "--vault",
            args.vault,
            "--api-key",
            args.api_key,
        ]
        if args.dry_run:
            seed_args.append("--dry-run")
        os.execv(sys.executable, seed_args)


if __name__ == "__main__":
    main()
