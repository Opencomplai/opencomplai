#!/usr/bin/env python3
"""Generate docs/src/concepts/eu-ai-act-principles.md from the same data-driven
mapping used by `opencomplai gaps`'s principle_summary (packages/core's
eu_ai_act_principles.json + gap_article_map.json), so the docs page and the CLI
output never drift out of sync.

Run manually after editing either data file:
    python scripts/generate_principle_docs.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_DATA = REPO_ROOT / "packages" / "core" / "src" / "opencomplai_core" / "data"
OUTPUT_PATH = REPO_ROOT / "docs" / "src" / "concepts" / "eu-ai-act-principles.md"


def _load_json(name: str) -> dict:
    return json.loads((CORE_DATA / name).read_text(encoding="utf-8"))


def _build_article_to_sources(gap_article_map: dict) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for article, config in gap_article_map.items():
        sources = config.get("sources", [])
        result[article] = [f"`{s['kind']}:{s['ref']}`" for s in sources] or ["_no automated source_"]
    return result


def render() -> str:
    principles_data = _load_json("eu_ai_act_principles.json")
    gap_article_map = _load_json("gap_article_map.json")
    article_sources = _build_article_to_sources(gap_article_map)

    lines = [
        "# Control Codes → Principles → Articles",
        "",
        "This page maps every EU AI Act article Opencomplai tracks to the 6 EU Trustworthy AI",
        "principles (per the EU High-Level Expert Group on AI), and to the rule/obligation/scan/",
        "evaluator source that produces its `opencomplai gaps` status.",
        "",
        "**This page is generated** from"
        " `packages/core/src/opencomplai_core/data/eu_ai_act_principles.json` and"
        " `packages/core/src/opencomplai_core/data/gap_article_map.json` — the exact same data"
        " `opencomplai gaps`'s `principle_summary` output reads, so this page and the CLI can",
        "never drift out of sync. Regenerate with `python scripts/generate_principle_docs.py`",
        "after editing either data file.",
        "",
        "---",
        "",
    ]

    for principle_id, config in principles_data["principles"].items():
        lines.append(f"## {config['title']}")
        lines.append("")
        lines.append(f"`{principle_id}`")
        lines.append("")
        lines.append("| Article | Source(s) |")
        lines.append("|---|---|")
        for article in config["articles"]:
            sources = ", ".join(article_sources.get(article, ["_no automated source_"]))
            lines.append(f"| {article} | {sources} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "See [Control Codes Reference](control-codes.md) for what triggers each rule code, and"
        " run `opencomplai gaps` to see this same mapping applied to your own system."
    )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    content = render()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
