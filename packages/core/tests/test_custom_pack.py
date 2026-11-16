"""Custom controls pack: loading, the registry, evaluation and the schema contract.

The file is untrusted input: size, YAML aliases and tags, bad fields and the
text of every error are pinned here.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path

import jsonschema
import pytest
import yaml
from opencomplai_core.custom_pack import (
    CUSTOM_PACK_FORMAT,
    MAX_PACK_BYTES,
    load_custom_pack,
    register_custom_pack,
)
from opencomplai_core.frameworks import (
    EU_AI_ACT,
    FRAMEWORKS,
    FrameworkPack,
    attestable_ids,
    attestation_only_ids,
    data_version,
    evaluate_targets,
    framework_of,
    pack_requirements,
    requirement_title,
    resolve_targets,
    validate_gate,
)
from opencomplai_core.json_schemas import (
    CUSTOM_PACK_SCHEMA_ID,
    build_custom_pack_schema,
)
from opencomplai_core.models import Attestation, GapStatus, SystemManifest

_REPO = Path(__file__).resolve().parents[3]
_SCHEMA = (
    _REPO
    / "packages"
    / "core"
    / "src"
    / "opencomplai_core"
    / "data"
    / "custom_pack.schema.json"
)
_DOCS_PAGE = _REPO / "docs" / "src" / "reference" / "custom-pack-format.md"

YAML_PACK = """\
format: opencomplai/custom-pack/v1
key: ACME_AI
label: Acme internal AI controls
controls:
  - id: AC-1
    title: Model inventory reviewed each quarter
    description: Reviewed and signed off by the governance group.
    default_ttl_days: 90
  - id: AC-2
    title: Customer-facing outputs reviewed before launch
