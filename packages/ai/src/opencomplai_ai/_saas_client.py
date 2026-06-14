"""Cloud API backend — routes to https://api.opencomplai.com/v1/intent."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from opencomplai_ai.models import IntentAnnotation, derive_eu_obligations

_API_URL = "https://api.opencomplai.com/v1/intent"


class SaaSIntentClient:
    def __init__(self) -> None:
        self._api_key = os.environ.get("OPENCOMPLAI_API_KEY", "")

    def classify(self, snippet: str) -> IntentAnnotation:
        if not self._api_key:
            return IntentAnnotation(
                model_id="saas",
                explanation="OPENCOMPLAI_API_KEY not set — set it to use cloud intent analysis.",
            )
        try:
            payload = json.dumps({"snippet": snippet}).encode("utf-8")
            req = urllib.request.Request(
                _API_URL,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())

            autonomy = data.get("decision_autonomy", "unknown")
            subject = data.get("subject_type", "unknown")
            consequential = data.get("consequential", "unknown")
            obligations = derive_eu_obligations(autonomy, subject, consequential)  # type: ignore[arg-type]
            return IntentAnnotation(
                decision_autonomy=autonomy,  # type: ignore[arg-type]
                subject_type=subject,  # type: ignore[arg-type]
                consequential=consequential,  # type: ignore[arg-type]
                eu_obligation=obligations,
                explanation=data.get("explanation"),
                model_id="saas",
                confidence=data.get("confidence", 0.9),
            )
        except Exception:
            return IntentAnnotation(
                model_id="saas",
                explanation="Cloud intent API unavailable — check OPENCOMPLAI_API_KEY and network.",
            )
