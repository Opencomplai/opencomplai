"""Tests for OIDC client-credentials token acquisition."""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from opencomplai_cli.oidc_client import OidcTokenError, acquire_token


def _fake_response(body: dict) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(body).encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def test_acquire_token_success() -> None:
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _fake_response(
            {"access_token": "jwt-value", "expires_in": 3600}
        )
        token, expires_in = acquire_token(
            "https://idp.example.test/oauth/token", "client-1", "secret-1"
        )
    assert token == "jwt-value"
    assert expires_in == 3600

    # Verify the request shape: form-encoded body, client_credentials grant.
    sent_request = mock_urlopen.call_args[0][0]
    assert sent_request.full_url == "https://idp.example.test/oauth/token"
    assert (
        sent_request.get_header("Content-type") == "application/x-www-form-urlencoded"
    )
    body = sent_request.data.decode("ascii")
    assert "grant_type=client_credentials" in body
    assert "client_id=client-1" in body
    assert "client_secret=secret-1" in body


def test_acquire_token_defaults_expires_in_when_absent() -> None:
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _fake_response({"access_token": "jwt-value"})
        _, expires_in = acquire_token("https://idp.example.test/oauth/token", "c", "s")
    assert expires_in == 3600


def test_acquire_token_includes_scope_when_given() -> None:
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _fake_response({"access_token": "jwt-value"})
        acquire_token(
            "https://idp.example.test/oauth/token", "c", "s", scope="ingest:write"
        )
    sent_request = mock_urlopen.call_args[0][0]
    assert "scope=ingest%3Awrite" in sent_request.data.decode("ascii")


def test_acquire_token_raises_on_http_error() -> None:
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://idp.example.test/oauth/token",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b""),
        )
        with pytest.raises(OidcTokenError, match="401"):
            acquire_token("https://idp.example.test/oauth/token", "bad", "creds")


def test_acquire_token_raises_on_unreachable_endpoint() -> None:
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        with pytest.raises(OidcTokenError, match="unreachable"):
            acquire_token("https://idp.example.test/oauth/token", "c", "s")


def test_acquire_token_raises_on_missing_access_token() -> None:
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _fake_response({"token_type": "Bearer"})
        with pytest.raises(OidcTokenError, match="access_token"):
            acquire_token("https://idp.example.test/oauth/token", "c", "s")


def test_acquire_token_raises_on_non_json_response() -> None:
    with patch("urllib.request.urlopen") as mock_urlopen:
        resp = MagicMock()
        resp.read.return_value = b"not json"
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        mock_urlopen.return_value = resp
        with pytest.raises(OidcTokenError, match="non-JSON"):
            acquire_token("https://idp.example.test/oauth/token", "c", "s")
