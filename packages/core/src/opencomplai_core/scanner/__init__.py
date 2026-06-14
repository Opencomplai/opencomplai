"""Hybrid AI-usage scanner — corroboration engine."""

from opencomplai_core.scanner.constants import SCANNER_VERSION

__all__ = ["SCANNER_VERSION", "get_detector_registry"]


def get_detector_registry():
    from opencomplai_core.scanner.registry import DETECTOR_REGISTRY

    return DETECTOR_REGISTRY
