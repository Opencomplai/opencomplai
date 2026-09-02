"""
Model-artifact integrity checks (AI-EGRESS, finding 77).

Model downloads previously resolved the Hugging Face default branch with no
revision pin and no checksum, so a compromised or taken-over repo would have
served altered weights that then executed against customer code in CI — a
supply-chain vector against a security tool.

Two properties are enforced here:

* **Pinning.** A spec carrying a ``revision`` is fetched at exactly that
  immutable commit, never at the moving branch head.
* **Checksums, re-verified on cache hits.** A spec carrying a ``sha256`` is
  verified after download *and* every time the cached file is reused.
  Verifying only at download time would let a later modification of the cached
  file — by other software on the machine, or by an attacker with local write
  access — go unnoticed forever, which is precisely the window a cache creates.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

#: Read in chunks: model files run to several GB and must not be loaded whole.
_CHUNK_BYTES = 1024 * 1024


class ModelIntegrityError(RuntimeError):
    """Raised when a model artifact does not match its expected checksum."""


class UnpinnedModelError(RuntimeError):
    """Raised when an unpinned model would be downloaded without confirmation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifact(path: Path, expected_sha256: str, *, context: str) -> None:
    """
    Check ``path`` against ``expected_sha256``.

    A blank expectation is a no-op — the catalog does not yet carry checksums
    for every model (see PLAN/execution/DEFERRED-DECISIONS.md). That is a gap
    to close, not a licence to pretend verification happened, so nothing here
    reports success when there was nothing to check.

    On mismatch the offending file is **deleted** before raising: leaving an
    artifact that failed verification on disk invites the next run to hit it as
    a cache hit, and a corrupt or hostile file is not something to keep.
    """
    if not expected_sha256:
        return

    actual = sha256_file(path)
    if actual != expected_sha256:
        try:
            path.unlink()
        except OSError:  # pragma: no cover — best effort
            pass
        raise ModelIntegrityError(
            f"Checksum mismatch for {path.name} ({context}).\n"
            f"  expected sha256: {expected_sha256}\n"
            f"  actual sha256:   {actual}\n"
            f"The file has been deleted. This can mean a corrupted download, or "
            f"that the upstream artifact was replaced. Do not re-download "
            f"without confirming the expected checksum is still correct."
        )


def describe_pin(revision: str, sha256: str) -> str:
    """One-line provenance summary for a download prompt."""
    parts = []
    parts.append(
        f"revision: {revision}" if revision else "revision: UNPINNED (branch head)"
    )
    parts.append(f"sha256: {sha256[:16]}…" if sha256 else "sha256: NOT VERIFIED")
    return "  ".join(parts)


__all__ = [
    "ModelIntegrityError",
    "UnpinnedModelError",
    "describe_pin",
    "sha256_file",
    "verify_artifact",
]
