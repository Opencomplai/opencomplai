"""
Content-Addressable Store (CAS) for immutable evidence objects.

Evidence objects are stored keyed by their SHA-256 content hash.
Retrieval is always by hash — objects are immutable once written
(REQ-EV-002, WORM semantics).

Two backends are supported:
- LocalCASBackend  : local filesystem (default; used by Docker / community)
- VercelBlobCASBackend : Vercel Blob object store (used for hosted Vercel deployment)

The active backend is selected by the STORAGE_BACKEND env var:
  STORAGE_BACKEND=local        → LocalCASBackend (default)
  STORAGE_BACKEND=vercel_blob  → VercelBlobCASBackend
"""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from pathlib import Path


class CASBackend(ABC):
    """Abstract interface for content-addressable evidence storage."""

    @abstractmethod
    def write(self, content: bytes) -> str:
        """Store content and return its canonical hash (``sha256:<hex>``)."""

    @abstractmethod
    def read(self, content_hash: str) -> bytes:
        """Return content by hash. Raises FileNotFoundError if missing."""

    @abstractmethod
    def exists(self, content_hash: str) -> bool:
        """Return True if an object with this hash exists."""


class LocalCASBackend(CASBackend):
    """Local filesystem content-addressable store."""

    def __init__(self, base_dir: str) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, content_hash: str) -> Path:
        prefix = content_hash.replace("sha256:", "")[:2]
        return self.base_dir / prefix / content_hash.replace("sha256:", "")

    def write(self, content: bytes) -> str:
        digest = hashlib.sha256(content).hexdigest()
        content_hash = f"sha256:{digest}"
        dest = self._path_for(content_hash)

        if dest.exists():
            return content_hash

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return content_hash

    def read(self, content_hash: str) -> bytes:
        path = self._path_for(content_hash)
        if not path.exists():
            raise FileNotFoundError(f"Evidence object not found: {content_hash}")

        content = path.read_bytes()
        actual_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if actual_hash != content_hash:
            raise ValueError(
                f"Integrity violation: stored object hash {actual_hash} "
                f"does not match requested hash {content_hash}"
            )
        return content

    def exists(self, content_hash: str) -> bool:
        return self._path_for(content_hash).exists()


class VercelBlobCASBackend(CASBackend):
    """
    Vercel Blob content-addressable store.

    Requires:
      BLOB_READ_WRITE_TOKEN  — issued from the Vercel project's Blob settings
    """

    _BLOB_PREFIX = "evidence/"

    def __init__(self) -> None:
        try:
            import vercel_blob  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "vercel-blob package is required for STORAGE_BACKEND=vercel_blob. "
                "Add it to your requirements: pip install vercel-blob"
            ) from exc
        self._blob = vercel_blob

    def _key(self, content_hash: str) -> str:
        hex_part = content_hash.replace("sha256:", "")
        return f"{self._BLOB_PREFIX}{hex_part[:2]}/{hex_part}"

    def write(self, content: bytes) -> str:
        digest = hashlib.sha256(content).hexdigest()
        content_hash = f"sha256:{digest}"

        if self.exists(content_hash):
            return content_hash

        self._blob.put(
            self._key(content_hash),
            content,
            {"access": "private", "addRandomSuffix": False},
        )
        return content_hash

    def read(self, content_hash: str) -> bytes:
        if not self.exists(content_hash):
            raise FileNotFoundError(f"Evidence object not found: {content_hash}")

        result = self._blob.download(self._key(content_hash))
        content: bytes = result if isinstance(result, bytes) else result.content
        actual_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if actual_hash != content_hash:
            raise ValueError(
                f"Integrity violation: stored object hash {actual_hash} "
                f"does not match requested hash {content_hash}"
            )
        return content

    def exists(self, content_hash: str) -> bool:
        try:
            self._blob.head(self._key(content_hash))
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Backwards-compatible alias so existing callers (e.g. tests) keep working
# ---------------------------------------------------------------------------
CASStore = LocalCASBackend


def get_cas_backend(evidence_data_dir: str | None = None) -> CASBackend:
    """
    Return the CAS backend selected by the STORAGE_BACKEND env var.

    STORAGE_BACKEND=vercel_blob  → VercelBlobCASBackend
    anything else (default)      → LocalCASBackend
    """
    backend = os.environ.get("STORAGE_BACKEND", "local").lower()
    if backend == "vercel_blob":
        return VercelBlobCASBackend()
    base_dir = evidence_data_dir or os.environ.get("EVIDENCE_DATA_DIR", "/tmp/evidence")
    return LocalCASBackend(base_dir)
