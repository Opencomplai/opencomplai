"""
Tests for verify_ledger.py — stdlib-only ledger verifier.

Uses unittest.mock to avoid real HTTP calls.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

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
        assert not isinstance(ctx.value, verify_ledger.RateLimitedError)

    def test_http_429_is_reported_as_rate_limited_with_a_way_forward(self):
        exc = urllib.error.HTTPError(
            url="http://test",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None,  # type: ignore[arg-type]
        )
        exc.read = lambda: b'{"message":"Rate limit exceeded"}'
        with patch("urllib.request.urlopen", side_effect=exc):
            with pytest.raises(verify_ledger.RateLimitedError) as ctx:
                verify_ledger._get_json("http://test/slow")
        message = str(ctx.value)
        assert "HTTP 429" in message
        assert "Wait" in message
        assert "OPENCOMPLAI_RATE_LIMIT_MAX" in message

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
        """Write a dossier in the current schema: the anchor lives under
        record_keeping (Art. 12 record-keeping split out of Annex IV pt.4)."""
        dossier = {
            "dossier_id": "test-dossier-id",
            "system_id": "test",
            "record_keeping": {
                "ledger_root_hash": anchor,
                "logging_enabled": True,
            },
        }
        path = tmp_path / "dossier.json"
        path.write_text(json.dumps(dossier))
        return path

    def _write_legacy_dossier(self, tmp_path: Path, anchor: str | None) -> Path:
        """Write a dossier in the pre-split schema: the anchor lives under
        section4.ledger_root_hash, with no record_keeping section at all."""
        dossier = {
            "dossier_id": "legacy-dossier-id",
            "system_id": "test",
            "section4": {
                "ledger_root_hash": anchor,
                "logging_enabled": True,
            },
        }
        path = tmp_path / "legacy_dossier.json"
        path.write_text(json.dumps(dossier))
        return path

    _GENESIS = "sha256:" + "0" * 64

    def _mock_tips(self, tips: list[str]):
        """Return a mock urlopen response serving one final page of tips (the
        shape a current vault answers a limit/after_seq request with)."""
        body = json.dumps(
            {
                "genesis": self._GENESIS,
                "tips": tips,
                "count": len(tips),
                "next_after_seq": None,
            }
        ).encode()
        return _make_response(body)

    def _fake_vault(self, pages: dict[int, dict]):
        """Return (urlopen side_effect, requested) for a vault that serves the
        page registered under each after_seq. `requested` collects the parsed
        query of every request, in order."""
        requested: list[dict[str, list[str]]] = []

        def fake_urlopen(req, timeout=None):
            query = parse_qs(urlsplit(req.full_url).query)
            requested.append(query)
            if len(requested) > 50:
                raise AssertionError("endless paging loop: more than 50 requests")
            page = pages[int(query["after_seq"][0])]
            return _make_response(json.dumps(page).encode())

        return fake_urlopen, requested

    def _write_dossier_for(self, anchor: str) -> Path:
        import tempfile

        tmp = self.enterContext(tempfile.TemporaryDirectory())
        path = Path(tmp) / "dossier.json"
        path.write_text(json.dumps({"record_keeping": {"ledger_root_hash": anchor}}))
        return path

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
                    "record_keeping": {"ledger_root_hash": self._KNOWN_TIP},
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

    def test_legacy_section4_location_still_supported_as_fallback(self):
        """Dossiers generated before the Art. 12 record-keeping split (no
        record_keeping section at all) must still be verifiable via the
        legacy section4.ledger_root_hash location."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dossier_path = self._write_legacy_dossier(tmp_path, self._KNOWN_TIP)
            tips = [self._KNOWN_TIP]
            mock_resp = self._mock_tips(tips)
            with patch("urllib.request.urlopen", return_value=mock_resp):
                ok, reason = verify_ledger.check_dossier_anchor(
                    "http://vault:8002", str(dossier_path)
                )
            assert ok
            assert reason == ""

    def test_record_keeping_location_takes_precedence_over_legacy_section4(self):
        """When both locations are present (e.g. a dossier written by an old
        tool version and re-read by this one), record_keeping is current and
        must win over a stale section4 value."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dossier = {
                "dossier_id": "mixed-test",
                "record_keeping": {"ledger_root_hash": self._KNOWN_TIP},
                "section4": {"ledger_root_hash": self._OTHER_TIP},
            }
            path = tmp_path / "mixed_dossier.json"
            path.write_text(json.dumps(dossier))

            # Only the record_keeping anchor is in history — if the legacy
            # section4 value were read instead, this would fail.
            tips = [self._KNOWN_TIP]
            mock_resp = self._mock_tips(tips)
            with patch("urllib.request.urlopen", return_value=mock_resp):
                ok, reason = verify_ledger.check_dossier_anchor(
                    "http://vault:8002", str(path)
                )
            assert ok
            assert reason == ""

    def test_first_request_pages_with_limit_and_cursor(self):
        """The tool asks for a bounded page, never the whole chain at once."""
        path = self._write_dossier_for(self._KNOWN_TIP)
        fake, requested = self._fake_vault(
            {
                0: {
                    "genesis": self._GENESIS,
                    "tips": [self._KNOWN_TIP],
                    "count": 1,
                    "next_after_seq": None,
                }
            }
        )
        with patch("urllib.request.urlopen", side_effect=fake):
            ok, _ = verify_ledger.check_dossier_anchor("http://vault:8002", str(path))
        assert ok
        # 5000 is the vault's maximum page size: the fewest requests, so the
        # gateway's per-minute limit is hit on the largest possible ledger.
        assert requested == [{"limit": ["5000"], "after_seq": ["0"]}]

    def test_anchor_found_on_first_page_stops_paging(self):
        path = self._write_dossier_for(self._KNOWN_TIP)
        # A second request would KeyError on a page nobody registered.
        fake, requested = self._fake_vault(
            {
                0: {
                    "genesis": self._GENESIS,
                    "tips": [self._OTHER_TIP, self._KNOWN_TIP],
                    "count": 2,
                    "next_after_seq": 2,
                },
            }
        )
        with patch("urllib.request.urlopen", side_effect=fake):
            ok, reason = verify_ledger.check_dossier_anchor(
                "http://vault:8002", str(path)
            )
        assert ok
        assert reason == ""
        assert len(requested) == 1

    def test_anchor_found_on_a_later_page_follows_the_cursor(self):
        path = self._write_dossier_for(self._KNOWN_TIP)
        # The anchor is on the page after_seq=3 serves, so seq 4 is never asked for.
        fake, requested = self._fake_vault(
            {
                0: {
                    "genesis": self._GENESIS,
                    "tips": [self._OTHER_TIP, self._OTHER_TIP],
                    "count": 2,
                    "next_after_seq": 2,
                },
                2: {"tips": [self._OTHER_TIP], "count": 1, "next_after_seq": 3},
                3: {"tips": [self._KNOWN_TIP], "count": 1, "next_after_seq": 4},
            }
        )
        with patch("urllib.request.urlopen", side_effect=fake):
            ok, reason = verify_ledger.check_dossier_anchor(
                "http://vault:8002", str(path)
            )
        assert ok
        assert reason == ""
        assert [q["after_seq"] for q in requested] == [["0"], ["2"], ["3"]]

    def test_anchor_not_found_after_paging_reports_every_tip_examined(self):
        path = self._write_dossier_for(self._KNOWN_TIP)
        fake, requested = self._fake_vault(
            {
                0: {
                    "genesis": self._GENESIS,
                    "tips": [self._OTHER_TIP, self._OTHER_TIP],
                    "count": 2,
                    "next_after_seq": 2,
                },
                2: {"tips": [self._OTHER_TIP], "count": 1, "next_after_seq": None},
            }
        )
        with patch("urllib.request.urlopen", side_effect=fake):
            ok, reason = verify_ledger.check_dossier_anchor(
                "http://vault:8002", str(path)
            )
        assert not ok
        assert "does not appear in 4 historical" in reason  # genesis + 3 tips
        assert len(requested) == 2

    def test_anchor_equal_to_genesis_is_found_from_the_genesis_field(self):
        """An empty chain's anchor is the genesis hash, which a paged response
        reports in "genesis", not in "tips"."""
        path = self._write_dossier_for(self._GENESIS)
        with patch("urllib.request.urlopen", return_value=self._mock_tips([])):
            ok, reason = verify_ledger.check_dossier_anchor(
                "http://vault:8002", str(path)
            )
        assert ok
        assert reason == ""

    def test_genesis_is_only_matched_on_the_first_page(self):
        """The genesis hash is not a tip of any later page; a response that
        repeats it there must not be mistaken for the dossier's anchor."""
        path = self._write_dossier_for(self._KNOWN_TIP)
        fake, _ = self._fake_vault(
            {
                0: {
                    "genesis": self._GENESIS,
                    "tips": [self._OTHER_TIP],
                    "count": 1,
                    "next_after_seq": 1,
                },
                1: {
                    "genesis": self._KNOWN_TIP,
                    "tips": [self._OTHER_TIP],
                    "count": 1,
                    "next_after_seq": None,
                },
            }
        )
        with patch("urllib.request.urlopen", side_effect=fake):
            ok, _ = verify_ledger.check_dossier_anchor("http://vault:8002", str(path))
        assert not ok

    def test_older_vault_that_ignores_paging_is_treated_as_complete(self):
        """A vault from before paging answers with the whole chain and no
        next_after_seq: one request, genesis at tips[0], no looping."""
        body = {"tips": [self._GENESIS, self._KNOWN_TIP], "count": 2}
        requested: list[str] = []

        def fake_urlopen(req, timeout=None):
            requested.append(req.full_url)
            return _make_response(json.dumps(body).encode())

        found = self._write_dossier_for(self._KNOWN_TIP)
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ok, reason = verify_ledger.check_dossier_anchor(
                "http://vault:8002", str(found)
            )
        assert ok
        assert reason == ""
        assert len(requested) == 1

        # The same shape reports a miss, with the right count.
        missing = self._write_dossier_for(self._OTHER_TIP)
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ok, reason = verify_ledger.check_dossier_anchor(
                "http://vault:8002", str(missing)
            )
        assert not ok
        assert "does not appear in 2 historical" in reason

    def test_non_advancing_cursor_is_an_error_not_an_endless_loop(self):
        path = self._write_dossier_for(self._KNOWN_TIP)
        stuck = {
            "genesis": self._GENESIS,
            "tips": [self._OTHER_TIP],
            "count": 1,
            "next_after_seq": 0,
        }
        fake, requested = self._fake_vault({0: stuck})
        with patch("urllib.request.urlopen", side_effect=fake):
            with pytest.raises(verify_ledger.VaultProtocolError) as ctx:
                verify_ledger.check_dossier_anchor("http://vault:8002", str(path))
        assert "malformed cursor from the vault" in str(ctx.value)
        assert len(requested) == 1

    def test_non_integer_cursor_is_an_error_not_a_bad_request(self):
        """A cursor that is not an int must be refused before it is sent back
        as after_seq."""
        path = self._write_dossier_for(self._KNOWN_TIP)
        for bad in ("5", 2.5, [2], {"seq": 2}):
            garbled = {
                "genesis": self._GENESIS,
                "tips": [self._OTHER_TIP],
                "count": 1,
                "next_after_seq": bad,
            }
            fake, requested = self._fake_vault({0: garbled})
            with patch("urllib.request.urlopen", side_effect=fake):
                with pytest.raises(verify_ledger.VaultProtocolError) as ctx:
                    verify_ledger.check_dossier_anchor("http://vault:8002", str(path))
            assert "malformed cursor from the vault" in str(ctx.value)
            assert len(requested) == 1  # the bad cursor was never followed

    def test_missing_dossier_file_raises(self):
        """A missing dossier file raises RuntimeError (connectivity issue → exit 2)."""
        with pytest.raises(RuntimeError) as ctx:
            verify_ledger.check_dossier_anchor(
                "http://vault:8002", "/nonexistent/path/dossier.json"
            )
        assert "Cannot read dossier file" in str(ctx.value)


