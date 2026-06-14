"""Model and vector artifact metadata extraction."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.scanner.feature_types import ArtifactRef
from opencomplai_core.scanner.inventory import MODEL_EXTENSIONS, RepoInventory


def extract_artifacts(inventory: RepoInventory) -> list[ArtifactRef]:
    results: list[ArtifactRef] = []
    for entry in inventory.entries:
        ext = Path(entry.rel_path).suffix.lower()
        if ext in MODEL_EXTENSIONS:
            results.append(
                ArtifactRef(
                    path=entry.rel_path,
                    location=f"{entry.rel_path}:1",
                    scope=entry.scope,
                    extension=ext,
                )
            )
    return results
