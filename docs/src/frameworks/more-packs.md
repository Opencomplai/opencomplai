# More framework packs

Besides the EU AI Act, NIST AI RMF, ISO/IEC 42001 and ISO/IEC 27090, Opencomplai carries eleven more
frameworks as native, attestation-led packs. They work like ISO/IEC 42001: one row per requirement,
article, control or criterion; every row takes a provider attestation and reads **Unverified** until you
record one. A few rows also look for supporting evidence in the repository, which never lowers a row and
never makes an unattested row Met.

None of this is an audit, a certification, a SOC 2 report or a legal assessment. Every row is the
project's own short description at low confidence, flagged for founder review. For copyrighted standards
(ISO, AICPA, ETSI) the rows carry ids and headings only, never the standard's text.

## The packs

| Framework | Key | Rows | Source the ids follow | Supporting evidence |
|---|---|---|---|---|
| ISO/IEC 27001:2022 (incl. Amd 1:2024) | `ISO_IEC_27001` | 118: clauses 4.1-10.2 and the 93 Annex A controls | Contents lists of ISO/IEC 27001:2022 and ISO/IEC 27002:2022 | SBOM or model pins (A.5.21); event logs (A.8.15, A.8.16) |
| SOC 2 Trust Services Criteria (2017, points of focus revised 2022) | `SOC_2` | 61: CC1-CC9, A1, C1, PI1, P1-P8 | Criterion ids as AICPA numbers them, checked against public outlines | event logs (CC7.2) |
| NIS2, Directive (EU) 2022/2555 | `NIS2` | 21: Arts 20, 21 and 23 | The Directive; ISO/IEC 27001 links mostly from ENISA's NIS2 technical implementation guidance mapping | none |
| DORA, Regulation (EU) 2022/2554 | `DORA` | 37: Arts 5-14, 16-19, 24-30, 45 | The Regulation as published | event logs (Art. 10); red-team report (Arts 24, 25) |
| EBA guidelines | `EBA` | 25: GL/2019/04 (3.8), GL/2019/02 (outsourcing), GL/2020/06 (loan origination) | The guidelines; GL/2019/04 as amended by GL/2025/02 | none |
| EIOPA Opinion on AI governance and risk management (Aug 2025) | `EIOPA_AI` | 8 topics | The Opinion's own paragraph ranges | none |
| GDPR, Regulation (EU) 2016/679 | `GDPR` | 21 articles that matter for an AI system | The Regulation as published | none |
| Cyber Resilience Act, Regulation (EU) 2024/2847 | `CRA` | 63: Art. 13, 14, 28, 30 and Annexes I, II, VII | The Regulation as published | SBOM or pins (Annex I Part II (1)); threat model (Art. 13(2)) |
| ETSI EN 304 223 V2.1.1 (2025-12) | `ETSI_EN_304_223` | 72 provisions under 13 principles | The EN's provision numbers | red-team report, threat model, SBOM or pins on the matching provisions |
| ISO/IEC 42005:2025 (AI system impact assessment) | `ISO_IEC_42005` | 20 clauses | Contents list of the published standard | none |
| ISO/IEC 23894:2023 (AI risk management guidance) | `ISO_IEC_23894` | 23 clauses | Contents list of the published standard | none |

Every row lists the EU AI Act articles it relates to. The security and operational frameworks also list
ISO/IEC 27001 Annex A controls, and ISO/IEC 42005 and ISO/IEC 23894 list ISO/IEC 42001 rows. Links are
the project's own judgement unless the table names an official mapping. See
[Framework mappings](mappings.md) for every row and link, including which frameworks point at each
ISO/IEC 27001 control.

## Using a pack

Target it like any other framework and record attestations under `framework_inputs`:

```json
{
  "compliance_targets": ["EU_AI_ACT", "GDPR", "ISO_IEC_27001"],
  "framework_inputs": {
    "GDPR": {
      "attested": {
        "GDPR:Art. 35": {
          "statement": "DPIA for the support assistant approved; see records/dpia-2026.pdf.",
          "attested_by": "dpo@example.com",
          "attested_at": "2026-11-03"
        }
      }
    }
  }
}
```

`opencomplai gaps --target GDPR` prints the table; `check --with-gaps` writes it into `framework_reports`;
`check --gate GDPR` gates CI on its Missing rows. An Unverified row never fails a gate. A row that does
not apply to you goes under `framework_inputs.<KEY>.excluded` with your reason.

## What to keep in mind

- **Scope.** The rows cover what each text asks of an organisation or product that builds or runs an AI
  system. They do not replace the full text, an auditor, a supervisor or legal advice.
- **SOC 2.** Rows follow the criteria; attesting them is not a SOC 2 examination, which only a licensed
  CPA firm performs.
- **DORA and EBA.** These packs sit beside the older mapped-only citations: `gaps --map-to DORA|EBA` still
  adds one citation per EU AI Act article to the EU table (see [Mapped regimes](../concepts/mapped-regimes.md)).
  Since DORA applies, the EBA ICT guidelines (GL/2019/04) keep only section 3.8, and the outsourcing
  guidelines (GL/2019/02) are due to be replaced; the rows say so.
- **EIOPA.** The Opinion addresses AI systems that are neither prohibited nor high-risk under the AI Act.
- **CRA.** Every row names when its duty starts: reporting under Art. 14 from 11 September 2026, the rest
  from 11 December 2027.
- **AI Act changes.** Regulation (EU) 2026/1744 moved the special-category basis for bias detection from
  Art. 10(5) to a new Art. 4a and reworded Art. 27(4); links point at the articles as they stand.
