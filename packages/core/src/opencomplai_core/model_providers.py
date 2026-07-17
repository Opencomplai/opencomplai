"""Optional, explicitly opt-in model-provider clients for `opencomplai eval`.

Distinct from `adapters/http.py` (`HTTPAdapter`), which is purpose-built for
ground-truth claim verification routed through the egress proxy (a different
interface: `lookup(claim: dict) -> dict`, async, egress-proxy-only). A model-provider
call here sends a prompt and gets a completion back from an external model API —
confirmed during this deliverable's pre-read that `HTTPAdapter` is not reusable for
this purpose, so this module is a narrowly-scoped, separate client.

HARD RULE: nothing in this module is ever called from `opencomplai check`'s default
(air-gapped) path. It is only reachable via `opencomplai eval --provider ...`, an
explicit, clearly-labeled opt-in. Every result produced here must be tagged
non-deterministic so it is never mistaken for the default lexical evaluators' output.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProviderCompletion:
    """A single provider call result. Always non-deterministic/network-dependent."""

    provider: str
    model: str
    prompt: str
    completion: str
    deterministic: bool = False


class ModelProviderClient(ABC):
    """Sends a prompt to an external model API and returns the completion."""

    @property
    @abstractmethod
    def provider_id(self) -> str: ...

    @abstractmethod
    def complete(self, prompt: str, *, model: str, api_key: str) -> ProviderCompletion: ...


class OpenAICompatibleProvider(ModelProviderClient):
    """Client for any OpenAI-compatible chat completions endpoint.

    Covers OpenAI itself and any self-hosted/vLLM/compatible-API deployment that
    implements the same `/v1/chat/completions` shape — kept generic rather than
    OpenAI-specific so a single client covers the common case described in the plan
    ("OpenAI/HF/vLLM-hosted models").
    """

    def __init__(self, base_url: str = "https://api.openai.com/v1") -> None:
        self._base_url = base_url.rstrip("/")

    @property
    def provider_id(self) -> str:
        return "openai_compatible"

    def complete(self, prompt: str, *, model: str, api_key: str) -> ProviderCompletion:
        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            msg = f"Model provider returned {exc.code}: {body}"
            raise RuntimeError(msg) from exc
        except Exception as exc:
            msg = f"Model provider call failed: {exc}"
            raise RuntimeError(msg) from exc

        completion = data["choices"][0]["message"]["content"]
        return ProviderCompletion(
            provider=self.provider_id,
            model=model,
            prompt=prompt,
            completion=completion,
            deterministic=False,
        )


_PROVIDER_REGISTRY: dict[str, type[ModelProviderClient]] = {
    "openai": OpenAICompatibleProvider,
    "openai_compatible": OpenAICompatibleProvider,
}


def get_provider_client(provider: str, *, base_url: str | None = None) -> ModelProviderClient:
    provider_cls = _PROVIDER_REGISTRY.get(provider)
    if provider_cls is None:
        known = ", ".join(sorted(_PROVIDER_REGISTRY))
        msg = f"Unknown model provider {provider!r}. Known providers: {known}"
        raise ValueError(msg)
    if base_url is not None:
        return provider_cls(base_url=base_url)
    return provider_cls()
