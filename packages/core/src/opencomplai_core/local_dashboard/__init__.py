"""Local developer dashboard — localhost only (not Pro / dashboard-saas)."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opencomplai_core.output_envelope import wrap_scan_output

_HISTORY_LIMIT = 50


def history_dir(project_root: Path) -> Path:
    """XDG-ish local history root for a project."""
    base = Path.home() / ".opencomplai" / "scan-history"
    digest = abs(hash(str(project_root.resolve()))) % (10**12)
    path = base / f"p{digest}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_history(project_root: Path, *, limit: int = _HISTORY_LIMIT) -> list[dict[str, Any]]:
    root = history_dir(project_root)
    files = sorted(root.glob("*.json"), reverse=True)
    records: list[dict[str, Any]] = []
    for path in files[:limit]:
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return records


def save_history_record(project_root: Path, payload: dict[str, Any]) -> Path:
    root = history_dir(project_root)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    path = root / f"{stamp}-{int(time.time() * 1000) % 1000:03d}.json"
    envelope = wrap_scan_output(payload)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(envelope.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)
    # Cap history
    files = sorted(root.glob("*.json"), reverse=True)
    for stale in files[_HISTORY_LIMIT:]:
        try:
            stale.unlink()
        except OSError:
            pass
    return path


def create_app(project_root: Path):
    """Build a FastAPI app bound for loopback use only."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
        from fastapi.middleware.trustedhost import TrustedHostMiddleware
    except ImportError as exc:
        msg = (
            "Local serve requires the optional CLI extra: "
            "pip install 'opencomplai-cli[serve]'"
        )
        raise ImportError(msg) from exc

    app = FastAPI(title="OpenComplAI local dashboard", docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _DASHBOARD_HTML

    @app.get("/api/history")
    def api_history() -> JSONResponse:
        return JSONResponse(list_history(project_root))

    @app.post("/api/scan")
    def api_scan() -> JSONResponse:
        from opencomplai_core.models import SystemManifest
        from opencomplai_core.scan_engine import run_scan

        manifest_path = project_root / "system-manifest.json"
        if manifest_path.is_file():
            manifest = SystemManifest.model_validate(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
            system_id = manifest.system_id
            purpose = manifest.intended_purpose
        else:
            system_id = "local-serve"
            purpose = "quick local serve scan"

        report = run_scan(
            system_id=system_id,
            commit_ref="HEAD",
            repo_root=project_root,
            declared_purpose=purpose,
        )
        payload = json.loads(report.model_dump_json())
        path = save_history_record(project_root, payload)
        return JSONResponse(
            {
                "history_path": str(path),
                "severity": report.severity.value,
                "detected_categories": report.detected_categories,
                "scan_errors": report.scan_errors,
            }
        )

    return app


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OpenComplAI — local dashboard</title>
<style>
 body{font-family:system-ui,sans-serif;margin:2rem;max-width:960px}
 button{padding:.5rem 1rem;cursor:pointer}
 table{border-collapse:collapse;width:100%;margin-top:1rem}
 td,th{border:1px solid #ddd;padding:.4rem;text-align:left;font-size:.9rem}
 .note{color:#555;font-size:.9rem}
</style>
</head>
<body>
<h1>OpenComplAI local dashboard</h1>
<p class="note">
  Loopback only — this is <strong>not</strong> the Pro / SaaS dashboard.
  History stays on this machine under <code>~/.opencomplai/scan-history/</code>.
</p>
<button id="run">Run scan</button>
<pre id="status"></pre>
<h2>Recent history</h2>
<table id="hist"><tr><th>When</th><th>Severity</th><th>Categories</th></tr></table>
<script>
async function refresh(){
  const rows = await (await fetch('/api/history')).json();
  const t = document.getElementById('hist');
  t.innerHTML = '<tr><th>When</th><th>Severity</th><th>Categories</th></tr>';
  for (const r of rows){
    const p = r.payload || r;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${r.generated_at||''}</td><td>${(p.severity||'')}</td><td>${(p.detected_categories||[]).join(', ')}</td>`;
    t.appendChild(tr);
  }
}
document.getElementById('run').onclick = async () => {
  document.getElementById('status').textContent = 'Scanning…';
  const res = await fetch('/api/scan', {method:'POST'});
  document.getElementById('status').textContent = await res.text();
  refresh();
};
refresh();
</script>
</body>
</html>
"""
