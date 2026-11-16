#!/usr/bin/env python3
"""Write docs/src/frameworks/mappings.md from the per-pack directories.

    python scripts/generate_framework_mappings_doc.py          # rewrite the page
    python scripts/generate_framework_mappings_doc.py --check  # exit 1 if stale

packages/core/tests/test_framework_mappings.py runs the --check form.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "packages" / "core" / "src")
)

from opencomplai_core.frameworks import FRAMEWORKS, load_requirements_map
from opencomplai_core.pack_registry import load_pack_meta

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "packages" / "core" / "src" / "opencomplai_core" / "data"
PAGE = REPO_ROOT / "docs" / "src" / "frameworks" / "mappings.md"

HEADER = """# Framework mappings

How each requirement of NIST AI RMF 1.0, ISO/IEC 42001:2023 and ISO/IEC 27090:2026
relates to the EU AI Act and to the other two frameworks, followed by the further native
packs and their links to the EU AI Act, ISO/IEC 27001 and ISO/IEC 42001. This page is
generated from the data files in `packages/core/src/opencomplai_core/data/`; do not edit
it by hand.

The tables below describe 0.16.0. Output from 0.15.0 differs: some rows,
links and statuses here are not in 0.15.0.

- **NIST AI RMF:** the EU AI Act column decides the verdict, except for an article that
  an attestation decides (Art. 4, and Art. 20 from 0.16.0), which counts as no
  NIST evidence and is set aside. The evidence of the other articles is re-projected onto
  the subcategory (worst status, lowest confidence). From 0.16.0, an article
  linked at low confidence reads as Unverified rather than Missing or Partial, so only a
  medium-or-better link can fail a subcategory. A subcategory with no article, or only a
  set-aside one (GOVERN 2.2), takes a provider attestation instead; from 0.16.0
  so does one whose articles all do not apply in the run, according to a recorded checker
  session. MAP 3.4 (Art. 4 and Art. 26) holds at Unverified at best while Art. 26
  applies. So do MANAGE 2.3 (Art. 20, 72 and 73) and MANAGE 2.4 (Art. 14 and Art. 20)
  while Art. 20 applies. Where a recorded checker session shows that Art. 26 does not
  apply, MAP 3.4 takes an attestation and reads Met once one is recorded; where it shows
  that Art. 20 does not apply, MANAGE 2.3 and MANAGE 2.4 read from their other articles.
- **NIST AI RMF to ISO/IEC 42001** links come from NIST's own crosswalk ("NIST AI RMF to
  ISO/IEC FDIS 42001 AI Management System Crosswalk"). Its Annex B guidance numbers are
  read as the Annex A controls, and sub-clauses 7.5.x, 9.2.x and 9.3.x as their parent rows.
- **ISO/IEC 27090 to ISO/IEC 27001 Annex A and SOC 2** anchors are given per row,
  as control ids only; rows without an anchor show "—".
- **Every other link** is this project's own mapping, at low confidence.
- **ISO/IEC 42001 and ISO/IEC 27090** rows show clause ids and short headings only, never
  standard text.
- Every mapping is flagged for founder review. A link says two requirements cover related
  ground. It is not a claim that meeting one meets the other.
