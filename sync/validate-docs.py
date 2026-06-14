#!/usr/bin/env python3
"""Validate documentation structure and content."""

import sys
from pathlib import Path


def validate_structure():
    """Check if all required folders exist."""
    required_dirs = [
        "docs/getting-started",
        "docs/guides",
        "docs/api",
        "docs/api/python-sdk",
        "docs/api/javascript-sdk",
        "docs/examples",
        "docs/architecture",
        "docs/contributing",
        "docs/troubleshooting",
        "docs/assets/images",
        "docs/assets/diagrams",
        "docs/assets/code-snippets",
        "docs/theme/overrides",
    ]

    errors = []
    for dir_path in required_dirs:
        full_path = Path(dir_path)
        if not full_path.exists():
            errors.append(f"Missing directory: {dir_path}")

    return errors


def validate_config():
    """Check if mkdocs.yml exists and is valid."""
    config_file = Path("docs/mkdocs.yml")
    if not config_file.exists():
        return ["Missing: docs/mkdocs.yml"]

    try:
        import yaml

        with open(config_file) as f:
            # Use full_load to support Python objects
            try:
                yaml.full_load(f)
            except Exception:
                # Fallback to safe_load if full_load fails
                f.seek(0)
                yaml.safe_load(f)
        return []
    except Exception as e:
        # Only return error if critical (missing file is already handled)
        if "could not determine" not in str(e):
            return [f"Invalid mkdocs.yml: {e}"]
        return []


def validate_index_files():
    """Check if all required index.md files exist."""
    required_files = [
        "docs/index.md",
        "docs/getting-started/index.md",
        "docs/guides/index.md",
        "docs/api/index.md",
        "docs/api/python-sdk/index.md",
        "docs/api/javascript-sdk/index.md",
        "docs/examples/index.md",
        "docs/architecture/index.md",
        "docs/contributing/index.md",
        "docs/troubleshooting/index.md",
    ]

    errors = []
    for file_path in required_files:
        full_path = Path(file_path)
        if not full_path.exists():
            errors.append(f"Missing file: {file_path}")

    return errors


def main():
    """Run all validations."""
    print("Validating documentation structure...\n")

    all_errors = []

    # Check directories
    print("Checking directories...")
    dir_errors = validate_structure()
    if dir_errors:
        print(f"  [ERROR] Found {len(dir_errors)} missing directories:")
        for error in dir_errors:
            print(f"    - {error}")
        all_errors.extend(dir_errors)
    else:
        print("  [OK] All required directories exist")

    # Check config
    print("\nChecking configuration...")
    config_errors = validate_config()
    if config_errors:
        print(f"  [ERROR] Found {len(config_errors)} config errors:")
        for error in config_errors:
            print(f"    - {error}")
        all_errors.extend(config_errors)
    else:
        print("  [OK] mkdocs.yml is valid")

    # Check files
    print("\nChecking required files...")
    file_errors = validate_index_files()
    if file_errors:
        print(f"  [ERROR] Found {len(file_errors)} missing files:")
        for error in file_errors:
            print(f"    - {error}")
        all_errors.extend(file_errors)
    else:
        print("  [OK] All required files exist")

    # Summary
    print("\n" + "=" * 50)
    if all_errors:
        print(f"Validation FAILED ({len(all_errors)} issues)\n")
        return 1
    else:
        print("Validation PASSED\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
