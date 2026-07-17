# OpenComplAI remediation example — Art. 12 event logging
#
# LICENSE NOTICE: AGPL-3.0 example code. Copying into proprietary apps may
# create AGPL obligations — review with counsel before production use.
#
# What: log AI interaction events with retention metadata.
# When: any production model call path (Art. 12 record-keeping).
# Don't: log secrets or raw PII without redaction.

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("opencomplai.event_logging")


@dataclass
class AiEvent:
    event_type: str
    system_id: str
    actor: str = "system"
    retention_days: int = 180
    metadata: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def log_ai_event(event: AiEvent) -> None:
    """Emit a structured AI interaction log line (stdout / configured handler)."""
    payload = asdict(event)
    # Callers should redact secrets before attaching metadata.
    logger.info("ai_event %s", json.dumps(payload, sort_keys=True))
