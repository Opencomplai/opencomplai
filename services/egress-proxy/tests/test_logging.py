import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opencomplai_egress_proxy.main import gateway_health, sync_metadata


@pytest.mark.asyncio
@patch("opencomplai_egress_proxy.main.logger")
async def test_gateway_health_logs_failure(mock_logger):
    with patch("httpx.AsyncClient.get", side_effect=Exception("connection refused")):
        response = await gateway_health()

    assert response.status_code == 503
    mock_logger.warning.assert_called_once_with(
        "Gateway health check failed: %s", "Exception"
    )


@pytest.mark.asyncio
@patch("opencomplai_egress_proxy.main.logger")
async def test_sync_metadata_invalid_json_logs_error_class_only(mock_logger):
    request = MagicMock()
    request.json = AsyncMock(side_effect=json.JSONDecodeError("secret", "doc", 0))

    response = await sync_metadata(request)

    assert response.status_code == 422
    mock_logger.warning.assert_called_once_with(
        "Invalid JSON in sync_metadata payload: %s", "JSONDecodeError"
    )
