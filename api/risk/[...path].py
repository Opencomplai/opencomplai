"""
Vercel serverless entry point for the risk-engine service.

Adds the service source and shared core package to sys.path so the existing
FastAPI app can be imported without any code changes.
"""

import os
import sys

_root = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(_root, "services", "risk-engine", "src"))
sys.path.insert(0, os.path.join(_root, "packages", "core", "src"))

from opencomplai_risk_engine.main import app  # noqa: E402

# Vercel detects an ASGI app assigned to a module-level `app` variable.
__all__ = ["app"]
