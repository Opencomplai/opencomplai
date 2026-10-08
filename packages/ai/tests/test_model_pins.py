"""Offline checks that downloadable model specs are pinned (no network)."""

from __future__ import annotations

import re
from pathlib import Path

from opencomplai_ai import models
from opencomplai_ai.models import MODEL_CATALOG

REV = re.compile(r"^[0-9a-f]{40}$")
SHA = re.compile(r"^[0-9a-f]{64}$")


def _gguf():
    return {k: v for k, v in MODEL_CATALOG.items() if v.runtime == "llama-cpp"}


def test_gguf_specs_are_fully_pinned():
    assert _gguf()
    for mid, spec in _gguf().items():
        assert REV.match(spec.revision), f"{mid}: revision not a 40-hex commit"
        assert SHA.match(spec.sha256), f"{mid}: sha256 not 64-hex"


def test_hub_specs_have_revision():
    for mid, spec in MODEL_CATALOG.items():
        if spec.hf_repo:
            assert REV.match(spec.revision), f"{mid}: revision not a 40-hex commit"


def test_pins_are_distinct_and_not_placeholders():
    shas = [s.sha256 for s in _gguf().values()]
    assert len(shas) == 5
    assert all(len(set(h)) > 1 for h in shas)
    assert len(set(shas)) == len(shas)


def test_pin_source_recorded():
    text = Path(models.__file__).read_text(encoding="utf-8")
    block = text.split("# PIN_SOURCES", 1)[1].split("MODEL_CATALOG:", 1)[0]
    for mid, spec in MODEL_CATALOG.items():
        if spec.revision:
            assert f"#   {mid}:" in block, f"{mid}: missing from PIN_SOURCES"


def test_codebert_sha256_exemption_is_explicit():
    assert MODEL_CATALOG["codebert-onnx"].sha256 == ""
