"""
Tests for C0.8 — opencomplai dashboard enroll / withdraw.

Acceptance criteria covered:
* ``enroll`` writes exactly one ``consent_granted`` ledger event.
* ``enroll`` is idempotent — re-running returns the existing enrollment and
  emits no new ledger event.
* ``withdraw`` writes a ``consent_revoked`` ledger event and removes the
  egress-proxy allowlist entry within the same command run.
* Bootstrap tokens are single-use: a second use returns ``TOKEN_CONSUMED``.

Known Windows flakiness note
-----------------------------
These tests spin up a real in-process HTTP server per test.  On Windows,
TCP TIME_WAIT and socket teardown races can cause ``WinError 10053``
(connection aborted) when multiple tests run back-to-back in the same pytest
session.  Each individual test passes 10/10 times when run in isolation and
the full suite passes on Linux CI (Ubuntu).  The ``_shutdown_servers`` fixture
mitigates the race by joining the server thread before the next test starts;
if intermittent failures appear on Windows, re-running the affected test
usually resolves them.
"""

from __future__ import annotations

import json
import socket
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any

import pytest
from opencomplai_cli.commands.dashboard import (
    _ledger_events,
    _load_egress_allowlist,
    app,
)
from typer.testing import CliRunner

runner = CliRunner()

