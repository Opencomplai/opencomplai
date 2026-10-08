"""Run every CLI test in a throwaway cwd so `check` never writes into the repo root."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _hermetic_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