"""


def _ids(values: list[str]) -> str:
    return ", ".join(v.split(":", 1)[-1] for v in values) or "—"


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


REVIEW_COLS = ["Evidence class", "Review"]


def _review_cells(row: dict) -> list[str]:
    cls = row.get("evidence_class")
    flag = row.get("needs_founder_review")
    return [
        cls or "â€”",
        "â€”" if flag is None else ("not yet reviewed" if flag else "reviewed"),
    ]


def _section(key: str, heading: str, rows: dict, note: str = "") -> list[str]:
    classes = [r.get("evidence_class") for r in rows.values()]
    out = ["", f"## {heading}", "", f"Key `{key}`.{note}"]
    if any(classes):
        checked = sum(c in ("machine", "hybrid") for c in classes)
        out += ["", f"{checked} of {len(rows)} rows checked from evidence"]
    return [*out, ""]


def _table(cols: list[str]) -> list[str]:
    return ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]


def render() -> str:
    nist = json.loads((DATA / "nist_ai_rmf_subcategories.json").read_text("utf-8"))
    reqs = {
        key: load_requirements_map(pack.requirements)
        for key, pack in FRAMEWORKS.items()
        if pack.requirements
    }
    # Which frameworks link to each ISO/IEC 27001 Annex A control.
    linked_from: dict[str, list[str]] = {}
    for key, rows in reqs.items():
        for row in rows.values():
            for control in row.get("iso_27001", []):
                names = linked_from.setdefault(control, [])
                if key not in names:
                    names.append(key)
    out = [HEADER]
    for key, pack in FRAMEWORKS.items():
        rows = reqs.get(key, {})
        if key == "EU_AI_ACT":
            out += _section(key, pack.label, rows)
            out += _table(["Id", "Sources", *REVIEW_COLS])
            for rid, row in rows.items():
                kinds = ", ".join(sorted({s["kind"] for s in row["sources"]}))
                out.append(
                    f"| {rid} | {kinds} | " + " | ".join(_review_cells(row)) + " |"
                )
        elif key == "NIST_AI_RMF":
            out += _section(key, "NIST AI RMF 1.0", rows)
            out += _table(
                [
                    "Subcategory",
                    "EU AI Act (confidence)",
                    "Why",
                    "ISO/IEC 42001",
                    "ISO/IEC 27090",
                    *REVIEW_COLS,
                ]
            )
            for s in nist["subcategories"]:
                eu = ", ".join(
                    f"{e['article']} ({e['confidence']})" for e in s["eu_ai_act"]
                )
                cells = _review_cells(rows[f"{key}:{s['id']}"])
                out.append(
                    f"| {s['id']} | {eu or 'none: attestation'} "
                    f"| {_cell(s['mapping_note'])} | {_ids(s['iso_42001'])} "
                    f"| {_ids(s['iso_27090'])} | {' | '.join(cells)} |"
                )
        elif key == "ISO_IEC_42001":
            out += _section(key, "ISO/IEC 42001:2023", rows)
            out += _table(
                [
                    "Id",
                    "Heading",
                    "EU AI Act",
                    "NIST AI RMF",
                    "ISO/IEC 27090",
                    *REVIEW_COLS,
                ]
            )
            for rid, row in rows.items():
                out.append(
                    f"| {_ids([rid])} | {_cell(row['title'])} "
                    f"| {_ids(row['eu_ai_act'])} | {_ids(row['nist_ai_rmf'])} "
                    f"| {_ids(row['iso_27090'])} | {' | '.join(_review_cells(row))} |"
                )
        elif key == "ISO_IEC_27090":
            out += _section(key, "ISO/IEC 27090:2026", rows)
            out += [
                "ISO/IEC 27001 Annex A and SOC 2 columns give control ids only, for teams"
                " that already run one of those programmes. Checks lists the output"
                " evaluators a row also reads and, marked probe, the file or code probes"
                " that add supporting evidence to an attestation.",
                "",
            ]
            out += _table(
                [
                    "Id",
                    "Heading",
                    "What we look for",
                    "Checks",
                    "EU AI Act",
                    "NIST AI RMF",
                    "ISO/IEC 42001",
                    "ISO/IEC 27001 Annex A",
                    "SOC 2",
                    *REVIEW_COLS,
                ]
            )
            for rid, row in rows.items():
                checks = [
                    s["ref"] + (" (probe)" if s["kind"] == "artifact" else "")
                    for s in row["sources"]
                    if s["kind"] in ("evaluator", "artifact")
                ]
                out.append(
                    f"| {_ids([rid])} | {_cell(row['title'])} | {_cell(row['note'])} "
                    f"| {_ids(checks)} | {_ids(row['eu_ai_act'])} "
                    f"| {_ids(row['nist_ai_rmf'])} | {_ids(row['iso_42001'])} "
                    f"| {_ids(row['iso_27001'])} | {_ids(row['soc2'])} "
                    f"| {' | '.join(_review_cells(row))} |"
                )
        else:
            is_27001 = key == "ISO_IEC_27001"
            with_42001 = any(row.get("iso_42001") for row in rows.values())
            cols = ["Id", "Heading", "What we look for", "Checks", "EU AI Act"]
            cols += ["Linked from"] if is_27001 else ["ISO/IEC 27001 Annex A"]
            cols += ["ISO/IEC 42001"] if with_42001 else []
            out += _section(
                key,
                load_pack_meta(key)["name"],
                rows,
                " Attestation-led: every row reads Unverified until attested.",
            )
            out += _table(cols + REVIEW_COLS)
            for rid, row in rows.items():
                checks = [
                    s["ref"] + " (probe)"
                    for s in row["sources"]
                    if s["kind"] == "artifact"
                ]
                last = (
                    ", ".join(linked_from.get(rid.split(":", 1)[1], [])) or "â€”"
                    if is_27001
                    else _ids(row.get("iso_27001", []))
                )
                cells = [_ids([rid]), _cell(row["title"]), _cell(row["note"])]
                cells += [_ids(checks), _ids(row["eu_ai_act"]), last]
                cells += [_ids(row.get("iso_42001", []))] if with_42001 else []
                out.append("| " + " | ".join(cells + _review_cells(row)) + " |")
    return "\n".join(out) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv[1:]:
        current = PAGE.read_text("utf-8") if PAGE.exists() else ""
        if current.replace("\r\n", "\n") != text:
            print(f"{PAGE} is stale: run scripts/generate_framework_mappings_doc.py")
            return 1
        return 0
    PAGE.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {PAGE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
