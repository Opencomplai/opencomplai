# OpenComplAI remediation example — Art. 50 transparency middleware (ASGI)
#
# LICENSE NOTICE: This file is AGPL-3.0 example code shipped with OpenComplAI.
# Copying it into a proprietary application may create AGPL obligations.
# Treat as a starting point; have counsel review before production use.
#
# What: disclose AI interaction to end users via response headers.
# When: user-facing AI endpoints (Art. 50 transparency).
# Don't: treat this as legal compliance by itself.

from __future__ import annotations

from collections.abc import Awaitable, Callable

# Compatible with Starlette/FastAPI ASGI apps
Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]
Scope = dict


class TransparencyMiddleware:
    """Add an AI-disclosure header on every HTTP response."""

    def __init__(self, app: Callable, notice: str = "This service uses AI systems.") -> None:
        self.app = app
        self.notice = notice

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_header(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-ai-disclosure", self.notice.encode("utf-8")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_header)
