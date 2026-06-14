"""Tests for the content-addressable store (REQ-EV-002)."""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_evidence_vault.cas import CASStore


@pytest.fixture
def cas(tmp_path: Path) -> CASStore:
    return CASStore(str(tmp_path / "cas"))


def test_write_returns_sha256_prefixed_hash(cas: CASStore):
    content_hash = cas.write(b"hello world")
    assert content_hash.startswith("sha256:")


def test_write_is_idempotent(cas: CASStore):
    h1 = cas.write(b"idempotent content")
    h2 = cas.write(b"idempotent content")
    assert h1 == h2


def test_read_returns_original_content(cas: CASStore):
    content = b"test evidence payload"
    content_hash = cas.write(content)
    retrieved = cas.read(content_hash)
    assert retrieved == content


def test_read_missing_raises_file_not_found(cas: CASStore):
    with pytest.raises(FileNotFoundError):
        cas.read("sha256:" + "0" * 64)


def test_read_tampered_raises_value_error(cas: CASStore):
    content = b"original content"
    content_hash = cas.write(content)
    path = cas._path_for(content_hash)
    path.write_bytes(b"tampered content")
    with pytest.raises(ValueError, match="Integrity violation"):
        cas.read(content_hash)


def test_exists(cas: CASStore):
    content_hash = cas.write(b"existence test")
    assert cas.exists(content_hash) is True
    assert cas.exists("sha256:" + "f" * 64) is False
