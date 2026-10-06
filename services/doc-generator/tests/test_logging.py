from unittest.mock import patch

import pytest
from fastapi import HTTPException
from opencomplai_doc_generator.main import GenerateDocsRequest, generate_docs


@pytest.mark.asyncio
@patch("opencomplai_doc_generator.main.logger.exception")
async def test_generate_docs_logs_unexpected_errors(mock_exception):
    req_body = GenerateDocsRequest(
        system_id="test",
        commit_ref="HEAD",
        manifest={"system_id": "test"},
        assessment_results={},
    )

    with patch(
        "opencomplai_doc_generator.main.SystemManifest", side_effect=Exception("boom!")
    ):
        with pytest.raises(HTTPException) as exc_info:
            await generate_docs(req_body, tenant_id="test")

    assert exc_info.value.status_code == 500
    mock_exception.assert_called_once_with("Dossier generation failed unexpectedly")
