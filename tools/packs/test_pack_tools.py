"""Tests for the pack tools: canonical pack writer against the tracked pack data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import packfmt

PACK_DIR = (
    Path(__file__).resolve().parents[2] / "packages/core/src/opencomplai_core/packs"
)

PACKS = [
    "iso_27001",
    "soc_2",
    "nis2",
    "dora",
    "eba",
    "eiopa_ai",
    "gdpr",
    "cra",
    "etsi_en_304_223",
    "iso_42005",
    "iso_23894",
]
KEYS = {
    "iso_27001": "ISO_IEC_27001",
    "soc_2": "SOC_2",
    "nis2": "NIS2",
    "dora": "DORA",
    "eba": "EBA",
    "eiopa_ai": "EIOPA_AI",
    "gdpr": "GDPR",
    "cra": "CRA",
    "etsi_en_304_223": "ETSI_EN_304_223",
    "iso_42005": "ISO_IEC_42005",
    "iso_23894": "ISO_IEC_23894",
    "iso_42001": "ISO_IEC_42001",
}


@pytest.mark.parametrize("name", [*PACKS, "iso_42001"])
def test_dump_round_trips(name):
    text = (PACK_DIR / KEYS[name] / "requirements.json").read_text(encoding="utf-8")
    assert packfmt.dump(json.loads(text)) == text
