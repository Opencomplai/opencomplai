"""Tests for the opt-in model-provider client (opencomplai eval --provider)."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import patch

import pytest
from opencomplai_core.model_providers import (
    OpenAICompatibleProvider,
    ProviderCompletion,
    get_provider_client,
)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_get_provider_client_resolves_openai():
    client = get_provider_client("openai")
    assert isinstance(client, OpenAICompatibleProvider)
    assert client.provider_id == "openai_compatible"


def test_get_provider_client_raises_on_unknown_provider():
    with pytest.raises(ValueError, match="Unknown model provider"):
        get_provider_client("not_a_real_provider")


def test_openai_compatible_provider_marks_result_non_deterministic():
    client = OpenAICompatibleProvider()
    fake_payload = {"choices": [{"message": {"content": "Hello, world!"}}]}
    with patch(
        "opencomplai_core.model_providers.urllib.request.urlopen",
        return_value=_FakeResponse(fake_payload),
    ):
        result = client.complete("Say hello", model="gpt-4o-mini", api_key="fake-key")

    assert isinstance(result, ProviderCompletion)
    assert result.deterministic is False
    assert result.completion == "Hello, world!"
    assert result.provider == "openai_compatible"
    assert result.model == "gpt-4o-mini"


def test_model_providers_module_never_imported_by_check_path():
    """Guard: `opencomplai check`'s default path must never import model_providers."""
    import opencomplai_core.engine as engine_module

    source = open(engine_module.__file__, encoding="utf-8").read()
    assert "model_providers" not in source
