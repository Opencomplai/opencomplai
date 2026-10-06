from unittest.mock import patch

from opencomplai_risk_engine.main import _vault_request


@patch("opencomplai_risk_engine.main.logger.exception")
def test_vault_request_logs_swallowed_exception(mock_exception):
    with patch(
        "opencomplai_risk_engine.main.urlreq.urlopen",
        side_effect=Exception("network error"),
    ):
        result = _vault_request("GET", "/test")

    assert result is None
    mock_exception.assert_called_once_with("Vault request failed")
