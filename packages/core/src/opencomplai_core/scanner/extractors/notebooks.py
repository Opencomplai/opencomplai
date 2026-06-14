"""Notebook cell metadata extraction (redacted token summaries)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from opencomplai_core.scanner.feature_types import NotebookRef
from opencomplai_core.scanner.inventory import RepoInventory

TOKEN_PATTERN = re.compile(
    r"\b(openai|anthropic|langchain|torch|tensorflow|transformers|embedding|prompt)\b",
    re.I,
)


def extract_notebook_features(inventory: RepoInventory) -> list[NotebookRef]:
    results: list[NotebookRef] = []
    max_cells = inventory.limits.max_notebook_cells
    for entry in inventory.entries:
        if entry.language != "notebook":
            continue
        if entry.is_binary:
            continue
        try:
            data = json.loads(
                Path(entry.path).read_text(encoding="utf-8", errors="replace")
            )
        except (OSError, json.JSONDecodeError):
            continue
        cells = data.get("cells", [])
        if max_cells > 0:
            cells = cells[:max_cells]
        for idx, cell in enumerate(cells):
            source = cell.get("source", "")
            if isinstance(source, list):
                source = "".join(source)
            labels = sorted(
                {m.group(0).lower() for m in TOKEN_PATTERN.finditer(source)}
            )
            if labels:
                results.append(
                    NotebookRef(
                        cell_index=idx,
                        location=f"{entry.rel_path}:{idx + 1}",
                        scope=entry.scope,
                        token_labels=labels,
                    )
                )
    return results
