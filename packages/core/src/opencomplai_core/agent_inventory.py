"""Declared agent inventory carried in the system manifest.

The inventory is a provider's own declaration of the agents, tools, models,
mandate, delegation, guardrails and logging of an agent system. This module
records it verbatim and checks that it is internally consistent; it never
generates or interprets compliance content (``responsibility_map`` is free
text written by the provider).

Two conventions here are design choices, not sourced from any standard:

* A tool reference in a mandate is the string ``tool:<name>``.
* A tool reference must name a tool declared by the *same* agent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_Str = Annotated[str, Field(min_length=1)]
_TOOL_PREFIX = "tool:"


def _check_iso(value: str | None) -> str | None:
    if value is not None:
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"not an ISO 8601 date or timestamp: {value!r}") from exc
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentTool(_Strict):
    name: _Str
    kind: Literal["mcp", "function", "api"]
    scope: str | None = None
    side_effects: bool | None = None
    requires_approval: bool | None = None


class AgentModelRef(_Strict):
    provider: _Str
    model: _Str
    via: str | None = None


class AgentMandate(_Strict):
    """What the agent may and may not do, as the provider declared it.

    An entry of the form ``tool:<name>`` in either action list must name a
    tool declared by the same agent (see :func:`check_inventory`).
    """

    permitted_actions: list[str] = Field(default_factory=list)
    prohibited_actions: list[str] = Field(default_factory=list)
    limits: dict[str, str | int | float | bool] = Field(default_factory=dict)
    granted_by: str | None = None
    granted_at: str | None = None
    expires_at: str | None = None
    review_cadence: str | None = None

    _iso = field_validator("granted_at", "expires_at")(_check_iso)


class AgentDelegation(_Strict):
    may_delegate_to: list[_Str] = Field(default_factory=list)
    max_depth: int | None = Field(None, ge=0)


class AgentGuardrail(_Strict):
    kind: _Str
    evidence_ref: str | None = None


class AgentLogging(_Strict):
    decision_log_ref: str | None = None
    captures_intent: bool | None = None


class AgentSpec(_Strict):
    id: _Str
    name: _Str
    parent_id: str | None = Field(None, min_length=1)
    tools: list[AgentTool] = Field(default_factory=list)
    models: list[AgentModelRef] = Field(default_factory=list)
    mandate: AgentMandate | None = None
    delegation: AgentDelegation | None = None
    guardrails: list[AgentGuardrail] = Field(default_factory=list)
    logging: AgentLogging | None = None

    @model_validator(mode="after")
    def _unique_tool_names(self) -> AgentSpec:
        names = [t.name for t in self.tools]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"agent {self.id!r}: duplicate tool name {dupes[0]!r}")
        return self


class ResponsibilityMap(_Strict):
    """Free-form provider declaration; recorded verbatim, never interpreted."""

    customer_obligations: list[str] = Field(default_factory=list)
    upstream_provider_obligations: list[str] = Field(default_factory=list)


class AgentInventory(_Strict):
    agents: list[AgentSpec] = Field(..., min_length=1)
    responsibility_map: ResponsibilityMap | None = None

    @model_validator(mode="after")
    def _unique_agent_ids(self) -> AgentInventory:
        ids = [a.id for a in self.agents]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate agent id {dupes[0]!r}")
        return self


def check_inventory(inv: AgentInventory) -> list[str]:
    """Deep graph checks; returns sorted errors, each naming the agent id."""
    by_id = {a.id: a for a in inv.agents}
    errors: set[str] = set()

    # (a) dangling parents, (b) parent cycles. Every walk uses a visited set.
    cyclic: set[str] = set()  # agents whose parent chain loops
    for agent in inv.agents:
        if agent.parent_id is not None and agent.parent_id not in by_id:
            errors.add(f"agent {agent.id!r}: dangling parent {agent.parent_id!r}")
        seen: set[str] = set()
        cur: str | None = agent.id
        while cur is not None and cur in by_id:
            if cur in seen:
                cyclic.add(agent.id)
                errors.add(f"agent {cur!r}: parent cycle")
                break
            seen.add(cur)
            cur = by_id[cur].parent_id

    # (c) delegation: dangling delegates, and descendant depth vs max_depth.
    # Longest chain below each acyclic agent, found by walking up from each.
    height: dict[str, int] = {}
    for agent in inv.agents:
        if agent.id in cyclic:
            continue
        dist, cur = 0, agent.parent_id
        while cur is not None and cur in by_id:
            dist += 1
            height[cur] = max(height.get(cur, 0), dist)
            cur = by_id[cur].parent_id
    for agent in inv.agents:
        d = agent.delegation
        if d is None:
            continue
        for target in d.may_delegate_to:
            if target not in by_id:
                errors.add(f"agent {agent.id!r}: dangling delegate {target!r}")
        if (
            d.max_depth is not None
            and agent.id not in cyclic
            and height.get(agent.id, 0) > d.max_depth
        ):
            errors.add(
                f"agent {agent.id!r}: delegation depth {height[agent.id]} "
                f"exceeds max_depth {d.max_depth}"
            )

    # (d) tool refs in the mandate must name a tool of the same agent.
    for agent in inv.agents:
        if agent.mandate is None:
            continue
        known = {t.name for t in agent.tools}
        for action in (
            *agent.mandate.permitted_actions,
            *agent.mandate.prohibited_actions,
        ):
            if action.startswith(_TOOL_PREFIX):
                name = action[len(_TOOL_PREFIX) :]
                if name not in known:
                    errors.add(f"agent {agent.id!r}: unknown tool ref {name!r}")
    return sorted(errors)
