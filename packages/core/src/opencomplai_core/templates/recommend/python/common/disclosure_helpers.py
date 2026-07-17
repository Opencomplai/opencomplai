# OpenComplAI remediation example — Art. 50 ASGI/Flask disclosure helpers
#
# LICENSE NOTICE: AGPL-3.0 example code. Copying into proprietary apps may
# create AGPL obligations — review with counsel before production use.
#
# What: lightweight disclosure helpers for web frameworks.
# When: chat UIs or API gateways that surface AI responses.
# Don't: hide the notice behind CSS-only banners without accessible text.

from __future__ import annotations

from typing import Any

DISCLOSURE_TEXT = (
    "This interface uses artificial intelligence. Outputs may be inaccurate."
)


def flask_after_request(response: Any) -> Any:
    """Attach a disclosure header on Flask responses."""
    response.headers["X-AI-Disclosure"] = DISCLOSURE_TEXT
    return response


async def asgi_disclosure_middleware(app, scope, receive, send):  # type: ignore[no-untyped-def]
    """Minimal ASGI wrapper adding X-AI-Disclosure on HTTP responses."""

    async def send_wrapper(message: dict) -> None:
        if message.get("type") == "http.response.start":
            headers = list(message.get("headers", []))
            headers.append((b"x-ai-disclosure", DISCLOSURE_TEXT.encode("utf-8")))
            message = {**message, "headers": headers}
        await send(message)

    await app(scope, receive, send_wrapper)
