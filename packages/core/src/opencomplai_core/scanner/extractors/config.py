"""Config and endpoint hint extraction."""

from __future__ import annotations

import re
from pathlib import Path

from opencomplai_core.scanner.feature_types import ConfigRef
from opencomplai_core.scanner.inventory import RepoInventory

CONFIG_PATTERNS = [
    (re.compile(r"OPENAI_API_KEY", re.I), "config_key"),
    (re.compile(r"ANTHROPIC_API_KEY", re.I), "config_key"),
    (re.compile(r"AZURE_OPENAI_ENDPOINT", re.I), "config_key"),
    (re.compile(r"BEDROCK", re.I), "config_key"),
    (re.compile(r"VERTEX_AI", re.I), "config_key"),
    (re.compile(r"HF_TOKEN", re.I), "config_key"),
    (re.compile(r"api\.openai\.com", re.I), "endpoint"),
    (re.compile(r"api\.anthropic\.com", re.I), "endpoint"),
    (re.compile(r"bedrock-runtime", re.I), "endpoint"),
    (re.compile(r"aiplatform\.googleapis\.com", re.I), "endpoint"),
    (re.compile(r"generativelanguage\.googleapis\.com", re.I), "endpoint"),
    (re.compile(r"localhost:11434", re.I), "endpoint"),
]

TEXT_EXTENSIONS = {
    ".py",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".txt",
    ".md",
    ".ts",
    ".js",
}
ENV_FILENAMES = {".env", ".env.local", ".env.example"}


def extract_config_features(inventory: RepoInventory) -> list[ConfigRef]:
    results: list[ConfigRef] = []
    for entry in inventory.entries:
        if entry.is_binary:
            continue
        suffix = Path(entry.rel_path).suffix.lower()
        basename = Path(entry.rel_path).name.lower()
        if suffix not in TEXT_EXTENSIONS and basename not in ENV_FILENAMES:
            continue
        try:
            text = Path(entry.path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            for pattern, kind in CONFIG_PATTERNS:
                match = pattern.search(line)
                if match:
                    results.append(
                        ConfigRef(
                            key=match.group(0).lower(),
                            location=f"{entry.rel_path}:{i}",
                            scope=entry.scope,
                            kind=kind,
                        )
                    )
    return results
