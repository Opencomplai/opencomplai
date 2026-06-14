"""
Vercel serverless entry point for the egress-proxy service.

On Vercel, outbound network access is unrestricted at the infrastructure level;
the egress-proxy still enforces the application-level allowlist via ALLOWED_DESTINATIONS.
"""

import os
import sys

_root = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(_root, "services", "egress-proxy", "src"))
sys.path.insert(0, os.path.join(_root, "packages", "core", "src"))

from opencomplai_egress_proxy.main import app  # noqa: E402

__all__ = ["app"]
