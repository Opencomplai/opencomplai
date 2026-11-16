"""Custom controls pack: attestation-led controls an organisation defines in a file.

The file is JSON or YAML (docs/src/reference/custom-pack-format.md). It holds
data only: no code, expressions, file probes, includes, or YAML anchors and
aliases. Each control becomes a row that is Unverified until someone attests it
and is never Met by default.

The file is untrusted input. `load_custom_pack` caps its size before reading
it, parses with a safe loader, checks every field, and never puts the file's
own text into an error message. The pack's framework key is `CUSTOM_<key>` and
a row id is `CUSTOM_<key>:<id>`: ids split on the first ":" (`framework_of`),
so the id part may not hold one.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from opencomplai_core.frameworks import (
    CUSTOM_FRAMEWORK_PREFIX,
    FRAMEWORKS,
    FrameworkPack,
)

CUSTOM_PACK_FORMAT = "opencomplai/custom-pack/v1"
MAX_PACK_BYTES = 1_048_576
MAX_CONTROLS = 500
DEFAULT_TTL_DAYS = 365

# Characters that reorder or hide text, or that show as nothing: the soft hyphen,
# the combining grapheme joiner, the Arabic number signs and letter mark, the Arabic
# and Syriac end-of-text marks, Hangul and Khmer fillers and vowels with no shape,
# Mongolian and general variation selectors, zero-width and direction marks (the
# zero-width joiners too), line and paragraph separators, bidirectional embeddings
# and isolates, invisible operators, the Braille blank, the byte order mark, the
# interlinear annotation marks, the shorthand, musical and Egyptian hieroglyph
# format controls and the tag characters. The body of one exclusion class: no
# lookarounds, so the patterns also run in engines without them. The runtime event
# labels of the SDK exclude the same characters. It is a deny-list: a format
# character added to Unicode later is not in it.
HIDDEN_CHARACTERS = (
    r"\u00ad\u034f\u0600-\u0605\u061c\u06dd\u070f\u08e2\u115f\u1160\u17b4\u17b5"
    r"\u180b-\u180f\u200b-\u200f\u2028\u2029\u202a-\u202e\u2060-\u206f\u2800\u3164"
    r"\ufe00-\ufe0f\ufeff\uffa0\ufff9-\ufffb"
    # the characters themselves: `\U` is not an escape in every regex engine
    "\U00013430-\U0001343f\U0001bca0-\U0001bca3\U0001d173-\U0001d17a"
    "\U000e0000-\U000e0fff"
)
_UNSAFE = rf"\x00-\x1f\x7f-\x9f{HIDDEN_CHARACTERS}"
# One line of text with no control or hidden characters (a terminal or a log line
# cannot be forged or reordered through it) and at least one visible character.
_LINE = rf"^[^{_UNSAFE}]*[^\s{_UNSAFE}][^{_UNSAFE}]*$"
# The same rule as two linear patterns, for the published schema: `_LINE` backtracks
# quadratically under Python's `re` on a long line that ends in a bad character.
# The loader's engine is linear and keeps `_LINE`.
_LINE_CHARACTERS = rf"^[^{_UNSAFE}]+$"
_BLANK = r"^\s*$"


def _linear_line_schema(schema: dict[str, Any]) -> None:
    schema["pattern"] = _LINE_CHARACTERS
    schema["not"] = {"pattern": _BLANK}


# Free text may also run over several lines. A line break is LF or CRLF: a bare CR
# is refused, as it can overwrite what a terminal showed before it.
_TEXT = rf"^(?:[^\x00-\x08\x0b-\x1f\x7f-\x9f{HIDDEN_CHARACTERS}]|\r\n)*$"

_ROW_SOURCE = "custom pack (defined by the organisation)"


class CustomControl(BaseModel):
    """One control of a custom pack."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
        description="Control id, unique in the pack. No colon.",
    )
    title: str = Field(
        min_length=1,
        max_length=200,
        pattern=_LINE,
        json_schema_extra=_linear_line_schema,
    )
    description: str = Field(
        "",
        max_length=2000,
        pattern=_TEXT,
        description="What the control asks of the organisation.",
    )
    default_ttl_days: int = Field(
        DEFAULT_TTL_DAYS,
        ge=1,
        le=3650,
        description="Days an attestation of this control stays current.",
    )


class CustomPackDocument(BaseModel):
    """A custom controls pack file."""

    model_config = ConfigDict(extra="forbid", strict=True)

    format: Literal["opencomplai/custom-pack/v1"]
    key: str = Field(
        pattern=r"^[A-Z][A-Z0-9_]{1,40}$",
        description="Pack key. The framework key is CUSTOM_<key>.",
    )
    label: str = Field(
        min_length=1,
        max_length=120,
        pattern=_LINE,
        json_schema_extra=_linear_line_schema,
    )
    controls: list[CustomControl] = Field(min_length=1, max_length=MAX_CONTROLS)


_ONE_LINE_RULE = (
    "must be one line of visible text with no control, hidden or direction characters"
)
_PATTERN_RULES = {
    "title": _ONE_LINE_RULE,
    "label": _ONE_LINE_RULE,
    "description": (
        "may run over several lines (LF or CRLF) but has no other control "
        "or hidden characters"
    ),
}

