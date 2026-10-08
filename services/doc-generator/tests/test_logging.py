from unittest.mock import patch

import pytest
from fastapi import HTTPException
from opencomplai_doc_generator.main import GenerateDocsRequest, generate_docs
from pydantic import BaseModel, ValidationError


@pytest.mark.asyncio
@patch("opencomplai_doc_generator.main.logger.exception")
async def test_generate_docs_logs_unexpected_errors(mock_exception):
    req_body = GenerateDocsRequest(system_id="test", commit_ref="HEAD")

    with patch(
        "opencomplai_doc_generator.main.SystemManifest", side_effect=Exception("boom!")
    ):
        with pytest.raises(HTTPException) as exc_info:
            await generate_docs(req_body, tenant_id="test")

    assert exc_info.value.status_code == 500
    mock_exception.assert_called_once_with("Dossier generation failed unexpectedly")


def _validation_error() -> ValidationError:
    class _M(BaseModel):
        x: int

    try:
        _M(x="SECRET-TOKEN-abc123")
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a ValidationError")


@pytest.mark.asyncio
async def test_generate_docs_logs_validation_errors_without_input():
    req_body = GenerateDocsRequest(system_id="test", commit_ref="HEAD")

    with (
        patch(
            "opencomplai_doc_generator.main.SystemManifest",
            side_effect=_validation_error(),
        ),
        patch("opencomplai_doc_generator.main.logger") as mock_logger,
    ):
        with pytest.raises(HTTPException):
            await generate_docs(req_body, tenant_id="test")

    mock_logger.warning.assert_called_once_with(
        "Dossier request validation failed: %s", "ValidationError"
    )
    mock_logger.exception.assert_not_called()
