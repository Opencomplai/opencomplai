from unittest.mock import patch

import pytest
from opencomplai_egress_proxy.main import gateway_health


@pytest.mark.asyncio
@patch("opencomplai_egress_proxy.main.logger")
async def test_gateway_health_logs_failure(mock_logger):
    with patch("httpx.AsyncClient.get", side_effect=Exception("connection refused")):
        response = await gateway_health()

    assert response.status_code == 503
    mock_logger.warning.assert_called_once_with(
        "Gateway health check failed", exc_info=True
    )