class TestMainExitCodes(unittest.TestCase):
    """main() must say what went wrong, not call everything a connectivity
    error, and exit 2 for all of them."""

    _ANCHOR = "sha256:" + "a" * 64

    def _run_main(self, tips_failure) -> tuple[int, str]:
        """Run main() against a vault whose health and verify-chain answer
        normally and whose tips request fails with `tips_failure` (an
        exception to raise, or a dict to serve as the JSON body)."""
        import tempfile

        def fake_urlopen(req, timeout=None):
            if req.full_url.endswith("/health"):
                return _make_response(b'{"status": "ok"}')
            if req.full_url.endswith("/v1/evidence/verify-chain"):
                return _make_response(b'{"valid": true}')
            if isinstance(tips_failure, Exception):
                raise tips_failure
            return _make_response(json.dumps(tips_failure).encode())

        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp) / "dossier.json"
            dossier.write_text(
                json.dumps({"record_keeping": {"ledger_root_hash": self._ANCHOR}})
            )
            argv = ["verify_ledger.py", "--gateway-url", "http://gw", "--dossier"]
            stderr = io.StringIO()
            with (
                patch.object(sys, "argv", [*argv, str(dossier)]),
                patch("urllib.request.urlopen", side_effect=fake_urlopen),
                contextlib.redirect_stderr(stderr),
                contextlib.redirect_stdout(io.StringIO()),
                pytest.raises(SystemExit) as ctx,
            ):
                verify_ledger.main()
        return ctx.value.code, stderr.getvalue()

    def _http_error(self, code: int) -> urllib.error.HTTPError:
        exc = urllib.error.HTTPError(
            url="http://gw",
            code=code,
            msg="err",
            hdrs={},
            fp=None,  # type: ignore[arg-type]
        )
        exc.read = lambda: b"{}"
        return exc

    def test_rate_limit_is_reported_as_such(self):
        code, err = self._run_main(self._http_error(429))
        assert code == 2
        assert "Check 2 rate limited" in err
        assert "connectivity error" not in err
        assert "OPENCOMPLAI_RATE_LIMIT_MAX" in err

    def test_malformed_cursor_is_reported_as_a_protocol_error(self):
        code, err = self._run_main(
            {"genesis": "g", "tips": ["t"], "count": 1, "next_after_seq": "7"}
        )
        assert code == 2
        assert "Check 2 vault protocol error" in err
        assert "malformed cursor from the vault" in err
        assert "connectivity error" not in err

    def test_other_http_errors_stay_connectivity_errors(self):
        code, err = self._run_main(self._http_error(503))
        assert code == 2
        assert "Check 2 connectivity error" in err


if __name__ == "__main__":
    unittest.main()
