"""Cross-framework links (round FWMAP): every link resolves, and the NIST,
ISO/IEC 42001 and ISO/IEC 27090 data files agree with each other."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from opencomplai_core.frameworks import FRAMEWORKS, load_requirements_map
from opencomplai_core.nist_ai_rmf_subcategories import get_subcategories

EU = {
    k
    for k in load_requirements_map(FRAMEWORKS["EU_AI_ACT"].requirements)
    if not k.startswith("_")
}
ISO42 = load_requirements_map(FRAMEWORKS["ISO_IEC_42001"].requirements)
ISO27 = load_requirements_map(FRAMEWORKS["ISO_IEC_27090"].requirements)
NIST = get_subcategories()


def test_counts():
    assert (len(NIST), len(ISO42), len(ISO27)) == (72, 65, 31)


def test_every_link_resolves():
    for sid, entry in NIST.items():
        assert {a for a, _ in entry.eu_ai_act} <= EU, sid
        assert set(entry.iso_42001) <= set(ISO42), sid
        assert set(entry.iso_27090) <= set(ISO27), sid
    for rows, own in ((ISO42, "iso_27090"), (ISO27, "iso_42001")):
        other = ISO27 if own == "iso_27090" else ISO42
        for rid, row in rows.items():
            assert set(row["eu_ai_act"]) <= EU, rid
            assert set(row["nist_ai_rmf"]) <= set(NIST), rid
            assert set(row[own]) <= set(other), rid


def test_links_agree_in_both_directions():
    for sid, entry in NIST.items():
        for rid in ISO42:
            assert (rid in entry.iso_42001) == (sid in ISO42[rid]["nist_ai_rmf"]), (
                sid,
                rid,
            )
        for rid in ISO27:
            assert (rid in entry.iso_27090) == (sid in ISO27[rid]["nist_ai_rmf"]), (
                sid,
                rid,
            )
    for rid42, row42 in ISO42.items():
        for rid27, row27 in ISO27.items():
            assert (rid27 in row42["iso_27090"]) == (rid42 in row27["iso_42001"]), (
                rid42,
                rid27,
            )


ISO_27001_ANNEX_A = re.compile(
    r"A\.(5\.([1-9]|[12][0-9]|3[0-7])|6\.[1-8]|7\.([1-9]|1[0-4])|8\.([1-9]|[12][0-9]|3[0-4]))"
)
SOC2 = re.compile(r"(CC[1-9]\.[1-9]|A1\.[1-3]|C1\.[12]|PI1\.[1-5]|P[1-8]\.[1-6])")


def test_iso_27090_anchors_are_well_formed_ids():
    for rid, row in ISO27.items():
        assert all(ISO_27001_ANNEX_A.fullmatch(a) for a in row["iso_27001"]), rid
        assert all(SOC2.fullmatch(c) for c in row["soc2"]), rid


def test_mappings_page_is_up_to_date():
    script = (
        Path(__file__).resolve().parents[3]
        / "scripts"
        / "generate_framework_mappings_doc.py"
    )
    result = subprocess.run(
        [sys.executable, str(script), "--check"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout


def test_every_nist_subcategory_has_a_mapping_decision():
    """Each subcategory either re-projects EU AI Act evidence or says why not."""
    for sid, entry in NIST.items():
        assert entry.mapping_note.strip(), sid
        assert len({a for a, _ in entry.eu_ai_act}) == len(entry.eu_ai_act), sid
