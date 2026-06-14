"""Content-addressed feature cache."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from opencomplai_core.scanner.constants import (
    EXTRACTOR_VERSION,
    SCOPE_CLASSIFIER_VERSION,
)


@dataclass
class FeatureCache:
    cache_dir: Path
    config_hash: str
    detector_versions: dict[str, str]
    hits: int = 0
    misses: int = 0
    invalidations: int = 0
    recomputes: int = 0
    _entries: dict[str, dict] = field(default_factory=dict)

    def cache_key(self, file_hash: str) -> str:
        detector_blob = json.dumps(self.detector_versions, sort_keys=True)
        raw = "|".join(
            [
                file_hash,
                EXTRACTOR_VERSION,
                detector_blob,
                self.config_hash,
                SCOPE_CLASSIFIER_VERSION,
            ]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, file_hash: str) -> dict | None:
        key = self.cache_key(file_hash)
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            self.misses += 1
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("cache_key") != key:
                self.invalidations += 1
                self.recomputes += 1
                return None
            self.hits += 1
            return data.get("features")
        except (OSError, json.JSONDecodeError):
            self.invalidations += 1
            self.recomputes += 1
            return None

    def put(self, file_hash: str, features: dict) -> None:
        key = self.cache_key(file_hash)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"{key}.json"
        payload = {"cache_key": key, "features": features}
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    def summary(self) -> dict[str, int]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "invalidations": self.invalidations,
            "recomputes": self.recomputes,
        }

    def record_summary(self, feature_summary: dict[str, int]) -> None:
        self._entries["last_summary"] = feature_summary


def config_hash_from_dict(config: dict) -> str:
    canonical = json.dumps(config, sort_keys=True)
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def default_detector_versions() -> dict[str, str]:
    from opencomplai_core.scanner.registry import DETECTOR_REGISTRY

    return {d.detector_id: d.detector_version for d in DETECTOR_REGISTRY}
