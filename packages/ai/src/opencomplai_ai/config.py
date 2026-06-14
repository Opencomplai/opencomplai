"""Read/write ~/.opencomplai/ai-config.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

from opencomplai_ai.models import MODEL_CATALOG

_CONFIG_DIR = Path.home() / ".opencomplai"
_AI_CONFIG_FILE = _CONFIG_DIR / "ai-config.yaml"
_DEFAULT_MODEL = "qwen2.5-coder-1.5b"


def get_active_model() -> str:
    if not _AI_CONFIG_FILE.exists():
        return _DEFAULT_MODEL
    try:
        data = yaml.safe_load(_AI_CONFIG_FILE.read_text(encoding="utf-8")) or {}
        model_id = data.get("model_id", _DEFAULT_MODEL)
        if model_id in MODEL_CATALOG:
            return model_id
    except Exception:
        pass
    return _DEFAULT_MODEL


def set_active_model(model_id: str) -> None:
    if model_id not in MODEL_CATALOG:
        raise ValueError(
            f"Unknown model '{model_id}'. Valid options: {', '.join(MODEL_CATALOG)}"
        )
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if _AI_CONFIG_FILE.exists():
        try:
            existing = yaml.safe_load(_AI_CONFIG_FILE.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    existing["model_id"] = model_id
    _AI_CONFIG_FILE.write_text(yaml.safe_dump(existing), encoding="utf-8")


def get_cache_dir() -> Path:
    return Path.home() / ".cache" / "opencomplai" / "models"
