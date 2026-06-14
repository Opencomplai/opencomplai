"""No source, secrets, or PII in evidence payloads."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_core.scan_engine import run_scan

FAKE_SECRET = "sk-super-secret-key-12345"
FAKE_EMAIL = "user@example.com"


def test_secret_and_email_never_in_report(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        f'API_KEY = "{FAKE_SECRET}"\nEMAIL = "{FAKE_EMAIL}"\nimport openai\n',
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(f"OPENAI_API_KEY={FAKE_SECRET}\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("openai\n", encoding="utf-8")
    report = run_scan("s", "HEAD", tmp_path, "chatbot")
    blob = json.dumps(report.model_dump())
    assert FAKE_SECRET not in blob
    assert FAKE_EMAIL not in blob
