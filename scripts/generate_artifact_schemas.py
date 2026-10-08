#!/usr/bin/env python3
"""Generate the JSON Schemas for ScanStatusArtifact and GapReport into
packages/core/src/opencomplai_core/data/.

Run after editing ScanStatusArtifact, GapReport or any model they embed:
    python scripts/generate_artifact_schemas.py

packages/core/tests/test_artifact_schema_drift.py fails if the committed files
and the models disagree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "packages" / "core" / "src" / "opencomplai_core" / "data"


def main() -> None:
    sys.path.insert(0, str(REPO_ROOT / "packages" / "core" / "src"))
    from opencomplai_core.json_schemas import (
        build_artifact_schema,
        build_gap_report_schema,
    )

    for name, schema in (
        ("scan_status_artifact.schema.json", build_artifact_schema()),
        ("gap_report.schema.json", build_gap_report_schema()),
    ):
        path = DATA_DIR / name
        path.write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
