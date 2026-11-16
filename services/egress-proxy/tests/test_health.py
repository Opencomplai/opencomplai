"""
Health endpoint tests for egress-proxy.

``/health`` here is not a self-liveness probe: it proxies a real request to
``GATEWAY_API_URL`` and mirrors the gateway's answer. The previous version of
this file called it with no mocking, so it made an actual network request and
returned 503 whenever a gateway was not running — a permanent failure in the
documented baseline of known failures that said nothing about the code under
test.

The outbound call is now mocked, the way ``test_dlp.py`` already avoids real
egress, and both branches are covered. ``/egress-health`` — the endpoint that
reports this service's own liveness, and the one gateway-api probes for exactly
that reason (OPS-HEALTH) — is covered directly.
"""

import httpx
import pytest
from httpx import ASGITransport, AsyncClient, Response
from opencomplai_egress_proxy.main import GATEWAY_API_URL, app

_REAL_GET = httpx.AsyncClient.get


def _intercept_gateway(monkeypatch, handler):
    """
    Replace only the *outbound* gateway call, leaving the test's own ASGI
    client untouched.

    Patching ``httpx.AsyncClient.get`` wholesale does not work here: the test
    client is itself an ``httpx.AsyncClient``, so a blanket patch intercepts
    ``client.get("/health")`` before the app ever runs — the test then passes
    or fails on the mock alone and never exercises a line of egress-proxy.
    Dispatching on the URL keeps the patch to the one call being faked.
    """

    async def _dispatch(self, url, *args, **kwargs):
        if str(url).startswith(GATEWAY_API_URL):
            return await handler(url)
        return await _REAL_GET(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "get", _dispatch)


@pytest.mark.asyncio
async def test_egress_health_reports_own_liveness_without_any_outbound_call():
    """
    The real self-liveness endpoint: static, no dependencies. This is what
    gateway-api's /v1/status probes, precisely so a gateway-side fault cannot
    make egress-proxy look unhealthy.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/egress-health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "egress-proxy"


@pytest.mark.asyncio
async def test_health_mirrors_the_gateway_when_it_is_reachable(monkeypatch):
    async def _gateway_is_up(url):
        return Response(
            200,
            json={"status": "ok", "service": "gateway-api"},
            headers={"content-type": "application/json"},
        )

    _intercept_gateway(monkeypatch, _gateway_is_up)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_reports_degraded_when_the_gateway_is_unreachable(monkeypatch):
    async def _gateway_is_down(url):
        raise httpx.ConnectError("connection refused")

    _intercept_gateway(monkeypatch, _gateway_is_down)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    # 503 is the correct contract for this endpoint — it means "I cannot reach
    # the gateway". The defect was never the status code, only that a unit test
    # made the real call to decide it.
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
