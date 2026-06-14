"""
Vercel serverless entry point for the doc-generator service.

maxDuration is set to 120s in vercel.json to match the dossier generation SLO.
"""

import os
import sys

_root = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(_root, "services", "doc-generator", "src"))
sys.path.insert(0, os.path.join(_root, "packages", "core", "src"))

from opencomplai_doc_generator.main import app  # noqa: E402

__all__ = ["app"]
