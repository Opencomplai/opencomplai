#!/usr/bin/env python3
"""Generate packages/core/src/opencomplai_core/data/annex_iv_dossier.schema.json
through the `opencomplai_core.json_schemas` builder, so the committed JSON Schema never
drifts from the pydantic model it describes.

Run manually after editing any AnnexIVDossier/AnnexIVSection* model in
packages/core/src/opencomplai_core/dossier.py:
    python scripts/generate_dossier_schema.py

packages/core/tests/test_dossier_schema_drift.py fails loud if the committed
file and a fresh builder call ever disagree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = (
    REPO_ROOT
    / "packages"
    / "core"
    / "src"
    / "opencomplai_core"
    / "data"
    / "annex_iv_dossier.schema.json"
)


def main() -> None:
    sys.path.insert(0, str(REPO_ROOT / "packages" / "core" / "src"))
    from opencomplai_core.json_schemas import build_dossier_schema

    schema = build_dossier_schema()
    OUTPUT_PATH.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
