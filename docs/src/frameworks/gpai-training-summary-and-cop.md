# GPAI training summary and Code of Practice map

This is offline reference data for providers of general-purpose AI (GPAI) models. It has
two parts: a template for the publicly available summary of training content
(Art. 53(1)(d)), and a map from the three GPAI Code of Practice chapters to the
Art. 53 and Art. 55 obligations they address. It is not used by `gaps`, `check` or
the dossier, and nothing in it is uploaded.

!!! warning "Draft, not checked against the primary texts"
    Every row was written from recollection and has not been checked against the
    published texts. Every row has `confidence: low` and `needs_founder_review: true`,
    and none carries a source URL. The Code of Practice is voluntary: adherence is not
    a legal determination of compliance, and this tool grants no presumption of
    conformity.

## Training-content summary sections

The template renders to markdown with a blank provider entry under each section.

| Id | Section |
|---|---|
| `ts_general` | General information |
| `ts_public_datasets` | Publicly available datasets |
| `ts_private_datasets` | Private datasets |
| `ts_crawled_scraped` | Crawled and scraped data |
| `ts_user_data` | User data |
| `ts_synthetic_data` | Synthetic data |
| `ts_other_sources` | Other data sources |
| `ts_rights_reservation_opt_out` | Rights reservations and opt-outs |
| `ts_illegal_content_removal` | Removal of illegal content |
| `ts_other_processing` | Other data processing aspects |

## Code of Practice chapters

| Id | Chapter | Obligations | Applies to |
|---|---|---|---|
| `cop_transparency` | Transparency | Art. 53(1)(a), Art. 53(1)(b) | All GPAI providers |
| `cop_copyright` | Copyright | Art. 53(1)(c) | All GPAI providers |
| `cop_safety_security` | Safety and security | Art. 55 | Systemic-risk models only |

The Annex XI and XII documentation checklist is described under
[`recommend`](../cli/recommend.md).

For a recorded GPAI checker session, an Art. 53 row in `opencomplai recommend` writes
`art53-gpai_copyright_policy.md` and `art53-gpai_training_summary.md` (the summary template
rendered as a draft). An Art. 55 row writes neither.

## Validation

The data file is loaded by a fail-loud loader: a missing file, invalid JSON, a missing
key, a duplicate id, or a row without `needs_founder_review: true` raises an error
instead of returning a partial pack.
