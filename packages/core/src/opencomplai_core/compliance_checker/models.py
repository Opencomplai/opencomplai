"""Pydantic models for the FLI EU AI Act Compliance Checker."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

CHECKER_VERSION = "fli-2025-07-28"


class EntityType(StrEnum):
    """Operator role under EU AI Act Article 3(3)."""

    PROVIDER = "provider"
    DEPLOYER = "deployer"
    DISTRIBUTOR = "distributor"
    IMPORTER = "importer"
    PRODUCT_MANUFACTURER = "product_manufacturer"
    AUTHORISED_REP = "authorised_rep"


class StatusChangeItem(BaseModel):
    """A status transition surfaced to the user during evaluation."""

    id: str
    title: str
    body: str


class ObligationItem(BaseModel):
    """An applicable EU AI Act obligation."""

    id: str
    title: str
    body: str
    article_ref: str


class CheckerSession(BaseModel):
    """User answers keyed by FLI question identifiers."""

    answers: dict[str, Any] = Field(
        default_factory=dict,
        description="Question answers keyed by FLI node id (e.g. gate_is_ai_system)",
    )


class ComplianceCheckerResult(BaseModel):
    """Deterministic output of evaluate()."""

    checker_version: str = Field(default=CHECKER_VERSION)
    in_scope: bool = Field(
        ...,
        description="False when the AI Act does not apply to this assessment",
    )
    status_changes: list[StatusChangeItem] = Field(default_factory=list)
    obligations: list[ObligationItem] = Field(default_factory=list)
    determination_path: list[str] = Field(
        default_factory=list,
        description="Ordered trace of engine nodes visited",
    )
    is_high_risk: bool = False
    is_prohibited: bool = False
    effective_entity: EntityType | None = None
    answers: dict[str, Any] = Field(
        default_factory=dict,
        description="Answer snapshot for audit exports and manifest replay",
    )
    session_id: str | None = Field(
        None, description="UUID for this checker run when persisted"
    )
