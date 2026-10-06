import logging
import sys
from unittest.mock import patch

import pytest
from opencomplai_egress_proxy.main import gateway_health


@pytest.mark.asyncio
async def test_gateway_health_logs_failure(capsys):
    logger = logging.getLogger("opencomplai_egress_proxy.main")
    logger.addHandler(logging.StreamHandler(sys.stdout))

    with patch("httpx.AsyncClient.get", side_effect=Exception("connection refused")):
        response = await gateway_health()

    assert response.status_code == 503
    captured = capsys.readouterr()
    assert (
        "Gateway health check failed" in captured.err
        or "Gateway health check failed" in captured.out
    )
    assert "connection refused" in captured.err or "connection refused" in captured.out
