"""MCP server inventory from .mcp.json / mcp.json (names only)."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_core.scanner.feature_types import McpServerRef
from opencomplai_core.scanner.inventory import RepoInventory

_FILENAMES = {".mcp.json", "mcp.json"}
_MAX_NAME = 80


def extract_mcp_servers(inventory: RepoInventory) -> list[McpServerRef]:
    refs: list[McpServerRef] = []
    for entry in inventory.entries:
        if entry.is_binary or Path(entry.rel_path).name.lower() not in _FILENAMES:
            continue
        try:
            data = json.loads(Path(entry.path).read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        servers = data.get("mcpServers") if isinstance(data, dict) else None
        if not isinstance(servers, dict):
            continue
        for name, cfg in servers.items():
            name = str(name)[:_MAX_NAME]
            cfg = cfg if isinstance(cfg, dict) else {}
            transport = (
                "stdio" if "command" in cfg else "remote" if "url" in cfg else "unknown"
            )
            refs.append(
                McpServerRef(
                    name=name,
                    location=f"{entry.rel_path}:mcpServers.{name}",
                    scope=entry.scope,
                    transport=transport,
                )
            )
    return sorted(refs, key=lambda r: (r.name, r.location))
