#!/usr/bin/env python3
"""Write docs/src/frameworks/mappings.md from the framework data files.

    python scripts/generate_framework_mappings_doc.py          # rewrite the page
    python scripts/generate_framework_mappings_doc.py --check  # exit 1 if stale

packages/core/tests/test_framework_mappings.py runs the --check form.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "packages" / "core" / "src" / "opencomplai_core" / "data"
PAGE = REPO_ROOT / "docs" / "src" / "frameworks" / "mappings.md"

# Further native packs: key, data file, section heading. A pack whose data file is absent is
# not registered and gets no section.
MORE_PACKS = [
    ("ISO_IEC_27001", "iso_27001.json", "ISO/IEC 27001:2022"),
    ("SOC_2", "soc_2.json", "SOC 2 Trust Services Criteria"),
    ("NIS2", "nis2.json", "NIS2 Directive (EU) 2022/2555"),
    ("DORA", "dora.json", "DORA Regulation (EU) 2022/2554"),
    ("EBA", "eba.json", "EBA Guidelines"),
    ("EIOPA_AI", "eiopa_ai.json", "EIOPA Opinion on AI governance and risk management"),
    ("GDPR", "gdpr.json", "GDPR Regulation (EU) 2016/679"),
    ("CRA", "cra.json", "Cyber Resilience Act Regulation (EU) 2024/2847"),
    ("ETSI_EN_304_223", "etsi_en_304_223.json", "ETSI EN 304 223"),
    ("ISO_IEC_42005", "iso_42005.json", "ISO/IEC 42005:2025"),
    ("ISO_IEC_23894", "iso_23894.json", "ISO/IEC 23894:2023"),
]

HEADER = """# Framework mappings

How each requirement of NIST AI RMF 1.0, ISO/IEC 42001:2023 and ISO/IEC 27090:2026
relates to the EU AI Act and to the other two frameworks, followed by the further native
packs and their links to the EU AI Act, ISO/IEC 27001 and ISO/IEC 42001. This page is
generated from the data files in `packages/core/src/opencomplai_core/data/`; do not edit
it by hand.

- **NIST AI RMF:** the EU AI Act column decides the verdict. The evidence of those
  articles is re-projected onto the subcategory (worst status, lowest confidence). A
  subcategory with no article takes a provider attestation instead.
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


def render() -> str:
    nist = json.loads((DATA / "nist_ai_rmf_subcategories.json").read_text("utf-8"))
    iso42 = json.loads((DATA / "iso_42001.json").read_text("utf-8"))
    iso27 = json.loads((DATA / "iso_27090.json").read_text("utf-8"))
    out = [HEADER]

    out += [
        "## NIST AI RMF 1.0",
        "",
        "| Subcategory | EU AI Act (confidence) | Why | ISO/IEC 42001 | ISO/IEC 27090 |",
        "|---|---|---|---|---|",
    ]
    for s in nist["subcategories"]:
        eu = ", ".join(f"{e['article']} ({e['confidence']})" for e in s["eu_ai_act"])
        out.append(
            f"| {s['id']} | {eu or 'none: attestation'} | {_cell(s['mapping_note'])} "
            f"| {_ids(s['iso_42001'])} | {_ids(s['iso_27090'])} |"
        )

    out += [
        "",
        "## ISO/IEC 42001:2023",
        "",
        "| Id | Heading | EU AI Act | NIST AI RMF | ISO/IEC 27090 |",
        "|---|---|---|---|---|",
    ]
    for rid, row in iso42.items():
        out.append(
            f"| {_ids([rid])} | {_cell(row['title'])} | {_ids(row['eu_ai_act'])} "
            f"| {_ids(row['nist_ai_rmf'])} | {_ids(row['iso_27090'])} |"
        )

    out += [
        "",
        "## ISO/IEC 27090:2026",
        "",
        "ISO/IEC 27001 Annex A and SOC 2 columns give control ids only, for teams that"
        " already run one of those programmes. Checks lists the output evaluators a row"
        " also reads and, marked probe, the file or code probes that add supporting"
        " evidence to an attestation.",
        "",
        "| Id | Heading | What we look for | Checks | EU AI Act | NIST AI RMF "
        "| ISO/IEC 42001 | ISO/IEC 27001 Annex A | SOC 2 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for rid, row in iso27.items():
        checks = [
            s["ref"] + (" (probe)" if s["kind"] == "artifact" else "")
            for s in row["sources"]
            if s["kind"] in ("evaluator", "artifact")
        ]
        out.append(
            f"| {_ids([rid])} | {_cell(row['title'])} | {_cell(row['note'])} "
            f"| {_ids(checks)} | {_ids(row['eu_ai_act'])} "
            f"| {_ids(row['nist_ai_rmf'])} | {_ids(row['iso_42001'])} "
            f"| {_ids(row['iso_27001'])} | {_ids(row['soc2'])} |"
        )

    packs = [
        (key, heading, json.loads((DATA / fname).read_text("utf-8")))
        for key, fname, heading in MORE_PACKS
        if (DATA / fname).exists()
    ]
    # Which frameworks link to each ISO/IEC 27001 Annex A control (ISO/IEC 27090 included).
    linked_from: dict[str, list[str]] = {}
    for key, _, rows in [("ISO_IEC_27090", "", iso27), *packs]:
        for row in rows.values():
            for control in row.get("iso_27001", []):
                names = linked_from.setdefault(control, [])
                if key not in names:
                    names.append(key)
    for key, heading, rows in packs:
        is_27001 = key == "ISO_IEC_27001"
        with_42001 = any(row.get("iso_42001") for row in rows.values())
        cols = ["Id", "Heading", "What we look for", "Checks", "EU AI Act"]
        cols += ["Linked from"] if is_27001 else ["ISO/IEC 27001 Annex A"]
        cols += ["ISO/IEC 42001"] if with_42001 else []
        out += [
            "",
            f"## {heading}",
            "",
            f"Key `{key}`. Attestation-led: every row reads Unverified until attested.",
            "",
            "| " + " | ".join(cols) + " |",
            "|" + "---|" * len(cols),
        ]
        for rid, row in rows.items():
            checks = [
                s["ref"] + " (probe)" for s in row["sources"] if s["kind"] == "artifact"
            ]
            last = (
                ", ".join(linked_from.get(rid.split(":", 1)[1], [])) or "—"
                if is_27001
                else _ids(row.get("iso_27001", []))
            )
            cells = [_ids([rid]), _cell(row["title"]), _cell(row["note"]), _ids(checks)]
            cells += [_ids(row["eu_ai_act"]), last]
            cells += [_ids(row.get("iso_42001", []))] if with_42001 else []
            out.append("| " + " | ".join(cells) + " |")
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
