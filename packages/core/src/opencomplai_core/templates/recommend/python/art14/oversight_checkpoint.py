# OpenComplAI remediation example — Art. 14 human oversight checkpoint
#
# LICENSE NOTICE: AGPL-3.0 example code. Copying into proprietary apps may
# create AGPL obligations — review with counsel before production use.
#
# What: require an explicit human approval before a high-impact AI action.
# When: agentic or high-risk workflows (Art. 14 human oversight).
# Don't: auto-approve in production by default.

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class OversightDecision:
    approved: bool
    reviewer: str
    reason: str = ""


def require_human_approval(
    action_label: str,
    prompt_fn: Callable[[str], str] | None = None,
) -> OversightDecision:
    """Block until a human confirms the AI-proposed action.

    ``prompt_fn`` defaults to built-in ``input`` for CLI tools; web apps should
    replace this with a ticket / UI approval flow.
    """
    ask = prompt_fn or input
    answer = ask(f"[HITL] Approve action '{action_label}'? [y/N]: ").strip().lower()
    approved = answer in {"y", "yes"}
    reviewer = ask("Reviewer id: ").strip() or "anonymous"
    reason = ask("Reason: ").strip()
    return OversightDecision(approved=approved, reviewer=reviewer, reason=reason)
