"""The framework data export follows the parity check."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[3] / "tools" / "packs"
sys.path.insert(0, str(TOOLS))

import export_framework_data as export  # noqa: E402
import parity_check  # noqa: E402
from opencomplai_core.pack_registry import discover_packs  # noqa: E402

EU_MAP = (
    Path(export.__file__).resolve().parents[2]
    / "packages/core/src/opencomplai_core/data/gap_article_map.json"
)


@pytest.fixture(scope="module")
def data():
    return export.build_framework_data()


def _fw(data, key):
    return next(f for f in data["frameworks"] if f["key"] == key)


def test_fifteen_keys_in_registry_order(data):
    assert data["schema"] == 1
    assert [f["key"] for f in data["frameworks"]] == [m["id"] for m in discover_packs()]
    assert len(data["frameworks"]) == 15


def test_counts_add_up(data):
    for fw in data["frameworks"]:
        assert fw["machine"] + fw["hybrid"] + fw["organisational"] == fw["rows"], fw[
            "key"
        ]
        assert set(fw["parity"]) >= {f"P{n}" for n in range(1, 16)}


def test_eu_is_the_reference(data):
    eu = _fw(data, "EU_AI_ACT")
    assert eu["status"] == "evaluated"
    assert eu["parity"]["reference"] is True
    assert all(eu["parity"].values())


def test_eu_counts_follow_the_source_rule(data):
    rows = [
        v
        for k, v in json.loads(EU_MAP.read_text("utf-8")).items()
        if not k.startswith("_")
    ]
    want = {"machine": 0, "hybrid": 0, "organisational": 0}
    for r in rows:
        srcs = r["sources"]
        att = [s for s in srcs if s["kind"] == "attestation"]
        other = [
            s
            for s in srcs
            if s["kind"] != "attestation" and s.get("role") != "supporting"
        ]
        want["machine" if not att else "hybrid" if other else "organisational"] += 1
    eu = _fw(data, "EU_AI_ACT")
    assert {c: eu[c] for c in want} == want
    assert eu["rows"] == len(rows)


def test_failing_capability_demotes(monkeypatch):
    monkeypatch.setitem(
        parity_check.CHECKS, "P1", lambda ctx: (parity_check.FAIL, "forced")
    )
    gdpr = _fw(export.build_framework_data(), "GDPR")
    assert gdpr["status"] == "attestation-led"
    assert gdpr["parity"]["P1"] is False
    assert _fw(export.build_framework_data(), "NIST_AI_RMF")["status"] == "derived"


def test_check_fails_on_an_edited_copy(data, tmp_path, capsys):
    path = tmp_path / "frameworks.json"
    assert export.main(["--out", str(path)]) == 0
    assert export.main(["--check", str(path)]) == 0
    path.write_text(path.read_text("utf-8").replace('"GDPR"', '"GDPX"', 1), "utf-8")
    assert export.main(["--check", str(path)]) == 1
    assert "GDPX" in capsys.readouterr().out


def test_prints(data, capsys):
    assert export.main(["--print", "standing-line"]) == 0
    assert "15 frameworks" in capsys.readouterr().out
    assert export.main(["--print", "status-table"]) == 0
    assert capsys.readouterr().out.count("\n") == 17
