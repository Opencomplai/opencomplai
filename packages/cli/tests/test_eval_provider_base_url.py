"""`opencomplai eval --provider-base-url` (SU-131)."""

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    monkeypatch.setenv("OPENCOMPLAI_PROVIDER_API_KEY", "test-key")


def _files(tmp_path: Path) -> tuple[Path, Path]:
    manifest = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "sys-1",
            "--intended-purpose",
            "support bot",
            "--output",
            str(manifest),
        ],
    )
    assert result.exit_code == 0, result.output
    sample = tmp_path / "set.json"
    sample.write_text(
        json.dumps({"eval_set_id": "s1", "system_id": "sys-1", "prompts": ["hello"]})
    )
    return manifest, sample


def _args(manifest: Path, sample: Path, *extra: str) -> list[str]:
    return ["eval", "--manifest", str(manifest), "--sample-set", str(sample), *extra]


def test_eval_calls_fake_server_on_loopback(tmp_path):
    seen: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["path"] = self.path
            seen["auth"] = self.headers.get("Authorization")
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            body = json.dumps(
                {"choices": [{"message": {"content": "fake-completion"}}]}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        manifest, sample = _files(tmp_path)
        port = server.server_address[1]
        result = runner.invoke(
            app,
            _args(
                manifest,
                sample,
                "--provider",
                "openai_compatible",
                "--model",
                "m",
                "--provider-base-url",
                f"http://127.0.0.1:{port}/v1",
                "--output",
                "json",
            ),
        )
    finally:
        server.shutdown()
        server.server_close()
    assert "fake-completion" in result.output, result.output
    assert seen["path"] == "/v1/chat/completions"
    assert seen["auth"] == "Bearer test-key"


def test_eval_rejects_plain_http_remote_url(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("request sent")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    manifest, sample = _files(tmp_path)
    result = runner.invoke(
        app,
        _args(
            manifest,
            sample,
            "--provider",
            "openai_compatible",
            "--model",
            "m",
            "--provider-base-url",
            "http://example.com/v1",
        ),
    )
    assert result.exit_code == 2, result.output


def test_eval_base_url_requires_provider(tmp_path):
    manifest, sample = _files(tmp_path)
    result = runner.invoke(
        app, _args(manifest, sample, "--provider-base-url", "https://example.com/v1")
    )
    assert result.exit_code == 2, result.output
