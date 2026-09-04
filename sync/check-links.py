#!/usr/bin/env python3
"""Check for broken links in documentation."""

import re
from pathlib import Path

#: Directories whose markdown we do not own and must not gate CI on. The docs
#: build runs `npm ci` in docs/checker-widget before the link check, so without
#: this the walk picks up vendored READMEs — ~24 of them carry relative links
#: to files not shipped in the published package, which is not our defect.
_EXCLUDED_DIRS = frozenset({"node_modules", ".venv", "site", "__pycache__"})


def _is_excluded(path: Path) -> bool:
    return any(part in _EXCLUDED_DIRS for part in path.parts)


def check_internal_links():
    """Validate internal markdown links."""
    docs_dir = Path("docs")
    errors = []

    for md_file in docs_dir.rglob("*.md"):
        if _is_excluded(md_file):
            continue
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Find all markdown links: [text](path)
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)

        for text, link in links:
            # Skip external links and data URIs
            if link.startswith(("http://", "https://", "#", "data:", "mailto:")):
                continue

            # Skip anchors
            if link.startswith("#"):
                continue

            # Strip anchor fragment before resolving path
            link_path = link.split("#")[0]
            if not link_path:
                continue

            # Resolve relative path
            target = (md_file.parent / link_path).resolve()

            # Check if file exists
            if not target.exists():
                errors.append(f"{md_file}: broken link [{text}]({link_path})")

    return errors


def main():
    """Run link checks."""
    print("Checking internal links...")
    errors = check_internal_links()

    if errors:
        print(f"[ERROR] Found {len(errors)} broken links:\n")
        for error in errors:
            print(f"  - {error}")
        return 1
    else:
        print("[OK] All internal links are valid!")
        return 0


if __name__ == "__main__":
    exit(main())
