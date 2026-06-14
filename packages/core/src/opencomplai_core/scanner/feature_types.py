"""Typed feature records — no extractor imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from opencomplai_core.models import EvidenceScope


@runtime_checkable
class ScanProgressCallback(Protocol):
    def on_phase(self, phase: str, total: int) -> None: ...

    def on_step(self, phase: str, current: int, label: str = "") -> None: ...

    def on_done(
        self,
        elapsed_s: float,
        file_count: int,
        skip_reasons: dict[str, int] | None = None,
        limits_hit: list[str] | None = None,
    ) -> None: ...


@dataclass
class ManifestPackage:
    name: str
    location: str
    scope: EvidenceScope
    source: str


@dataclass
class ImportRef:
    module: str
    location: str
    scope: EvidenceScope


@dataclass
class CallsiteRef:
    name: str
    location: str
    scope: EvidenceScope


@dataclass
class ConfigRef:
    key: str
    location: str
    scope: EvidenceScope
    kind: str


@dataclass
class ArtifactRef:
    path: str
    location: str
    scope: EvidenceScope
    extension: str


@dataclass
class NotebookRef:
    cell_index: int
    location: str
    scope: EvidenceScope
    token_labels: list[str]


@dataclass
class SemanticRef:
    term: str
    location: str
    scope: EvidenceScope
    context: str


@dataclass
class FeatureStore:
    repo_root: Path
    packages: list[ManifestPackage] = field(default_factory=list)
    imports: list[ImportRef] = field(default_factory=list)
    callsites: list[CallsiteRef] = field(default_factory=list)
    configs: list[ConfigRef] = field(default_factory=list)
    artifacts: list[ArtifactRef] = field(default_factory=list)
    notebooks: list[NotebookRef] = field(default_factory=list)
    semantics: list[SemanticRef] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


@dataclass
class ScanConfig:
    excludes: frozenset[str] = frozenset()  # deprecated: use .ocignore patterns
    ocignore_path: Path | None = None
    cache_dir: Path | None = None
    use_cache: bool = True
