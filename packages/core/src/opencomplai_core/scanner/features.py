"""FeatureStore extraction orchestration."""

from __future__ import annotations

from opencomplai_core.scanner.cache import FeatureCache
from opencomplai_core.scanner.extractors.artifacts import extract_artifacts
from opencomplai_core.scanner.extractors.ast import (
    extract_ast_callsites,
    extract_ast_imports,
)
from opencomplai_core.scanner.extractors.config import extract_config_features
from opencomplai_core.scanner.extractors.manifests import extract_manifest_features
from opencomplai_core.scanner.extractors.notebooks import extract_notebook_features
from opencomplai_core.scanner.feature_types import (
    FeatureStore,
    ScanConfig,
    ScanProgressCallback,
)
from opencomplai_core.scanner.inventory import RepoInventory

__all__ = [
    "ArtifactRef",
    "CallsiteRef",
    "ConfigRef",
    "FeatureStore",
    "ImportRef",
    "ManifestPackage",
    "NotebookRef",
    "ScanConfig",
    "extract_features",
]

from opencomplai_core.scanner.feature_types import (
    ArtifactRef,
    CallsiteRef,
    ConfigRef,
    ImportRef,
    ManifestPackage,
    NotebookRef,
)


def extract_features(
    inventory: RepoInventory,
    config: ScanConfig | None = None,
    cache: FeatureCache | None = None,
    progress_cb: ScanProgressCallback | None = None,
) -> FeatureStore:
    config = config or ScanConfig()
    store = FeatureStore(repo_root=inventory.repo_root)

    if progress_cb:
        progress_cb.on_phase("extract", 6)

    store.packages.extend(extract_manifest_features(inventory))
    if progress_cb:
        progress_cb.on_step("extract", 1, "manifests")
    store.imports.extend(extract_ast_imports(inventory))
    if progress_cb:
        progress_cb.on_step("extract", 2, "ast_imports")
    store.callsites.extend(extract_ast_callsites(inventory))
    if progress_cb:
        progress_cb.on_step("extract", 3, "ast_callsites")
    store.configs.extend(extract_config_features(inventory))
    if progress_cb:
        progress_cb.on_step("extract", 4, "config")
    store.artifacts.extend(extract_artifacts(inventory))
    if progress_cb:
        progress_cb.on_step("extract", 5, "artifacts")
    store.notebooks.extend(extract_notebook_features(inventory))
    if progress_cb:
        progress_cb.on_step("extract", 6, "notebooks")

    store.summary = {
        "packages": len(store.packages),
        "imports": len(store.imports),
        "callsites": len(store.callsites),
        "configs": len(store.configs),
        "artifacts": len(store.artifacts),
        "notebooks": len(store.notebooks),
    }
    if cache is not None and config.use_cache:
        cache.record_summary(store.summary)
    return store
