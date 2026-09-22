"""Control catalog — static obligation/article -> control metadata mapping.

Single source of truth for the default freshness (TTL) window and display
title of every control instance the ControlInstance model can represent.
Keyed by article reference string exactly as emitted by `gap_report.py` and
enumerated in `data/gap_article_map.json` (see that file for the article
universe). Bundled as static Python data — like the knowledge packs in
`opencomplai_core.knowledge` — rather than loaded from JSON, so there is no
I/O and no risk of a missing/corrupt file silently degrading the catalog.

A `default_ttl_days` of `None` means the article has no meaningful evidence
freshness window (e.g. a one-time declaration) and a control for it never
goes EVIDENCE_STALE from age alone.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ControlCatalogEntry:
    title: str
    default_ttl_days: int | None
    #: Mapped (not evaluated) ISO/IEC 42001:2023 clause for this article, from
    #: `data/framework_crosswalk.json` — None when the crosswalk has no row
    #: for this article. See `framework_crosswalk.py` for what "mapped" means.
    iso_42001_clause: str | None = None
    #: Mapped (not evaluated) NIST AI RMF 1.0 function/category for this
    #: article, from the same crosswalk. None when no row exists.
    nist_ai_rmf_subcategory: str | None = None


# Every article key emitted by gap_report.py / data/gap_article_map.json must
# appear here (extras are fine; omissions are not — see
# packages/core/tests/test_control_model.py::test_catalog_covers_every_gap_article).
CONTROL_CATALOG: dict[str, ControlCatalogEntry] = {
    "Art. 4": ControlCatalogEntry(
        title="AI literacy measures",
        default_ttl_days=180,
    ),
    "Art. 5": ControlCatalogEntry(
        title="Prohibited practices screening",
        default_ttl_days=180,
    ),
    "Art. 6": ControlCatalogEntry(
        title="High-risk classification",
        default_ttl_days=180,
    ),
    "Art. 9": ControlCatalogEntry(
        title="Risk management system",
        default_ttl_days=90,
    ),
    "Art. 10": ControlCatalogEntry(
        title="Data and data governance",
        default_ttl_days=90,
    ),
    "Art. 11": ControlCatalogEntry(
        title="Technical documentation",
        default_ttl_days=180,
    ),
    "Art. 12": ControlCatalogEntry(
        title="Record-keeping / logging",
        default_ttl_days=30,
    ),
    "Art. 13": ControlCatalogEntry(
        title="Transparency and provision of information to deployers",
        default_ttl_days=180,
    ),
    "Art. 14": ControlCatalogEntry(
        title="Human oversight",
        default_ttl_days=180,
    ),
    "Art. 15": ControlCatalogEntry(
        title="Accuracy, robustness and cybersecurity",
        default_ttl_days=180,
    ),
    "Art. 16": ControlCatalogEntry(
        title="Obligations of providers of high-risk AI systems",
        default_ttl_days=180,
    ),
    "Art. 17": ControlCatalogEntry(
        title="Quality management system",
        default_ttl_days=180,
    ),
    "Art. 24": ControlCatalogEntry(
        title="Distributor conformity obligations",
        default_ttl_days=180,
    ),
    "Art. 25": ControlCatalogEntry(
        title="Responsibilities along the AI value chain / substantial modification",
        default_ttl_days=180,
    ),
    "Art. 27": ControlCatalogEntry(
        title="Fundamental rights impact assessment",
        default_ttl_days=180,
    ),
    "Art. 43": ControlCatalogEntry(
        title="Conformity assessment",
        default_ttl_days=365,
    ),
    "Art. 47": ControlCatalogEntry(
        title="EU declaration of conformity",
        default_ttl_days=365,
    ),
    "Art. 48": ControlCatalogEntry(
        title="CE marking",
        default_ttl_days=365,
    ),
    "Art. 50": ControlCatalogEntry(
        title="Transparency obligations for certain AI systems",
        default_ttl_days=180,
    ),
    "Art. 53": ControlCatalogEntry(
        title="GPAI provider obligations",
        default_ttl_days=180,
    ),
    "Art. 55": ControlCatalogEntry(
        title="GPAI systemic-risk obligations",
        default_ttl_days=180,
    ),
}


def _with_crosswalk_references(
    catalog: dict[str, ControlCatalogEntry],
) -> dict[str, ControlCatalogEntry]:
    """Best-effort attach `data/framework_crosswalk.json` references.

    Mirrors the doc-generator's best-effort harmonised-standards lookup
    (`services/doc-generator/.../generator.py::_harmonised_standards_catalogue_ids`):
    a missing or malformed crosswalk degrades to no references rather than
    breaking every control_catalog consumer, since this module is imported
    widely (CLI, engine, tests) and must stay usable on its own.
    """
    try:
        from opencomplai_core.framework_crosswalk import get_crosswalk

        crosswalk = get_crosswalk()
    except Exception:
        return catalog

    enriched = dict(catalog)
    for article, entry in catalog.items():
        row = crosswalk.get(article)
        if row is not None:
            enriched[article] = replace(
                entry,
                iso_42001_clause=row.iso_42001_clause,
                nist_ai_rmf_subcategory=row.nist_ai_rmf_subcategory,
            )
    return enriched


# Applied as a post-processing step (rather than wrapping the literal above)
# so the article table stays a plain, easy-to-diff dict literal.
CONTROL_CATALOG = _with_crosswalk_references(CONTROL_CATALOG)


def get_catalog() -> dict[str, ControlCatalogEntry]:
    """Return the validated control catalog.

    Fails loud (raises ValueError) rather than returning a silently empty or
    malformed catalog, mirroring the knowledge-pack loading convention in
    `opencomplai_core.knowledge` where core must never run against an empty
    ruleset.
    """
    if not CONTROL_CATALOG:
        raise ValueError("control_catalog: CONTROL_CATALOG is empty")

    for article_ref, entry in CONTROL_CATALOG.items():
        if not isinstance(article_ref, str) or not article_ref.strip():
            raise ValueError(f"control_catalog: malformed article key {article_ref!r}")
        if not isinstance(entry, ControlCatalogEntry):
            raise ValueError(
                f"control_catalog: entry for {article_ref!r} is not a ControlCatalogEntry"
            )
        if not isinstance(entry.title, str) or not entry.title.strip():
            raise ValueError(
                f"control_catalog: entry for {article_ref!r} has an empty title"
            )
        if entry.default_ttl_days is not None and (
            not isinstance(entry.default_ttl_days, int) or entry.default_ttl_days <= 0
        ):
            raise ValueError(
                f"control_catalog: entry for {article_ref!r} has an invalid "
                f"default_ttl_days {entry.default_ttl_days!r}"
            )

    return CONTROL_CATALOG


# Alias matching the "loader" naming used in the epic task description.
load_control_catalog = get_catalog
