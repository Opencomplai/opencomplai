"""examples/framework-gates: every registered framework has a parseable gate example."""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core.frameworks import FRAMEWORKS
from opencomplai_core.project_config import load_project_config

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "examples" / "framework-gates"
KEYS = [k for k in FRAMEWORKS if not k.startswith("CUSTOM_")]


@pytest.mark.parametrize("key", KEYS)
def test_example_exists_and_parses(key: str) -> None:
    path = EXAMPLES / key / "opencomplai.yaml"
    assert path.is_file(), f"no gate example for {key}"
    cfg = load_project_config(path)
    if key == "EU_AI_ACT":
        assert cfg.gate_frameworks == []
        assert cfg.scan_fail_on == "major"
    else:
        assert cfg.gate_frameworks == [key]
        assert cfg.gate_fail_on == "missing"


def test_every_folder_is_a_registered_key() -> None:
    folders = [p.name for p in EXAMPLES.iterdir() if p.is_dir()]
    assert folders
    assert set(folders) <= set(FRAMEWORKS)
