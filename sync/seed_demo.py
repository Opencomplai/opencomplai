#!/usr/bin/env python3
"""
Seed demo data into a running OpenComplAI stack.

Usage:
    python scripts/seed_demo.py                # idempotent — safe to re-run
    python scripts/seed_demo.py --dry-run      # print what would be sent; touch nothing
    python scripts/seed_demo.py --gateway http://localhost:9000  # custom gateway URL

All demo records carry system_id prefixed with 'demo-' so reset_demo.py
can target-delete them without touching production data.
"""

from __future__ import annotations

import argparse
import json

# ---------------------------------------------------------------------------
# Bootstrap sys.path so the demo sub-package is importable without install
# ---------------------------------------------------------------------------
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))

from demo.bias_alerts import BIAS_ALERTS
from demo.dossiers import DOSSIER_MANIFESTS, dossier_ingest_metadata
from demo.ledger_events import HITL_EVENTS, RISK_CLASSIFICATION_EVENTS
from demo.scan_events import generate_scan_events
from demo.systems import DEMO_SYSTEMS, HIGH_RISK_SYSTEM_IDS

# ---------------------------------------------------------------------------
# Config / defaults
# ---------------------------------------------------------------------------

DEFAULT_GATEWAY = os.environ.get("DEMO_GATEWAY_URL", "http://localhost:8080")
DEFAULT_API_KEY = os.environ.get("DEMO_TENANT_API_KEY", "demo-api-key-local")
DEFAULT_VAULT = os.environ.get("DEMO_VAULT_URL", "http://localhost:8002")

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Api-Key": api_key,
    }