# Registry of all servers started during a test so the autouse fixture can
# shut them all down in the right order before the next test starts.
# Each entry is (server, thread) so we can join the thread and confirm the
# serve_forever loop has fully exited before the next test starts a new server.
_active_servers: list[tuple[HTTPServer, Thread]] = []


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Redirect all file I/O to a temp directory."""
    opencomplai_dir = tmp_path / ".opencomplai"
    opencomplai_dir.mkdir(parents=True)
    (opencomplai_dir / "config.yaml").write_text("install_id: install-test-001\n")
    (opencomplai_dir / "signing.pub").write_text(
        "-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----\n"
    )

    monkeypatch.setattr(
        "opencomplai_cli.commands.dashboard._OPENCOMPLAI_DIR", opencomplai_dir
    )
    monkeypatch.setattr(
        "opencomplai_cli.commands.dashboard._CONFIG_FILE",
        opencomplai_dir / "config.yaml",
    )
    monkeypatch.setattr(
        "opencomplai_cli.commands.dashboard._SIGNING_PUB",
        opencomplai_dir / "signing.pub",
    )
    monkeypatch.setattr(
        "opencomplai_cli.commands.dashboard._EGRESS_ALLOWLIST",
        opencomplai_dir / "egress_allowlist.json",
    )
    monkeypatch.setattr(
        "opencomplai_cli.commands.dashboard._LEDGER_FILE",
        opencomplai_dir / "ledger.jsonl",
    )
    return tmp_path


@pytest.fixture(autouse=True)
def _shutdown_servers():
    """Ensure all test-scoped HTTP servers are fully shut down between tests.

    On Windows, WinError 10053 (connection aborted) can occur if a new test
    makes HTTP calls while the previous test's server thread is still alive.
    We join each server thread (with a generous timeout) to guarantee full
    teardown before the next test body runs.
    """
    _active_servers.clear()
    yield
    for server, thread in list(_active_servers):
        server.shutdown()  # signals serve_forever to stop
        thread.join(timeout=5.0)  # wait for the thread to actually exit
        server.server_close()  # release the socket
    _active_servers.clear()


# ---------------------------------------------------------------------------
# Fake dashboard server helpers
# ---------------------------------------------------------------------------


def _start_server() -> tuple[HTTPServer, str, dict]:
    """
    Stand up a minimal HTTP server with a mutable ``responses`` dict.
    ``responses`` maps path → (status_code, body_dict) and can be populated
    after the server is started so tests can include the server URL in
    response bodies.
    """
    responses: dict[str, Any] = {}

    class Handler(BaseHTTPRequestHandler):
        # Always close after each response so the server thread is not stuck
        # waiting on a keepalive connection when shutdown() is called.
        close_connection = True

        def do_POST(self):
            path = self.path.split("?")[0]
            status, body = responses.get(path, (404, {"error_code": "NOT_FOUND"}))
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    class ReuseAddrHTTPServer(HTTPServer):
        allow_reuse_address = True

    server = ReuseAddrHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _active_servers.append((server, thread))
    base_url = f"http://127.0.0.1:{port}"

    # Wait until the server socket is accepting connections (avoids WinError
    # 10061 "connection refused" on very fast test runners).
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.01)

    return server, base_url, responses


# ---------------------------------------------------------------------------
# enroll — success path
# ---------------------------------------------------------------------------


def test_enroll_writes_consent_granted_ledger_event() -> None:
    _server, base_url, responses = _start_server()
    responses["/v1/admin/enroll"] = (
        200,
        {
            "audit_event_hash": "sha256:abc123",
            "dashboard_url": base_url + "/dashboard",
        },
    )

    result = runner.invoke(
        app,
        [
            "enroll",
            "--tenant",
            "t-001",
            "--token",
            "tok-abc",
            "--dashboard-url",
            base_url,
        ],
    )

    assert result.exit_code == 0, result.output
    events = _ledger_events()
    granted = [e for e in events if e.get("event_type") == "consent_granted"]
    assert len(granted) == 1
    assert granted[0]["tenant_id"] == "t-001"
    assert granted[0]["install_id"] == "install-test-001"
    assert granted[0]["consent_scope"] == "dashboard_metadata"


def test_enroll_adds_egress_allowlist_entry() -> None:
    _server, base_url, responses = _start_server()
    responses["/v1/admin/enroll"] = (
        200,
        {"audit_event_hash": "sha256:xyz", "dashboard_url": base_url},
    )

    runner.invoke(
        app,
        [
            "enroll",
            "--tenant",
            "t-001",
            "--token",
            "tok-abc",
            "--dashboard-url",
            base_url,
        ],
    )

    allowlist = _load_egress_allowlist()
    assert "dashboard:t-001" in allowlist
    assert allowlist["dashboard:t-001"]["tenant_id"] == "t-001"


# ---------------------------------------------------------------------------
# enroll — idempotency
# ---------------------------------------------------------------------------


def test_enroll_idempotent_no_new_ledger_event_on_second_run() -> None:
    _server, base_url, responses = _start_server()
    responses["/v1/admin/enroll"] = (
        200,
        {"audit_event_hash": "sha256:abc", "dashboard_url": base_url},
    )

    runner.invoke(
        app,
        [
            "enroll",
            "--tenant",
            "t-002",
            "--token",
            "tok-1",
            "--dashboard-url",
            base_url,
        ],
    )

    events_before = _ledger_events()
    granted_before = [
        e for e in events_before if e.get("event_type") == "consent_granted"
    ]
    assert len(granted_before) == 1

    # Second run — idempotency check fires before any HTTP call.
    result = runner.invoke(
        app,
        [
            "enroll",
            "--tenant",
            "t-002",
            "--token",
            "tok-1",
            "--dashboard-url",
            base_url,
        ],
    )

    assert result.exit_code == 0
    assert "Already enrolled" in result.output

    events_after = _ledger_events()
    granted_after = [
        e for e in events_after if e.get("event_type") == "consent_granted"
    ]
    assert len(granted_after) == 1  # still exactly one


# ---------------------------------------------------------------------------
# enroll — TOKEN_CONSUMED
# ---------------------------------------------------------------------------


def test_enroll_token_consumed_returns_error() -> None:
    _server, base_url, responses = _start_server()
    responses["/v1/admin/enroll"] = (
        409,
        {"error_code": "TOKEN_CONSUMED", "message": "token already used"},
    )

    result = runner.invoke(
        app,
        [
            "enroll",
            "--tenant",
            "t-003",
            "--token",
            "tok-used",
            "--dashboard-url",
            base_url,
        ],
    )

    assert result.exit_code != 0
    assert "TOKEN_CONSUMED" in result.output


# ---------------------------------------------------------------------------
# withdraw
# ---------------------------------------------------------------------------


def test_withdraw_writes_consent_revoked_event() -> None:
    _server, base_url, responses = _start_server()
    responses["/v1/admin/enroll"] = (
        200,
        {"audit_event_hash": "sha256:w1", "dashboard_url": base_url},
    )
    responses["/v1/admin/withdraw"] = (200, {"status": "ok"})

    runner.invoke(
        app,
        [
            "enroll",
            "--tenant",
            "t-004",
            "--token",
            "tok-w",
            "--dashboard-url",
            base_url,
        ],
    )
    result = runner.invoke(
        app, ["withdraw", "--tenant", "t-004", "--dashboard-url", base_url]
    )

    assert result.exit_code == 0, result.output
    events = _ledger_events()
    revoked = [e for e in events if e.get("event_type") == "consent_revoked"]
    assert len(revoked) == 1
    assert revoked[0]["tenant_id"] == "t-004"


def test_withdraw_removes_egress_allowlist_entry() -> None:
    _server, base_url, responses = _start_server()
    responses["/v1/admin/enroll"] = (
        200,
        {"audit_event_hash": "sha256:w2", "dashboard_url": base_url},
    )
    responses["/v1/admin/withdraw"] = (200, {"status": "ok"})

    runner.invoke(
        app,
        [
            "enroll",
            "--tenant",
            "t-005",
            "--token",
            "tok-w2",
            "--dashboard-url",
            base_url,
        ],
    )
    assert "dashboard:t-005" in _load_egress_allowlist()

    runner.invoke(app, ["withdraw", "--tenant", "t-005", "--dashboard-url", base_url])

    assert "dashboard:t-005" not in _load_egress_allowlist()


def test_withdraw_after_enroll_makes_re_enroll_possible() -> None:
    """After withdraw, a second enroll writes a new consent_granted event."""
    _server, base_url, responses = _start_server()
    responses["/v1/admin/enroll"] = (
        200,
        {"audit_event_hash": "sha256:reroll", "dashboard_url": base_url},
    )
    responses["/v1/admin/withdraw"] = (200, {"status": "ok"})

    runner.invoke(
        app,
        [
            "enroll",
            "--tenant",
            "t-006",
            "--token",
            "tok-r1",
            "--dashboard-url",
            base_url,
        ],
    )
    runner.invoke(app, ["withdraw", "--tenant", "t-006", "--dashboard-url", base_url])
    result = runner.invoke(
        app,
        [
            "enroll",
            "--tenant",
            "t-006",
            "--token",
            "tok-r2",
            "--dashboard-url",
            base_url,
        ],
    )

    assert result.exit_code == 0
    events = _ledger_events()
    granted = [e for e in events if e.get("event_type") == "consent_granted"]
    assert len(granted) == 2  # original + re-enroll
