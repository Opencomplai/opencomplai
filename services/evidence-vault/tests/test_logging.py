from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from opencomplai_evidence_vault.main import create_app


@pytest.mark.asyncio
@patch("opencomplai_evidence_vault.main.logger.exception")
async def test_get_status_logs_database_error(mock_exception):
    app = create_app()
    mock_session = AsyncMock()
    app.state.sessionmaker = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    mock_session.execute.side_effect = Exception("DB connection refused")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    mock_exception.assert_called_once_with("Database connectivity check failed")
