"""Tests for purge helper functions (REQ-GTVG-002)."""

from datetime import UTC, datetime, timedelta

from opencomplai_core.purge import expired_cutoff, is_expired


def test_expired_cutoff_is_in_past() -> None:
    cutoff = expired_cutoff(retention_days=90)
    assert cutoff < datetime.now(UTC)


def test_expired_cutoff_correct_delta() -> None:
    before = datetime.now(UTC)
    cutoff = expired_cutoff(retention_days=30)
    datetime.now(UTC)
    expected_approx = before - timedelta(days=30)
    # Allow 2-second drift
    assert abs((cutoff - expected_approx).total_seconds()) < 2


def test_is_expired_old_record() -> None:
    cutoff = datetime.now(UTC)
    old_ts = cutoff - timedelta(days=1)
    assert is_expired(old_ts, cutoff) is True


def test_is_expired_fresh_record() -> None:
    cutoff = datetime.now(UTC) - timedelta(days=90)
    fresh_ts = datetime.now(UTC)
    assert is_expired(fresh_ts, cutoff) is False


def test_is_expired_naive_datetime_treated_as_utc() -> None:
    cutoff = datetime.now(UTC)
    naive_old = datetime.utcnow() - timedelta(hours=1)  # naive UTC
    assert is_expired(naive_old, cutoff) is True


def test_is_expired_boundary_exclusive() -> None:
    cutoff = datetime(2026, 1, 1, tzinfo=UTC)
    exactly_at_cutoff = datetime(2026, 1, 1, tzinfo=UTC)
    # Boundary: not strictly less than, so not expired
    assert is_expired(exactly_at_cutoff, cutoff) is False