"""

JSON_PACK = {
    "format": "opencomplai/custom-pack/v1",
    "key": "ACME_AI",
    "label": "Acme internal AI controls",
    "controls": [
        {
            "id": "AC-1",
            "title": "Model inventory reviewed each quarter",
            "description": "Reviewed and signed off by the governance group.",
            "default_ttl_days": 90,
        },
        {"id": "AC-2", "title": "Customer-facing outputs reviewed before launch"},
    ],
}


def _doc(**over: object) -> dict:
    return {**JSON_PACK, **over}


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_bytes(text.encode("utf-8"))  # no newline translation: sizes are exact
    return path


def _load_dict(tmp_path: Path, doc: dict, name: str = "pack.json") -> FrameworkPack:
    return load_custom_pack(_write(tmp_path, name, json.dumps(doc)))


def _error(tmp_path: Path, text: str, name: str = "pack.yaml") -> str:
    with pytest.raises(ValueError, match=r".") as caught:
        load_custom_pack(_write(tmp_path, name, text))
    return str(caught.value)


@pytest.fixture
def acme(tmp_path, monkeypatch) -> FrameworkPack:
    pack = load_custom_pack(_write(tmp_path, "acme.yaml", YAML_PACK))
    monkeypatch.setitem(FRAMEWORKS, pack.id, pack)
    return pack


def _manifest(**over: object) -> SystemManifest:
    return SystemManifest(system_id="sys", intended_purpose="credit scoring", **over)


# --- a valid pack -------------------------------------------------------------


def test_yaml_and_json_give_identical_maps_and_the_same_data_version(tmp_path):
    from_yaml = load_custom_pack(_write(tmp_path, "pack.yaml", YAML_PACK))
    from_json = load_custom_pack(_write(tmp_path, "pack.json", json.dumps(JSON_PACK)))

    assert from_yaml.requirements_data == from_json.requirements_data
    assert data_version(from_yaml) == data_version(from_json)
    assert from_yaml.id == "CUSTOM_ACME_AI"
    assert from_yaml.label == "Acme internal AI controls (custom pack, attestation-led)"
    assert from_yaml.disclaimer_ref == "DISCLAIMER_V2"
    assert from_yaml.requirements is None
    assert from_yaml.derive is None
    # A different pack has a different version.
    other = _load_dict(tmp_path, _doc(label="x", controls=JSON_PACK["controls"][:1]))
    assert data_version(other) != data_version(from_json)


def test_rows_follow_the_native_pack_invariants(tmp_path):
    pack = load_custom_pack(_write(tmp_path, "pack.yaml", YAML_PACK))
    requirements = pack_requirements(pack)

    assert list(requirements) == ["CUSTOM_ACME_AI:AC-1", "CUSTOM_ACME_AI:AC-2"]
    for rid, config in requirements.items():
        assert rid.startswith(f"{pack.id}:")
        assert len(rid) > len(pack.id) + 1
        assert isinstance(config["title"], str)
        assert config["title"].strip()
        ttl = config["default_ttl_days"]
        assert isinstance(ttl, int)
        assert ttl > 0
        assert config["sources"] == [{"kind": "attestation", "ref": rid}]
        assert config["source"] == "custom pack (defined by the organisation)"
        assert config["confidence"] == "low"
        assert config["needs_founder_review"] is False
    first, second = requirements.values()
    assert first["note"] == "Reviewed and signed off by the governance group."
    assert first["default_ttl_days"] == 90
    assert second["note"] == ""
    assert second["default_ttl_days"] == 365


def test_a_pack_read_from_a_bom_and_yml_file_loads(tmp_path):
    path = tmp_path / "pack.yml"
    path.write_bytes(b"\xef\xbb\xbf" + YAML_PACK.encode("utf-8"))
    assert load_custom_pack(path).id == "CUSTOM_ACME_AI"


def test_framework_of_splits_a_custom_row_id_on_the_first_colon():
    assert framework_of("CUSTOM_ACME_AI:AC-1") == "CUSTOM_ACME_AI"


def test_register_adds_the_pack_once(tmp_path, monkeypatch):
    pack = load_custom_pack(_write(tmp_path, "acme.yaml", YAML_PACK))
    # Set then delete, so the registry is restored when the test ends.
    monkeypatch.setitem(FRAMEWORKS, pack.id, pack)
    monkeypatch.delitem(FRAMEWORKS, pack.id)

    register_custom_pack(pack)

    assert FRAMEWORKS[pack.id] is pack
    with pytest.raises(ValueError, match="already registered"):
        register_custom_pack(pack)
    with pytest.raises(ValueError, match="already registered"):
        load_custom_pack(_write(tmp_path, "again.yaml", YAML_PACK))


def test_register_refuses_a_key_that_is_not_a_custom_key():
    with pytest.raises(ValueError, match="not a custom pack key"):
        register_custom_pack(FrameworkPack("GDPR2", "x", requirements_data={}))


def test_the_registry_helpers_read_a_custom_pack(acme):
    rid = "CUSTOM_ACME_AI:AC-1"
    assert requirement_title(rid) == "Model inventory reviewed each quarter"
    assert requirement_title("CUSTOM_ACME_AI:NOPE") is None
    assert attestable_ids(acme.id) == {rid, "CUSTOM_ACME_AI:AC-2"}
    assert attestation_only_ids(acme.id) == {rid, "CUSTOM_ACME_AI:AC-2"}
    assert resolve_targets(_manifest(), [EU_AI_ACT, acme.id]) == [EU_AI_ACT, acme.id]


# --- rejections ---------------------------------------------------------------


def test_a_file_over_one_megabyte_is_refused_without_reading_it(tmp_path, monkeypatch):
    path = _write(tmp_path, "big.yaml", "# " + "x" * MAX_PACK_BYTES + "\n")
    assert path.stat().st_size > MAX_PACK_BYTES

    def boom(*args, **kwargs):
        raise AssertionError("the oversized file was opened")

    monkeypatch.setattr(Path, "open", boom)
    with pytest.raises(ValueError, match="larger than 1048576 bytes"):
        load_custom_pack(path)


def test_a_file_of_exactly_the_limit_is_not_refused_for_size(tmp_path):
    body = YAML_PACK + "#" * (MAX_PACK_BYTES - len(YAML_PACK) - 1) + "\n"
    path = _write(tmp_path, "edge.yaml", body)
    assert path.stat().st_size == MAX_PACK_BYTES
    assert load_custom_pack(path).id == "CUSTOM_ACME_AI"


def test_501_controls_are_refused_and_500_are_not(tmp_path):
    def controls(n: int) -> list[dict]:
        return [{"id": f"C{i}", "title": f"Control {i}"} for i in range(n)]

    assert (
        len(_load_dict(tmp_path, _doc(controls=controls(500))).requirements_data) == 500
    )
    with pytest.raises(ValueError, match="controls"):
        _load_dict(tmp_path, _doc(controls=controls(501)))


def test_no_controls_is_refused(tmp_path):
    with pytest.raises(ValueError, match="controls"):
        _load_dict(tmp_path, _doc(controls=[]))


def test_a_duplicate_id_is_refused(tmp_path):
    controls = [{"id": "A", "title": "One"}, {"id": "A", "title": "Two"}]
    with pytest.raises(ValueError, match="share an id"):
        _load_dict(tmp_path, _doc(controls=controls))


@pytest.mark.parametrize("bad_id", ["A:1", "", "-A", ".A", "a b", "A" * 65, "é", "A\n"])
def test_a_bad_control_id_is_refused(tmp_path, bad_id):
    with pytest.raises(ValueError, match=r"controls\[0\]\.id"):
        _load_dict(tmp_path, _doc(controls=[{"id": bad_id, "title": "T"}]))


@pytest.mark.parametrize("key", ["acme", "A", "1ABC", "A-B", "A" * 42, "ACME AI", ""])
def test_a_bad_key_is_refused(tmp_path, key):
    with pytest.raises(ValueError, match="key"):
        _load_dict(tmp_path, _doc(key=key))


def test_the_longest_key_is_accepted(tmp_path):
    key = "A" * 41
    assert _load_dict(tmp_path, _doc(key=key)).id == f"CUSTOM_{key}"


def test_an_unknown_top_level_key_is_refused(tmp_path):
    with pytest.raises(ValueError, match="Extra inputs"):
        _load_dict(tmp_path, _doc(extra="x"))


def test_an_unknown_control_key_is_refused(tmp_path):
    controls = [{"id": "A", "title": "T", "check": "exec('x')"}]
    with pytest.raises(ValueError, match=r"controls\[0\]"):
        _load_dict(tmp_path, _doc(controls=controls))


@pytest.mark.parametrize("fmt", ["opencomplai/custom-pack/v2", "", None, 1])
def test_a_wrong_format_is_refused(tmp_path, fmt):
    with pytest.raises(ValueError, match="format"):
        _load_dict(tmp_path, _doc(format=fmt))


def test_a_missing_format_is_refused(tmp_path):
    doc = _doc()
    del doc["format"]
    with pytest.raises(ValueError, match="format"):
        _load_dict(tmp_path, doc)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", ""),
        ("title", "   "),
        ("title", "x" * 201),
        ("title", "two\nlines"),
        ("title", "esc\x1b[31mred"),
        ("title", 5),
        ("description", "x" * 2001),
        ("description", "bell\x07"),
        ("default_ttl_days", 0),
        ("default_ttl_days", 3651),
        ("default_ttl_days", "30"),
        ("default_ttl_days", True),
        ("default_ttl_days", 1.5),
    ],
)
def test_a_bad_control_field_is_refused(tmp_path, field, value):
    control = {"id": "A", "title": "T", field: value}
    with pytest.raises(ValueError, match=rf"controls\[0\]\.{field}"):
        _load_dict(tmp_path, _doc(controls=[control]))


@pytest.mark.parametrize(
    ("where", "doc"),
    [
        ("controls[0].title", _doc(controls=[{"id": "A", "title": "T\nX"}])),
        ("controls[0].title", _doc(controls=[{"id": "A", "title": "  "}])),
        ("label", _doc(label="a\u202eb")),
    ],
)
def test_a_text_pattern_error_says_the_rule_not_the_regex(tmp_path, where, doc):
    with pytest.raises(ValueError, match=r".") as caught:
        _load_dict(tmp_path, doc)
    assert str(caught.value) == (
        f"{where}: must be one line of visible text with no control, "
        "hidden or direction characters"
    )


def test_a_description_pattern_error_says_the_rule_not_the_regex(tmp_path):
    control = {"id": "A", "title": "T", "description": "bell\x07"}
    with pytest.raises(ValueError, match=r".") as caught:
        _load_dict(tmp_path, _doc(controls=[control]))
    assert str(caught.value) == (
        "controls[0].description: may run over several lines (LF or CRLF) "
        "but has no other control or hidden characters"
    )


def test_description_may_run_over_several_lines(tmp_path):
    control = {"id": "A", "title": "T", "description": "one\n\ttwo\r\nthree"}
    pack = _load_dict(tmp_path, _doc(controls=[control]))
    assert pack_requirements(pack)["CUSTOM_ACME_AI:A"]["note"] == "one\n\ttwo\r\nthree"


@pytest.mark.parametrize("label", ["", "  ", "x" * 121, "a\nb", "a\x1b[2Jb"])
def test_a_bad_label_is_refused(tmp_path, label):
    with pytest.raises(ValueError, match="label"):
        _load_dict(tmp_path, _doc(label=label))


@pytest.mark.parametrize("text", ["", "- a\n- b\n", "just text\n", "42\n", "null\n"])
def test_a_pack_that_is_not_a_mapping_is_refused(tmp_path, text):
    assert _error(tmp_path, text)


def test_an_invalid_json_file_is_refused(tmp_path):
    assert "not valid JSON" in _error(tmp_path, '{"format": ', name="pack.json")


def test_a_deeply_nested_file_is_refused_cleanly(tmp_path):
    deep = "[" * 100_000 + "]" * 100_000
    assert "not valid JSON" in _error(tmp_path, deep, name="pack.json")
    assert "not valid YAML" in _error(tmp_path, deep)


def test_a_file_that_is_not_utf8_is_refused(tmp_path):
    path = tmp_path / "pack.yaml"
    path.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(ValueError, match="UTF-8"):
        load_custom_pack(path)


def test_a_missing_file_and_a_directory_are_refused(tmp_path):
    with pytest.raises(ValueError, match="could not read the file"):
        load_custom_pack(tmp_path / "nope.yaml")
    with pytest.raises(ValueError, match="regular file"):
        load_custom_pack(tmp_path)


def test_a_registered_key_is_refused(tmp_path, monkeypatch):
    monkeypatch.setitem(FRAMEWORKS, "CUSTOM_ACME_AI", FrameworkPack("X", "x"))
    with pytest.raises(ValueError, match="CUSTOM_ACME_AI is already registered"):
        load_custom_pack(_write(tmp_path, "pack.yaml", YAML_PACK))


_HEAD = "format: opencomplai/custom-pack/v1\nkey: ACME_AI\nlabel: L\ncontrols:\n"


@pytest.mark.parametrize(
    "text",
    [
        _HEAD + "  - &base\n    id: A\n    title: T\n  - <<: *base\n    id: B\n",
        _HEAD + "  - &base\n    id: A\n    title: T\n",
        _HEAD + "  - id: A\n    title: &t T\n  - id: B\n    title: *t\n",
    ],
    ids=["merge", "anchor", "alias"],
)
def test_a_yaml_anchor_or_alias_is_refused(tmp_path, text):
    assert "anchors or aliases" in _error(tmp_path, text)


def test_a_billion_laughs_file_fails_fast(tmp_path):
    lols = ["a: &a [x, x, x, x, x, x, x, x, x]"]
    previous = "a"
    for name in "bcdefghi":
        lols.append(f"{name}: &{name} [{', '.join(['*' + previous] * 9)}]")
        previous = name
    started = time.monotonic()
    message = _error(tmp_path, "\n".join(lols) + "\n")
    assert time.monotonic() - started < 2
    assert "anchors or aliases" in message


@pytest.mark.parametrize(
    "tag",
    [
        "!!python/object/apply:os.system ['echo SENTINEL']",
        "!!python/object:os.SENTINEL {}",
        "!!python/name:os.system",
    ],
)
def test_a_yaml_object_tag_is_refused(tmp_path, tag):
    text = YAML_PACK.replace("label: Acme internal AI controls", f"label: {tag}")
    message = _error(tmp_path, text)
    assert "not valid YAML" in message
    assert "SENTINEL" not in message


def test_a_yaml_file_with_two_documents_is_refused(tmp_path):
    assert "not valid YAML" in _error(tmp_path, YAML_PACK + "---\nformat: x\n")


def test_a_huge_yaml_integer_is_refused_cleanly(tmp_path):
    text = YAML_PACK.replace("default_ttl_days: 90", "default_ttl_days: " + "9" * 6000)
    assert _error(tmp_path, text)


@pytest.mark.parametrize(
    "text",
    [
        _HEAD.replace("controls:\n", "controls: SENTINEL_BODY\n"),
        _HEAD + "  - id: A\n    title: T\n    leak_SENTINEL: x\n",
        _HEAD + "  - id: SENTINEL:ID\n    title: T\n",
        _HEAD.replace("ACME_AI", "sentinel_key") + "  - id: A\n    title: T\n",
        _HEAD.replace("custom-pack/v1", "SENTINEL/v1") + "  - id: A\n    title: T\n",
        "SENTINEL: [unclosed",
        _HEAD + "  - id: A\n    title: T\nSENTINEL_TOP: 1\n",
        _HEAD + "  - id: A\n    title: T\n    default_ttl_days: SENTINEL_DAYS\n",
    ],
)
def test_error_messages_never_contain_the_files_text(tmp_path, text):
    message = _error(tmp_path, text)
    assert "sentinel" not in message.lower()
    assert len(message) < 200


def test_error_messages_name_only_fields_and_positions(tmp_path):
    controls = [{"id": "A", "title": "T", "leak_SECRET": 1}]
    message = _error(tmp_path, json.dumps(_doc(controls=controls)), name="p.json")
    assert message.startswith("controls[0].?: ")
    assert "SECRET" not in message


# --- repeated mapping keys -----------------------------------------------------


_ONE_CONTROL = '[{"id": "A", "title": "T"}]'
_REPEATS_A_KEY = "a mapping in the file repeats a key"


@pytest.mark.parametrize(
    "text",
    [
        # a second `controls` block would replace the first
        '{"format": "opencomplai/custom-pack/v1", "key": "ACME_AI", "label": "L",'
        f' "controls": {_ONE_CONTROL}, "controls": [{{"id": "B", "title": "T"}}]}}',
        # a repeated field inside a control
        '{"format": "opencomplai/custom-pack/v1", "key": "ACME_AI", "label": "L",'
        ' "controls": [{"id": "A", "title": "T", "title": "U"}]}',
        # a repeated key that the model would refuse anyway
        '{"format": "opencomplai/custom-pack/v1", "key": "ACME_AI", "label": "L",'
        f' "controls": {_ONE_CONTROL}, "SENTINEL_KEY": 1, "SENTINEL_KEY": 2}}',
    ],
    ids=["controls-block", "control-field", "unknown-key"],
)
def test_a_json_mapping_that_repeats_a_key_is_refused(tmp_path, text):
    message = _error(tmp_path, text, name="pack.json")
    assert message == _REPEATS_A_KEY


@pytest.mark.parametrize(
    "text",
    [
        _HEAD + "  - id: A\n    title: T\ncontrols:\n  - id: B\n    title: T\n",
        _HEAD + "  - id: A\n    title: T\n    title: U\n",
        _HEAD + "  - id: A\n    title: T\nSENTINEL_KEY: 1\nSENTINEL_KEY: 2\n",
        _HEAD.replace("label: L\n", "label: L\nlabel: M\n")
        + "  - id: A\n    title: T\n",
        # a merge key that clashes with an explicit key
        _HEAD + "  - <<: {id: A, title: T}\n    title: U\n",
    ],
    ids=["controls-block", "control-field", "unknown-key", "label", "merge-clash"],
)
def test_a_yaml_mapping_that_repeats_a_key_is_refused(tmp_path, text):
    message = _error(tmp_path, text)
    assert message == _REPEATS_A_KEY


def test_a_yaml_mapping_without_a_repeat_still_loads_with_a_merge_key(tmp_path):
    pack = load_custom_pack(
        _write(tmp_path, "pack.yaml", _HEAD + "  - <<: {id: A}\n    title: T\n")
    )
    assert list(pack_requirements(pack)) == ["CUSTOM_ACME_AI:A"]


# --- hidden and reordering characters ---------------------------------------------


# Characters that reorder text or show as nothing: the first and last of every
# excluded range, and a middle one. The zero-width joiners (U+200C, U+200D) are
# refused too, as the page on the format says.
_HIDDEN_CODEPOINTS = [
    0x00AD,
    0x034F,
    0x0600,
    0x0605,
    0x061C,
    0x06DD,
    0x070F,
    0x08E2,
    0x115F,
    0x1160,
    0x17B4,
    0x17B5,
    0x180B,
    0x180D,
    0x180F,
    0x200B,
    0x200C,
    0x200D,
    0x200E,
    0x200F,
    0x2028,
    0x2029,
    0x202A,
    0x202B,
    0x202C,
    0x202D,
    0x202E,
    0x2060,
    0x2062,
    0x2066,
    0x2067,
    0x2068,
    0x2069,
    0x206A,
    0x206F,
    0x2800,
    0x3164,
    0xFE00,
    0xFE08,
    0xFE0F,
    0xFEFF,
    0xFFA0,
    0xFFF9,
    0xFFFA,
    0xFFFB,
    0x13430,
    0x1343F,
    0x1BCA0,
    0x1BCA3,
    0x1D173,
    0x1D17A,
    0xE0000,
    0xE0020,
    0xE007F,
    0xE0100,
    0xE0FFF,
]
# Their neighbours, which are ordinary text and stay allowed.
_PLAIN_NEIGHBOURS = [
    0x00AC,
    0x00AE,
    0x034E,
    0x0350,
    0x05FF,
    0x0606,
    0x061B,
    0x061D,
    0x06DC,
    0x06DE,
    0x070E,
    0x0710,
    0x08E1,
    0x08E3,
    0x115E,
    0x1161,
    0x17B3,
    0x17B6,
    0x180A,
    0x1810,
    0x2010,
    0x2027,
    0x2070,
    0x27FF,
    0x2801,
    0x3163,
    0x3165,
    0xFE10,
    0xFEFE,
    0xFF00,
    0xFF9F,
    0xFFA1,
    0xFFF8,
    0xFFFC,
    0x1342F,
    0x13440,
    0x1BC9F,
    0x1BCA4,
    0x1D172,
    0x1D17B,
    0xDFFFD,
    0xE1000,
]


def _id(codepoint: int) -> str:
    return f"U+{codepoint:04X}"


@pytest.mark.parametrize("codepoint", _HIDDEN_CODEPOINTS, ids=_id)
@pytest.mark.parametrize("field", ["label", "title", "description"])
def test_a_hidden_or_reordering_character_is_refused(tmp_path, field, codepoint):
    text = "ab" + chr(codepoint) + "cd"
    if field == "label":
        doc = _doc(label=text)
    else:
        doc = _doc(controls=[{"id": "A", "title": "T", field: text}])
    with pytest.raises(ValueError, match=field):
        _load_dict(tmp_path, doc)


@pytest.mark.parametrize("codepoint", _HIDDEN_CODEPOINTS, ids=_id)
def test_a_title_of_only_hidden_characters_is_refused(tmp_path, codepoint):
    controls = [{"id": "A", "title": chr(codepoint) * 3}]
    with pytest.raises(ValueError, match="title"):
        _load_dict(tmp_path, _doc(controls=controls))


@pytest.mark.parametrize("codepoint", _PLAIN_NEIGHBOURS, ids=_id)
def test_text_next_to_the_excluded_ranges_is_accepted(tmp_path, codepoint):
    text = "ab" + chr(codepoint) + "cd"
    controls = [{"id": "A", "title": text, "description": text}]
    pack = _load_dict(tmp_path, _doc(label=text, controls=controls))
    assert pack_requirements(pack)["CUSTOM_ACME_AI:A"]["title"] == text


def test_arabic_and_other_right_to_left_text_is_accepted(tmp_path):
    # Arabic and Hebrew letters, written as code points.
    title = "".join(map(chr, (0x645, 0x631, 0x62D, 0x628, 0x627, 0x20, 0x5E9, 0x5DC)))
    pack = _load_dict(tmp_path, _doc(controls=[{"id": "A", "title": title}]))
    assert pack_requirements(pack)["CUSTOM_ACME_AI:A"]["title"] == title


@pytest.mark.parametrize("codepoint", _HIDDEN_CODEPOINTS, ids=_id)
def test_the_schema_refuses_the_hidden_characters_too(codepoint):
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    for bad in (
        _doc(label="a" + chr(codepoint) + "b"),
        _doc(controls=[{"id": "A", "title": "a" + chr(codepoint) + "b"}]),
        _doc(controls=[{"id": "A", "title": "T", "description": chr(codepoint)}]),
    ):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)


def test_the_patterns_use_no_lookarounds():
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    patterns = re.findall(r'"pattern": "([^"]*)"', json.dumps(schema))
    assert patterns
    assert not [p for p in patterns if re.search(r"\(\?<?[=!]", p)]


@pytest.mark.parametrize(
    "text",
    ["one\rtwo", "one\r", "\rone", "one\r\r\ntwo", "one\n\rtwo"],
    ids=["inside", "last", "first", "before-crlf", "after-lf"],
)
def test_a_bare_carriage_return_is_refused_in_a_description(tmp_path, text):
    control = {"id": "A", "title": "T", "description": text}
    with pytest.raises(ValueError, match=r"controls\[0\]\.description"):
        _load_dict(tmp_path, _doc(controls=[control]))
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_doc(controls=[control]), schema)


def test_line_breaks_stay_accepted_in_a_description_by_loader_and_schema(tmp_path):
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    for text in ("a\nb", "a\r\nb", "a\r\n\r\nb\n", "a\r\n"):
        doc = _doc(controls=[{"id": "A", "title": "T", "description": text}])
        jsonschema.validate(doc, schema)
        pack = _load_dict(tmp_path, doc)
        assert pack_requirements(pack)["CUSTOM_ACME_AI:A"]["note"] == text


def test_the_text_pattern_is_not_a_slow_path_for_a_long_bad_description():
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    for text in ("a\r\n" * 10_000 + "\r", "a" * 30_000 + "\x00"):
        doc = _doc(controls=[{"id": "A", "title": "T", "description": text}])
        started = time.monotonic()
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(doc))
        assert errors
        assert time.monotonic() - started < 1


def _line_patterns(schema: dict) -> dict[str, dict]:
    return {
        "title": schema["$defs"]["CustomControl"]["properties"]["title"],
        "label": schema["properties"]["label"],
    }


@pytest.mark.parametrize("field", ["title", "label"])
def test_the_published_line_pattern_is_linear_on_a_long_line_with_a_bad_end(field):
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    definition = _line_patterns(schema)[field]
    # two linear patterns instead of one with two unbounded runs around a class
    assert definition["not"] == {"pattern": "^\\s*$"}
    assert not re.search(r"\]\*\[.*\]\*", definition["pattern"])
    bad = "a" * 30_000 + "\x00"
    doc = (
        _doc(controls=[{"id": "A", "title": bad}])
        if field == "title"
        else _doc(label=bad)
    )
    started = time.monotonic()
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(doc))
    assert errors
    # the single-pattern form took 3 seconds on this input
    assert time.monotonic() - started < 1


@pytest.mark.parametrize(
    ("text", "accepted"),
    [
        ("a", True),
        (" a ", True),
        ("two words", True),
        (chr(0x00E9), True),
        (" ", False),
        (chr(0x3000), False),
        (chr(0x00A0) + " " + chr(0x2003), False),
        ("a\x00", False),
        ("a" + chr(0x00AD), False),
        ("a" + chr(0xE0001), False),
    ],
)
def test_the_two_part_line_rule_and_the_loader_agree(tmp_path, text, accepted):
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    for doc in (_doc(label=text), _doc(controls=[{"id": "A", "title": text}])):
        if accepted:
            jsonschema.validate(doc, schema)
            _load_dict(tmp_path, doc)
        else:
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(doc, schema)
            with pytest.raises(ValueError, match=r"."):
                _load_dict(tmp_path, doc)


def test_a_key_with_a_final_line_break_passes_the_schema_but_not_the_loader(tmp_path):
    # Python's jsonschema uses re.search, where "$" also matches before a final
    # line break: the loader is the check, as the page on the format says.
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    doc = _doc(key="ACME_AI\n")
    jsonschema.validate(doc, schema)
    with pytest.raises(ValueError, match="key"):
        _load_dict(tmp_path, doc)


# --- the gate and the registry ----------------------------------------------------


def test_gating_on_a_custom_pack_that_is_not_loaded_says_how_to_load_it():
    with pytest.raises(
        ValueError, match=r"unknown gated framework CUSTOM_X;"
    ) as caught:
        validate_gate(["CUSTOM_X"], "missing", [EU_AI_ACT])
    assert str(caught.value).endswith("(load it with --custom-pack)")
    with pytest.raises(ValueError, match="unknown gated framework ISO_X") as other:
        validate_gate(["ISO_X"], "missing", [EU_AI_ACT])
    assert "--custom-pack" not in str(other.value)


def test_a_native_pack_without_data_raises_value_error_not_an_assertion(monkeypatch):
    monkeypatch.setitem(FRAMEWORKS, "BARE", FrameworkPack("BARE", "Bare"))
    with pytest.raises(ValueError, match="BARE has no requirements data"):
        evaluate_targets(
            _manifest(), [EU_AI_ACT, "BARE"], commit_ref="abc", today=date(2026, 10, 12)
        )


# --- evaluation ----------------------------------------------------------------


def _attestation() -> Attestation:
    return Attestation(
        statement="Reviewed in October.",
        attested_by="Jane Doe",
        attested_at="2026-10-12",
    )


def _evaluate(manifest: SystemManifest, targets: list[str]):
    return evaluate_targets(
        manifest, targets, commit_ref="abc1234", today=date(2026, 11, 1)
    )


def test_unattested_rows_are_unverified_and_an_attested_row_is_met(acme):
    manifest = _manifest(
        framework_inputs={
            acme.id: {"attested": {"CUSTOM_ACME_AI:AC-1": _attestation()}}
        }
    )
    reports = _evaluate(manifest, [EU_AI_ACT, acme.id])

    rows = {row.article: row for row in reports[acme.id].report.articles}
    assert set(rows) == {"CUSTOM_ACME_AI:AC-1", "CUSTOM_ACME_AI:AC-2"}
    assert rows["CUSTOM_ACME_AI:AC-1"].status is GapStatus.MET
    assert rows["CUSTOM_ACME_AI:AC-2"].status is GapStatus.UNVERIFIED
    assert (
        "framework_inputs.CUSTOM_ACME_AI.attested"
        in rows["CUSTOM_ACME_AI:AC-2"].rationale
    )
    assert reports[acme.id].label == acme.label
    assert reports[acme.id].data_version == data_version(acme)
    assert reports[acme.id].derived_from is None
    assert reports[acme.id].disclaimer_ref == "DISCLAIMER_V2"


def test_no_row_is_met_without_an_attestation(acme):
    reports = _evaluate(_manifest(), [EU_AI_ACT, acme.id])
    statuses = {row.status for row in reports[acme.id].report.articles}
    assert statuses == {GapStatus.UNVERIFIED}


def test_an_attestation_for_an_id_outside_the_pack_is_refused(acme):
    manifest = _manifest(
        framework_inputs={
            acme.id: {"attested": {"CUSTOM_ACME_AI:NOPE": _attestation()}}
        }
    )
    with pytest.raises(ValueError, match="CUSTOM_ACME_AI:NOPE"):
        _evaluate(manifest, [EU_AI_ACT, acme.id])


def test_an_exclusion_applies_to_a_custom_row(acme):
    manifest = _manifest(
        framework_inputs={
            acme.id: {"excluded": {"CUSTOM_ACME_AI:AC-2": "Not used by this system."}}
        }
    )
    report = _evaluate(manifest, [EU_AI_ACT, acme.id])[acme.id]
    assert [row.article for row in report.report.articles] == ["CUSTOM_ACME_AI:AC-1"]
    assert report.excluded == {"CUSTOM_ACME_AI:AC-2": "Not used by this system."}


def test_an_unregistered_custom_key_in_framework_inputs_is_ignored():
    manifest = _manifest(
        framework_inputs={"CUSTOM_X": {"attested": {"CUSTOM_X:A": _attestation()}}}
    )
    reports = _evaluate(manifest, [EU_AI_ACT])
    assert list(reports) == [EU_AI_ACT]


def test_other_unknown_framework_inputs_still_raise():
    manifest = _manifest(framework_inputs={"NOT_A_PACK": {}, "CUSTOM_X": {}})
    with pytest.raises(ValueError, match="NOT_A_PACK"):
        _evaluate(manifest, [EU_AI_ACT])
    with pytest.raises(ValueError, match="unknown compliance target CUSTOM_X"):
        _evaluate(_manifest(), [EU_AI_ACT, "CUSTOM_X"])


# --- the schema contract ---------------------------------------------------------


def test_the_committed_schema_equals_the_built_one():
    committed = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    assert committed == build_custom_pack_schema(), (
        "run `python scripts/generate_artifact_schemas.py` and commit the result."
    )
    assert committed["$id"] == CUSTOM_PACK_SCHEMA_ID
    assert committed["additionalProperties"] is False
    assert committed["properties"]["format"]["const"] == CUSTOM_PACK_FORMAT


def _fenced(text: str, language: str) -> str:
    match = re.search(rf"```{language}\n(.*?)```", text, re.DOTALL)
    assert match, f"no {language} block in the docs page"
    return match.group(1)


def test_the_examples_in_the_docs_page_validate_against_the_schema(tmp_path):
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    page = _DOCS_PAGE.read_text(encoding="utf-8")
    from_yaml = yaml.safe_load(_fenced(page, "yaml"))
    from_json = json.loads(_fenced(page, "json"))

    jsonschema.validate(from_yaml, schema)
    jsonschema.validate(from_json, schema)
    assert from_yaml == from_json
    # And the loader takes both.
    yaml_pack = load_custom_pack(_write(tmp_path, "doc.yaml", _fenced(page, "yaml")))
    json_pack = load_custom_pack(_write(tmp_path, "doc.json", _fenced(page, "json")))
    assert yaml_pack.requirements_data == json_pack.requirements_data


@pytest.mark.parametrize(
    "bad",
    [
        _doc(key="acme"),
        _doc(extra=1),
        _doc(format="x"),
        _doc(controls=[]),
        _doc(controls=[{"id": "A:1", "title": "T"}]),
        _doc(controls=[{"id": "A", "title": "T", "default_ttl_days": 0}]),
        _doc(controls=[{"id": "A", "title": "bad\x1b"}]),
    ],
)
def test_the_schema_and_the_loader_agree_on_bad_packs(tmp_path, bad):
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
    with pytest.raises(ValueError, match=r"."):
        _load_dict(tmp_path, bad)


def test_the_schema_accepts_what_the_loader_accepts(tmp_path):
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(JSON_PACK, schema)
    _load_dict(tmp_path, JSON_PACK)
