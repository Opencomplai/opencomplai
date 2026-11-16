"""Canonical text form of a pack data file."""

import json
import re


def dump(obj) -> str:
    """indent=2 JSON with arrays of plain strings kept on one line."""
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    text = re.sub(
        r"\[\s+((?:\"[^\"\n]*\",?\s+)+)\]",
        lambda m: "[" + ", ".join(re.findall(r"\"[^\"\n]*\"", m.group(1))) + "]",
        text,
    )
    return text + "\n"
