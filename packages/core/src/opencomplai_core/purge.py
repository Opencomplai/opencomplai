"""
Bias data purge helpers (REQ-GTVG-002).

The service-level purge that deletes BiasAlert DB records lives in
services/evidence-vault. This module provides pure helper functions
that work with any storage layer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def expired_cutoff(retention_days: int) -> datetime:
    """Return the UTC cutoff datetime: records older than this are expired."""
    return datetime.now(UTC) - timedelta(days=retention_days)


def is_expired(record_ts: datetime, cutoff: datetime) -> bool:
    """Return True if record_ts is before cutoff (i.e. the record is expired)."""
    if record_ts.tzinfo is None:
        record_ts = record_ts.replace(tzinfo=UTC)
    return record_ts < cutoff
