#!/usr/bin/env python3
"""Check for broken links in documentation."""

import re
from pathlib import Path


def check_internal_links():
    """Validate internal markdown links."""
    docs_dir = Path("docs")
    errors = []

    for md_file in docs_dir.rglob("*.md"):
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