def _post(url: str, body: dict, *, dry_run: bool, api_key: str) -> dict | None:
    payload = json.dumps(body).encode()
    if dry_run:
        print(f"  [DRY-RUN] POST {url}")
        print(f"            {json.dumps(body, indent=2)[:300]}")
        return {"_dry_run": True}
    req = urllib.request.Request(
        url,
        data=payload,
        headers=_headers(api_key),
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


def _post_vault(url: str, body: dict, *, dry_run: bool) -> dict | None:
    """POST directly to evidence-vault (no API-key auth required internally)."""
    payload = json.dumps(body).encode()
    if dry_run:
        print(f"  [DRY-RUN] POST {url}")
        return {"_dry_run": True}
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        print(f"  [WARN] POST {url} → {exc}")
        return None


# ---------------------------------------------------------------------------
# Seeder steps
# ---------------------------------------------------------------------------


def step1_wait_for_stack(gateway: str, *, dry_run: bool) -> None:
    if dry_run:
        print("[1] Stack health check — skipped (dry-run)")
        return
    print("[1] Waiting for gateway-api to be healthy…")
    for attempt in range(20):
        try:
            with urllib.request.urlopen(f"{gateway}/health", timeout=5) as r:
                if r.status < 500:
                    print(f"    Gateway healthy (attempt {attempt + 1})")
                    return
        except Exception:
            pass
        time.sleep(3)
    print("  [WARN] Gateway did not become healthy — proceeding anyway")


def step2_ingest_risk_classifications(vault: str, *, dry_run: bool) -> dict[str, str]:
    """Append a risk_classification ledger event for each demo system."""
    print("[2] Appending risk-classification ledger events…")
    event_ids: dict[str, str] = {}
    for system_id, event_body in RISK_CLASSIFICATION_EVENTS.items():
        resp = _post_vault(f"{vault}/v1/evidence/events", event_body, dry_run=dry_run)
        if resp and not resp.get("_dry_run"):
            event_ids[system_id] = resp.get("event_id", "")
            print(f"    ✓ {system_id} classified → event {event_ids[system_id][:8]}…")
        else:
            event_ids[system_id] = ""
    return event_ids


def step3_ingest_scan_artifacts(
    gateway: str,
    api_key: str,
    *,
    dry_run: bool,
) -> dict[str, list[dict]]:
    """Generate and ingest 30 scan-status artifacts per system."""
    print("[3] Ingesting scan-status artifacts…")
    results: dict[str, list[dict]] = {}
    for system in DEMO_SYSTEMS:
        sid = system["system_id"]
        events = generate_scan_events(sid)
        print(f"    {sid}: {len(events)} events", end="", flush=True)
        ingested = []
        for event in events:
            # Strip internal-only keys before sending
            metrics = event.pop("_metrics", {})
            policy_ver = event.pop("_policy_bundle_version", None)

            resp = _post(
                f"{gateway}/v1/pro/ingest/status-artifact",
                event,
                dry_run=dry_run,
                api_key=api_key,
            )
            if resp is not None:
                ingested.append(resp)

            # Also POST metrics
            if metrics:
                _post(
                    f"{gateway}/v1/pro/ingest/metrics",
                    metrics,
                    dry_run=dry_run,
                    api_key=api_key,
                )

            # POST dossier-metadata when policy_bundle_version is present
            if policy_ver:
                _post(
                    f"{gateway}/v1/pro/ingest/dossier-metadata",
                    {
                        "system_id": sid,
                        "policy_bundle_version": policy_ver,
                        "bundle_checksum": event.get("bundle_checksum"),
                        "timestamp": event.get("timestamp"),
                    },
                    dry_run=dry_run,
                    api_key=api_key,
                )

        results[sid] = ingested
        print(f" → {len(ingested)} ingested")
    return results


def step4_generate_dossiers(
    gateway: str,
    api_key: str,
    *,
    dry_run: bool,
) -> dict[str, list[str]]:
    """Generate Annex IV dossiers for HIGH-risk systems via doc-generator."""
    print("[4] Generating Annex IV dossiers for HIGH-risk systems…")
    dossier_ids: dict[str, list[str]] = {}
    for system_id in HIGH_RISK_SYSTEM_IDS:
        manifests = DOSSIER_MANIFESTS.get(system_id, [])
        dossier_ids[system_id] = []
        for idx, manifest in enumerate(manifests):
            resp = _post(
                f"{gateway}/v1/docs/generate",
                manifest,
                dry_run=dry_run,
                api_key=api_key,
            )
            dossier_id = (resp or {}).get(
                "dossier_id", f"demo-dossier-{system_id}-{idx}"
            )
            dossier_ids[system_id].append(dossier_id)
            print(f"    ✓ {system_id} dossier #{idx + 1} → {dossier_id[:16]}…")

            # Ingest dossier metadata
            meta = dossier_ingest_metadata(system_id, commit_ref="HEAD", idx=idx)
            _post(
                f"{gateway}/v1/pro/ingest/dossier-metadata",
                meta,
                dry_run=dry_run,
                api_key=api_key,
            )
    return dossier_ids


def step5_issue_badges(
    gateway: str,
    api_key: str,
    scan_results: dict[str, list[dict]],
    *,
    dry_run: bool,
) -> dict[str, str]:
    """Issue a compliance badge for each demo system from its latest scan."""
    print("[5] Issuing compliance badges…")
    badge_urls: dict[str, str] = {}
    for system in DEMO_SYSTEMS:
        sid = system["system_id"]
        import hashlib

        bundle_checksum = (
            "sha256:" + hashlib.sha256(f"badge-{sid}".encode()).hexdigest()
        )
        artifact = {
            "system_id": sid,
            "result": "pass",
            "commit_ref": "HEAD",
            "risk_class": system["risk_class"],
            "pending_verifications_count": 0,
        }
        resp = _post(
            f"{gateway}/v1/pro/badges/issue",
            {
                "system_id": sid,
                "bundle_checksum": bundle_checksum,
                "artifact": artifact,
            },
            dry_run=dry_run,
            api_key=api_key,
        )
        badge_id = (resp or {}).get("badge_id", "")
        badge_url = f"{gateway}/v1/pro/badges/{badge_id}/svg" if badge_id else "N/A"
        badge_urls[sid] = badge_url
        print(f"    ✓ {sid} → badge {badge_id[:16] if badge_id else 'N/A'}…")
    return badge_urls


def step6_inject_hitl_events(vault: str, *, dry_run: bool) -> None:
    """Append HITL halt/resume ledger events for demo-hr-hiring-v2."""
    print("[6] Injecting HITL halt/resume ledger events for demo-hr-hiring-v2…")
    for event in HITL_EVENTS:
        resp = _post_vault(f"{vault}/v1/evidence/events", event, dry_run=dry_run)
        event_type = event["event_type"]
        event_id = (resp or {}).get("event_id", "")
        print(f"    ✓ {event_type} → {event_id[:8] if event_id else 'dry-run'}…")


def step7_inject_bias_alerts(vault: str, *, dry_run: bool) -> None:
    """Store bias alerts for credit scoring and HR hiring."""
    print("[7] Injecting bias alerts…")
    for alert in BIAS_ALERTS:
        resp = _post_vault(f"{vault}/v1/bias-alerts", alert, dry_run=dry_run)
        alert_id = (resp or {}).get("alert_id", alert["alert_id"])
        print(
            f"    ✓ [{alert['severity']:6s}] {alert['system_id']} "
            f"/ {alert['metric']} → {alert_id[:8]}…"
        )


def _print_summary(
    badge_urls: dict[str, str],
    scan_results: dict[str, list[dict]],
    dossier_ids: dict[str, list[str]],
    *,
    dry_run: bool,
) -> None:
    tag = " (DRY RUN)" if dry_run else ""
    print(f"\n{'=' * 70}")
    print(f"  OpenComplAI Demo Seed Summary{tag}")
    print(f"{'=' * 70}")
    print(f"  {'System':<35} {'Events':>6}  {'Badge URL'}")
    print(f"  {'-' * 35} {'-' * 6}  {'-' * 20}")
    for system in DEMO_SYSTEMS:
        sid = system["system_id"]
        count = len(scan_results.get(sid, []))
        url = badge_urls.get(sid, "N/A")
        print(f"  {sid:<35} {count:>6}  {url}")
    print()
    print("  Dossiers generated:")
    for sid, ids in dossier_ids.items():
        for did in ids:
            print(f"    {sid}: {did}")
    bias_count = len(BIAS_ALERTS)
    hitl_count = len(HITL_EVENTS)
    print(f"\n  Bias alerts injected : {bias_count}")
    print(f"  HITL ledger events   : {hitl_count}")
    print(f"{'=' * 70}\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gateway",
        default=DEFAULT_GATEWAY,
        help=f"Gateway API base URL (default: {DEFAULT_GATEWAY})",
    )
    parser.add_argument(
        "--vault",
        default=DEFAULT_VAULT,
        help=f"Evidence Vault base URL (default: {DEFAULT_VAULT})",
    )
    parser.add_argument(
        "--api-key",
        default=DEFAULT_API_KEY,
        help=f"X-Api-Key header value (default: {DEFAULT_API_KEY})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads without touching the database",
    )
    args = parser.parse_args()

    print("\nOpenComplAI demo seeder")
    print(f"  Gateway : {args.gateway}")
    print(f"  Vault   : {args.vault}")
    print(f"  API key : {args.api_key[:8]}…")
    if args.dry_run:
        print("  Mode    : DRY RUN — no data will be written\n")
    else:
        print()

    step1_wait_for_stack(args.gateway, dry_run=args.dry_run)
    step2_ingest_risk_classifications(args.vault, dry_run=args.dry_run)
    scan_results = step3_ingest_scan_artifacts(
        args.gateway, args.api_key, dry_run=args.dry_run
    )
    dossier_ids = step4_generate_dossiers(
        args.gateway, args.api_key, dry_run=args.dry_run
    )
    badge_urls = step5_issue_badges(
        args.gateway, args.api_key, scan_results, dry_run=args.dry_run
    )
    step6_inject_hitl_events(args.vault, dry_run=args.dry_run)
    step7_inject_bias_alerts(args.vault, dry_run=args.dry_run)

    _print_summary(badge_urls, scan_results, dossier_ids, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
