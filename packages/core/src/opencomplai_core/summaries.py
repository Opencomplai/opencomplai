"""Closed `summaries` block of the scan-status artifact.

Leaf types only: bounded ints, bools, enums, sha256 hex, `YYYY-MM-DD` dates.
No free text, so nothing here can carry a narrative to the dashboard; chain
heads are typed `log_head_sha256` leaves.

needs_founder_review: true (E-15). This field set is a closed contract mirrored
by the hosted dashboard's ingest schema: no key may be added without a new,
deliberate re-pin of that schema.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from opencomplai_core.serialization import OMIT_NONE, OmitRule, omit_by_table

Count = Annotated[int, Field(ge=0, le=1_000_000)]
Day = Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", max_length=10)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$", max_length=64)]
IncidentId = Annotated[
    str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$", max_length=40)
]
KeyId = Annotated[str, Field(pattern=r"^[0-9a-f]{16}$", max_length=16)]

ClauseState = Literal["present", "unfilled", "missing", "unverified"]
_MAX_ITEMS = 50


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OversightSummary(_Closed):
    entries: Count
    approvals: Count
    resumes: Count
    roles: Count
    last_event_on: Day | None = None
    chain_valid: bool | None = None
    log_head_sha256: Sha256 | None = None


class AgentsSummary(_Closed):
    agents: Count
    with_mandate: Count
    with_guardrails: Count
    undeclared: Count | None = None
    log_entries: Count | None = None
    out_of_mandate: Count | None = None
    chain_valid: bool | None = None
    log_head_sha256: Sha256 | None = None


class QmsClauses(_Closed):
    a: ClauseState
    b: ClauseState
    c: ClauseState
    d: ClauseState
    e: ClauseState
    f: ClauseState
    g: ClauseState
    h: ClauseState
    i: ClauseState
    j: ClauseState
    k: ClauseState
    l: ClauseState  # noqa: E741
    m: ClauseState


class QmsSummary(_Closed):
    clauses: QmsClauses
    size_tier: Literal["micro", "small", "medium", "large", "unknown"] | None = None


class IncidentClass(StrEnum):
    UNCLASSIFIED = "unclassified"
    DEATH = "death"
    HEALTH_HARM = "health_harm"
    CRITICAL_INFRASTRUCTURE = "critical_infrastructure"
    FUNDAMENTAL_RIGHTS = "fundamental_rights"
    PROPERTY_ENVIRONMENT = "property_environment"
    WIDESPREAD_INFRINGEMENT = "widespread_infringement"


class IncidentItem(_Closed):
    incident_id: IncidentId
    incident_class: IncidentClass
    status: Literal["open", "closed"]
    declared_on: Day
    aware_on: Day
    reported_on: Day | None = None
    closed_on: Day | None = None
    party_types: list[Literal["authority", "deployer", "importer", "distributor"]] = (
        Field(default_factory=list, max_length=4)
    )


class IncidentsSummary(_Closed):
    open: Count
    closed: Count
    items: list[IncidentItem] = Field(default_factory=list, max_length=_MAX_ITEMS)


class PackKind(StrEnum):
    DEPLOYER = "deployer"


class PackIssuance(_Closed):
    pack_sha256: Sha256
    issued_on: Day
    kind: PackKind
    signer_key_id: KeyId | None = None
    items_provided: Count | None = None
    items_not_captured: Count | None = None


class PacksSummary(_Closed):
    issued: Count
    items: list[PackIssuance] = Field(default_factory=list, max_length=_MAX_ITEMS)


# Unset sub-objects vanish from the bytes; the schema does not accept null.
_SUMMARIES_OMIT: dict[str, OmitRule] = dict.fromkeys(
    ("oversight", "agents", "qms", "incidents", "packs"), OMIT_NONE
)


class ArtifactSummaries(_Closed):
    oversight: OversightSummary | None = None
    agents: AgentsSummary | None = None
    qms: QmsSummary | None = None
    incidents: IncidentsSummary | None = None
    packs: PacksSummary | None = None

    @model_serializer(mode="wrap")
    def _omit_unset(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        return omit_by_table(self, handler(self), _SUMMARIES_OMIT)