# The only names an error may quote from a file: the model's own field names.
_FIELD_NAMES = frozenset(
    {*CustomPackDocument.model_fields, *CustomControl.model_fields}
)


class _RepeatedKeyError(ValueError):
    """A mapping names one key twice: a later block would silently replace the
    first, so a reviewer could be shown one block while another is loaded."""


def _no_repeated_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    if len({key for key, _ in pairs}) != len(pairs):
        raise _RepeatedKeyError
    return dict(pairs)


class _NoAliasLoader(yaml.SafeLoader):
    """A safe YAML loader that refuses anchors, aliases and repeated mapping keys,
    so a small file cannot expand into a huge structure or hide a block."""

    def compose_node(self, parent: Any, index: Any) -> Any:
        if getattr(self.peek_event(), "anchor", None) is not None:
            raise ValueError("anchors and aliases are not allowed")
        return super().compose_node(parent, index)

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[Any, Any]:
        if isinstance(node, yaml.MappingNode):
            self.flatten_mapping(node)  # merge keys, so they are checked too
            seen: set[Any] = set()
            for key_node, _ in node.value:
                key = self.construct_object(key_node, deep=True)
                try:
                    fresh = key not in seen
                except TypeError:  # unhashable: the parent refuses it below
                    continue
                if not fresh:
                    raise _RepeatedKeyError
                seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _where(loc: tuple[Any, ...]) -> str:
    """Where in the pack an error is, naming only fields and list positions."""
    out = ""
    for part in loc:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += ("." if out else "") + (part if part in _FIELD_NAMES else "?")
    return out or "the pack"


def _parse(raw: bytes, as_json: bool) -> Any:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("the file is not valid UTF-8 text") from None
    try:
        if as_json:
            return json.loads(text, object_pairs_hook=_no_repeated_keys)
        loader = _NoAliasLoader(text)
        try:
            return loader.get_single_data()
        finally:
            loader.dispose()
    except _RepeatedKeyError:
        raise ValueError("a mapping in the file repeats a key") from None
    except (ValueError, yaml.YAMLError, RecursionError):
        # Not the parser's text: it quotes the file.
        kind = "JSON" if as_json else "YAML without anchors or aliases"
        raise ValueError(f"the file is not valid {kind}") from None


def _requirements(document: CustomPackDocument) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for control in document.controls:
        rid = f"{CUSTOM_FRAMEWORK_PREFIX}{document.key}:{control.id}"
        out[rid] = {
            "title": control.title,
            "note": control.description,
            "default_ttl_days": control.default_ttl_days,
            "sources": [{"kind": "attestation", "ref": rid}],
            "source": _ROW_SOURCE,
            "confidence": "low",
            "needs_founder_review": False,
        }
    return out


def load_custom_pack(path: Path) -> FrameworkPack:
    """Read, check and build a custom controls pack from a JSON or YAML file.

    A `.json` file is read as JSON, any other as YAML. Raises ValueError with a
    short message that never repeats the file's text.
    """
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("the pack is not a regular file")
        if info.st_size > MAX_PACK_BYTES:
            raise ValueError(f"the file is larger than {MAX_PACK_BYTES} bytes")
        with path.open("rb") as handle:
            raw = handle.read(MAX_PACK_BYTES + 1)
    except OSError as exc:
        raise ValueError(f"could not read the file ({exc.strerror})") from None
    if len(raw) > MAX_PACK_BYTES:
        raise ValueError(f"the file is larger than {MAX_PACK_BYTES} bytes")

    data = _parse(raw, path.suffix.lower() == ".json")
    try:
        document = CustomPackDocument.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        msg = first["msg"]
        # The text patterns are long character classes; say the rule instead.
        if first["type"] == "string_pattern_mismatch":
            field = first["loc"][-1] if first["loc"] else None
            if field in _PATTERN_RULES:
                msg = _PATTERN_RULES[field]
        raise ValueError(f"{_where(first['loc'])}: {msg}") from None

    ids = [control.id for control in document.controls]
    if len(set(ids)) != len(ids):
        raise ValueError("controls: two controls share an id")
    framework = f"{CUSTOM_FRAMEWORK_PREFIX}{document.key}"
    if framework in FRAMEWORKS:
        raise ValueError(f"the framework key {framework} is already registered")

    return FrameworkPack(
        framework,
        f"{document.label} (custom pack, attestation-led)",
        "DISCLAIMER_V2",
        requirements_data=_requirements(document),
    )


def register_custom_pack(pack: FrameworkPack) -> None:
    """Add `pack` to the framework registry. Raises ValueError when its key is taken
    or is not a custom pack's."""
    if not pack.id.startswith(CUSTOM_FRAMEWORK_PREFIX):
        raise ValueError(f"{pack.id} is not a custom pack key")
    if pack.id in FRAMEWORKS:
        raise ValueError(f"the framework key {pack.id} is already registered")
    FRAMEWORKS[pack.id] = pack
