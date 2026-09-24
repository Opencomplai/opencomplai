"""wrap_scan_output keeps the EU AI Act disclaimer unless told otherwise."""

from __future__ import annotations

from opencomplai_core.models import DISCLAIMER_V1, DISCLAIMER_V2
from opencomplai_core.output_envelope import wrap_scan_output


def test_envelope_defaults_to_eu_disclaimer():
    assert wrap_scan_output({}).disclaimer == DISCLAIMER_V1


def test_envelope_carries_the_given_disclaimer():
    envelope = wrap_scan_output({"k": 1}, disclaimer=DISCLAIMER_V2)

    assert envelope.disclaimer == DISCLAIMER_V2
    assert envelope.payload == {"k": 1}
    assert "EU AI Act" not in DISCLAIMER_V2
