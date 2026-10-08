"""The generated principles page must match the generator output."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def test_principles_page_matches_generator():
    scripts = Path(__file__).parents[3] / "scripts"
    spec = importlib.util.spec_from_file_location(
        "generate_principle_docs", scripts / "generate_principle_docs.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = module.OUTPUT_PATH.read_text(encoding="utf-8")
    assert module.render().replace("\r\n", "\n") == committed.replace("\r\n", "\n")
