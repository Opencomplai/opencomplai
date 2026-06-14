"""Scanner cache — key composition and corruption fail-closed."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.scanner.cache import FeatureCache, config_hash_from_dict


def test_cache_key_changes_with_config_hash(tmp_path: Path):
    cache = FeatureCache(
        cache_dir=tmp_path,
        config_hash="sha256:a",
        detector_versions={"DET_AI_DEP_V1": "1.0.0"},
    )
    k1 = cache.cache_key("filehash1")
    cache2 = FeatureCache(
        cache_dir=tmp_path,
        config_hash="sha256:b",
        detector_versions={"DET_AI_DEP_V1": "1.0.0"},
    )
    k2 = cache2.cache_key("filehash1")
    assert k1 != k2


def test_corrupted_cache_recomputes(tmp_path: Path):
    cache = FeatureCache(
        cache_dir=tmp_path,
        config_hash=config_hash_from_dict({"use_cache": True}),
        detector_versions={"DET_AI_DEP_V1": "1.0.0"},
    )
    key = cache.cache_key("abc")
    path = tmp_path / f"{key}.json"
    path.write_text('{"cache_key": "wrong", "features": {}}', encoding="utf-8")
    assert cache.get("abc") is None
    assert cache.invalidations >= 1


def test_cache_put_and_get_round_trip(tmp_path: Path):
    cache = FeatureCache(
        cache_dir=tmp_path,
        config_hash=config_hash_from_dict({}),
        detector_versions={"DET_AI_DEP_V1": "1.0.0"},
    )
    cache.put("file1", {"imports": 3})
    assert cache.get("file1") == {"imports": 3}
    assert cache.hits == 1
