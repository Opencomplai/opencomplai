"""
Vercel serverless entry point for the evidence-vault service.

Neon PostgreSQL is used for the ledger DB (DATABASE_URL env var).
Vercel Blob is used for the CAS (STORAGE_BACKEND=vercel_blob + BLOB_READ_WRITE_TOKEN).
"""

import os
import sys

_root = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(_root, "services", "evidence-vault", "src"))
sys.path.insert(0, os.path.join(_root, "packages", "core", "src"))

from opencomplai_evidence_vault.main import app  # noqa: E402

__all__ = ["app"]
