"""
Offline reader for the JSONL file audit sink of an agent runtime governance toolkit.

Read-only side tool: stdlib only, never imports the vendor library, opens no
socket, has no clock, and is never imported by `check`, `gaps` or any gate. The
importer normalises records and labels them honestly; the label is "format-valid,
not verified" because the sink's integrity hash is unkeyed unless the operator
holds a key, and rotated files restart their chain, so nothing here proves
completeness or retention. Evidence from this source is capped at PARTIAL.

The product is a public preview and the real field names are UNVERIFIED (only
`content_hash`, `previous_hash`, `policy_decision`, `matched_rule` and a `data`
object are grounded), so the preset lists several candidate keys per field and
`--map field=dotted.path` overrides it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from opencomplai_core.models import GapStatus

# E-15: preset data carries source, confidence and needs_founder_review.
AGT_PRESET: dict = {
    "source": "internal AGT memo: file sink JSONL; field names beyond "
    "content_hash/previous_hash/policy_decision/matched_rule/data unverified",
    "confidence": "low",
    "needs_founder_review": True,
    "fields": {
        "ts": ["timestamp", "ts", "time", "data.timestamp"],
        "agent_id": ["agent_id", "agent.id", "data.agent_id", "agent"],
        "action": ["action", "tool", "data.action", "data.tool"],
        "decision": ["policy_decision", "decision", "data.policy_decision"],
        "rule": ["matched_rule", "rule", "data.matched_rule"],
        "told": ["data.prompt", "data.intent", "data.input", "prompt", "input"],
        "approver": ["data.approver", "approver", "approved_by"],
    },
}
INTEGRITY_LABEL = "format-valid, not verified"
STATUS_CAP = GapStatus.PARTIAL
CAVEATS_META = {
    "source": "internal AGT memo (integrity hash unkeyed, no signed head)",
    "confidence": "low",
    "needs_founder_review": True,
}
CAVEATS: tuple[str, ...] = (
    "Integrity is not verified: the sink's hash is unkeyed unless the operator holds a key.",
    "Completeness and retention are not claimed: rotated files restart their chain and there is no signed head.",
    "The record format is a preview; field names may need --map.",
    "The record author may be the operator being assessed.",
)
_MAX = 500
_SAMPLES = 20


@dataclass(frozen=True)
class ImportedRecord:
    line: int
    ts: str | None
    agent_id: str | None
    action: str | None
    decision: str | None
    rule: str | None
    told: str | None
    approver: str | None
    raw_sha256: str
    outside_mandate: bool | None = None


@dataclass(frozen=True)
class ImportResult:
    records: tuple[ImportedRecord, ...]
    total_lines: int
    rejected: int
    rejected_samples: tuple[tuple[int, str], ...]
    file_sha256: str
    status: GapStatus
    integrity: str = INTEGRITY_LABEL
    caveats: tuple[str, ...] = field(default=CAVEATS)


def cap_status(requested: GapStatus) -> GapStatus:
    return STATUS_CAP if requested == GapStatus.MET else requested


def parse_map(pairs: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for pair in pairs:
        name, sep, path = pair.partition("=")
        name, path = name.strip(), path.strip()
        if not sep or not path or name not in AGT_PRESET["fields"]:
            raise ValueError(
                f"bad --map {pair!r}: expected field=dotted.path, field one of "
                + ", ".join(AGT_PRESET["fields"])
            )
        out[name] = [path]
    return out


def json_lines(data: bytes) -> Iterator[tuple[int, bytes, dict | None, str]]:
    """Yield `(line_no, raw, object|None, reason)` per non-blank line (BOM and CRLF tolerant)."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    for no, raw in enumerate(data.split(b"\n"), 1):
        raw = raw.rstrip(b"\r")
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw.decode("utf-8"))
        except ValueError:  # includes UnicodeDecodeError
            yield no, raw, None, "not valid JSON"
            continue
        if isinstance(obj, dict):
            yield no, raw, obj, ""
        else:
            yield no, raw, None, "not a JSON object"


def _dig(obj: dict, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _text(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True)
    return value[:_MAX]


def import_jsonl(path: Path, mapping: dict | None = None) -> ImportResult:
    data = Path(path).read_bytes()
    fields = {**AGT_PRESET["fields"], **(mapping or {})}
    records: list[ImportedRecord] = []
    samples: list[tuple[int, str]] = []
    total = rejected = 0
    for no, raw, obj, reason in json_lines(data):
        total += 1
        vals = {}
        if obj is not None:
            for name, keys in fields.items():
                vals[name] = next(
                    (v for v in (_dig(obj, k) for k in keys) if v is not None), None
                )
            if all(vals[k] is None for k in ("ts", "action", "decision")):
                reason = "no timestamp, action or decision field mapped"
        if reason:
            rejected += 1
            if len(samples) < _SAMPLES:
                samples.append((no, reason))
            continue
        records.append(
            ImportedRecord(
                line=no,
                raw_sha256=hashlib.sha256(raw).hexdigest(),
                **{k: _text(v) for k, v in vals.items()},
            )
        )
    return ImportResult(
        records=tuple(records),
        total_lines=total,
        rejected=rejected,
        rejected_samples=tuple(samples),
        file_sha256=hashlib.sha256(data).hexdigest(),
        # The best case an operator could claim is MET; the cap turns it into PARTIAL.
        status=cap_status(GapStatus.MET) if records else GapStatus.UNVERIFIED,
    )
