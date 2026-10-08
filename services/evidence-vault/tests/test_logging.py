import io
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from opencomplai_core.telemetry import JsonFormatter
from opencomplai_evidence_vault.main import _run_migrations, create_app


def _client(mock_session):
    app = create_app()
    app.state.sessionmaker = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
@patch("opencomplai_evidence_vault.main.logger.warning")
async def test_get_status_logs_database_error(mock_warning):
    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("DB connection refused")

    async with _client(mock_session) as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    mock_warning.assert_called_once_with(
        "Database connectivity check failed: %s", "Exception"
    )


@pytest.mark.asyncio
@patch("opencomplai_evidence_vault.main.logger.warning")
async def test_invalid_base64_logs_error_class_only(mock_warning, service_auth_headers):
    async with _client(AsyncMock()) as client:
        response = await client.post(
            "/v1/evidence/objects",
            json={"content_base64": "not*base64"},
            headers=service_auth_headers,
        )

    assert response.status_code == 422
    mock_warning.assert_called_once_with("Invalid base64 content received: %s", "Error")


def test_in_process_migration_keeps_service_logging(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'vault.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    json_handler = logging.StreamHandler(io.StringIO())
    json_handler.setFormatter(JsonFormatter("evidence-vault"))
    root.addHandler(json_handler)
    try:
        _run_migrations(url)

        assert json_handler in root.handlers
        assert root.level == level
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)
