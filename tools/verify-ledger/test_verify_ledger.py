"""
Tests for verify_ledger.py — stdlib-only ledger verifier.

Uses unittest.mock to avoid real HTTP calls.
"""

from __future__ import annotations

import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the tool directory to sys.path so we can import it directly
sys.path.insert(0, str(Path(__file__).parent))

import pytest
import verify_ledger


def _make_response(body: bytes, status: int = 200):
    """Build a mock urllib response context manager."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.status = status
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestGetJson(unittest.TestCase):
    def test_returns_parsed_dict(self):
        mock_resp = _make_response(b'{"valid": true}')
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = verify_ledger._get_json("http://test/health")
        assert result == {"valid": True}

    def test_raises_on_http_error(self):
        exc = urllib.error.HTTPError(
            url="http://test",
            code=500,
            msg="Server Error",
            hdrs={},
            fp=None,  # type: ignore[arg-type]
        )
        exc.read = lambda: b"Internal Server Error"
        with patch("urllib.request.urlopen", side_effect=exc):
            with pytest.raises(RuntimeError) as ctx:
                verify_ledger._get_json("http://test/fail")
        assert "HTTP 500" in str(ctx.value)

    def test_raises_on_url_error(self):
        exc = urllib.error.URLError(reason="Connection refused")
        with patch("urllib.request.urlopen", side_effect=exc):
            with pytest.raises(RuntimeError) as ctx:
                verify_ledger._get_json("http://localhost:9/nope")
        assert "Cannot connect" in str(ctx.value)


class TestCheckChainIntegrity(unittest.TestCase):
    def test_returns_true_when_valid(self):
        mock_resp = _make_response(b'{"valid": true}')
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = verify_ledger.check_chain_integrity("http://gateway:3000")
        assert result

    def test_returns_false_when_invalid(self):
        mock_resp = _make_response(b'{"valid": false}')
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = verify_ledger.check_chain_integrity("http://gateway:3000")
        assert not result

    def test_uses_provided_base_url(self):
        captured = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.full_url)
            return _make_response(b'{"valid": true}')

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            verify_ledger.check_chain_integrity("http://vault:8002")

        assert any("vault:8002" in url for url in captured)


class TestCheckHealth(unittest.TestCase):
    def test_returns_true_when_ok(self):
        mock_resp = _make_response(b'{"status": "ok"}')
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert verify_ledger.check_health("http://gateway:3000")

    def test_returns_false_on_error(self):
        exc = urllib.error.URLError(reason="refused")
        with patch("urllib.request.urlopen", side_effect=exc):
            assert not verify_ledger.check_health("http://gateway:3000")


# ---------------------------------------------------------------------------
# Tests for Check 2 — dossier anchor verification
# ---------------------------------------------------------------------------


class TestCheckDossierAnchor(unittest.TestCase):
    """
    Unit tests for check_dossier_anchor() using a synthetic dossier JSON and
    a fixture ledger history (mocked HTTP responses).
    """

    _KNOWN_TIP = "sha256:" + "a" * 64
    _OTHER_TIP = "sha256:" + "b" * 64

    def _write_dossier(self, tmp_path: Path, anchor: str | None) -> Path:
        dossier = {
            "dossier_id": "test-dossier-id",
            "system_id": "test",
            "section4": {
                "ledger_root_hash": anchor,
                "logging_enabled": True,
            },
        }
        path = tmp_path / "dossier.json"
        path.write_text(json.dumps(dossier))
        return path

    def _mock_tips(self, tips: list[str]):
        """Return a mock urlopen that serves the tips JSON."""
        body = json.dumps({"tips": tips, "count": len(tips)}).encode()
        return _make_response(body)

    def test_anchor_found_in_history(self):
        """Pass: the dossier's anchor appears in the chain tips."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dossier_path = self._write_dossier(tmp_path, self._KNOWN_TIP)
            tips = [self._OTHER_TIP, self._KNOWN_TIP, self._OTHER_TIP]
            mock_resp = self._mock_tips(tips)
            with patch("urllib.request.urlopen", return_value=mock_resp):
                ok, reason = verify_ledger.check_dossier_anchor(
                    "http://vault:8002", str(dossier_path)
                )
            assert ok
            assert reason == ""

    def test_anchor_not_in_history_returns_false(self):
        """Fail: the dossier's anchor is not in the chain — ledger may be truncated."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dossier_path = self._write_dossier(tmp_path, self._KNOWN_TIP)
            tips = [self._OTHER_TIP]  # KNOWN_TIP deliberately absent
            mock_resp = self._mock_tips(tips)
            with patch("urllib.request.urlopen", return_value=mock_resp):
                ok, reason = verify_ledger.check_dossier_anchor(
                    "http://vault:8002", str(dossier_path)
                )
            assert not ok
            assert "does not appear" in reason

    def test_null_anchor_returns_false_with_null_message(self):
        """Fail exit 4: dossier has no anchor — anchoring failed at generation time."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dossier_path = self._write_dossier(tmp_path, None)
            # No HTTP call needed since anchor check short-circuits on null
            ok, reason = verify_ledger.check_dossier_anchor(
                "http://vault:8002", str(dossier_path)
            )
            assert not ok
            assert "null" in reason

    def test_envelope_dossier_format_supported(self):
        """Dossier JSON wrapped in an outer {"dossier": {...}} envelope is handled."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Write envelope format
            dossier_data = {
                "dossier": {
                    "dossier_id": "env-test",
                    "section4": {"ledger_root_hash": self._KNOWN_TIP},
                }
            }
            path = tmp_path / "envelope.json"
            path.write_text(json.dumps(dossier_data))

            tips = [self._KNOWN_TIP]
            mock_resp = self._mock_tips(tips)
            with patch("urllib.request.urlopen", return_value=mock_resp):
                ok, reason = verify_ledger.check_dossier_anchor(
                    "http://vault:8002", str(path)
                )
            assert ok
            assert reason == ""

    def test_missing_dossier_file_raises(self):
        """A missing dossier file raises RuntimeError (connectivity issue → exit 2)."""
        with pytest.raises(RuntimeError) as ctx:
            verify_ledger.check_dossier_anchor(
                "http://vault:8002", "/nonexistent/path/dossier.json"
            )
        assert "Cannot read dossier file" in str(ctx.value)


if __name__ == "__main__":
    unittest.main()
