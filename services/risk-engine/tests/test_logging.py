from unittest.mock import patch

import pytest
from fastapi import HTTPException
from opencomplai_risk_engine.main import (
    EvalRunRequest,
    ManifestValidateRequest,
    _lookup_accepted_override,
    _vault_request,
    run_evals_endpoint,
    validate_manifest,
)


@patch("opencomplai_risk_engine.main.logger.exception")
def test_vault_request_logs_swallowed_exception(mock_exception):
    with patch(
        "opencomplai_risk_engine.main.urlreq.urlopen",
        side_effect=Exception("network error"),
    ):
        result = _vault_request("GET", "/test")

    assert result is None
    mock_exception.assert_called_once_with("Vault request failed")


@pytest.mark.asyncio
@patch("opencomplai_risk_engine.main.logger.warning")
async def test_validate_manifest_logs_error_class_only(mock_warning):
    request = ManifestValidateRequest(
        system_id="test",
        intended_purpose="test",
        compliance_targets=["secret-framework"],
    )

    with pytest.raises(HTTPException) as exc_info:
        await validate_manifest(request)

    assert exc_info.value.status_code == 422
    mock_warning.assert_called_once_with("Manifest validation failed: %s", "ValueError")


@pytest.mark.asyncio
@patch("opencomplai_risk_engine.main.logger.warning")
async def test_run_evals_logs_error_class_only(mock_warning):
    request = EvalRunRequest(system_id="test", sample_set={"secret": "value"})

    with pytest.raises(HTTPException) as exc_info:
        await run_evals_endpoint(request)

    assert exc_info.value.status_code == 422
    mock_warning.assert_called_once_with(
        "Eval sample set validation failed: %s", "ValidationError"
    )


def test_override_lookup_percent_encodes_the_client_key():
    with patch("opencomplai_risk_engine.main._vault_request", return_value=None) as vr:
        _lookup_accepted_override("my key/../x")

    vr.assert_called_once_with("GET", "/v1/hitl/overrides/my%20key%2F..%2Fx")
