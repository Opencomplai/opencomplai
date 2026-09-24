"""Conformance tests for the framework pack registry.

Every registered pack, plus the test-only FIXTURE pack, must be well formed:
exactly one of requirements/derive, prefixed ids outside the EU AI Act,
known source kinds and refs, and a stable data_version. Also covers the
registry helpers framework_of and resolve_targets.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from opencomplai_core.compliance_checker.catalog import load_obligations
from opencomplai_core.evaluators.registry import EVALUATOR_REGISTRY
from opencomplai_core.frameworks import (
    EU_AI_ACT,
    FRAMEWORKS,
    FrameworkPack,
    data_version,
    framework_of,
    load_requirements_map,
    resolve_targets,
)
from opencomplai_core.gap_probes import _PROBE_PATTERNS
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import SignalCategory, SystemManifest
from opencomplai_core.rules import RULE_REGISTRY

FIXTURE_REQUIREMENTS = (
    Path(__file__).parent / "fixtures" / "framework_pack" / "requirements.json"
)
FIXTURE_PACK = FrameworkPack(
    "FIXTURE", "Fixture framework", requirements=FIXTURE_REQUIREMENTS
)

ALL_PACKS = [*FRAMEWORKS.values(), FIXTURE_PACK]

EU_ONLY_KINDS = {"rule", "obligation"}
NATIVE_KINDS = {"artifact", "attestation", "scan", "evaluator"}


def _known_refs() -> dict[str, set[str]]:
    return {
        "artifact": set(_PROBE_PATTERNS),
        "scan": {c.value for c in SignalCategory},
        "evaluator": {e.evaluator_id for e in EVALUATOR_REGISTRY},
        "rule": {r.rule_id for r in RULE_REGISTRY},
        "obligation": set(load_obligations()),
    }


@pytest.mark.parametrize("pack", ALL_PACKS, ids=lambda p: p.id)
def test_pack_is_native_or_derived_not_both(pack: FrameworkPack):
    assert (pack.requirements is None) != (pack.derive is None)
    assert pack.label.strip()


def test_registry_keys_match_pack_ids():
    assert all(key == pack.id for key, pack in FRAMEWORKS.items())
    assert FRAMEWORKS[EU_AI_ACT].disclaimer_ref == "DISCLAIMER_V1"
    assert FRAMEWORKS["NIST_AI_RMF"].disclaimer_ref == "DISCLAIMER_V2"


@pytest.mark.parametrize(
    "pack", [p for p in ALL_PACKS if p.requirements is not None], ids=lambda p: p.id
)
def test_native_requirements_are_well_formed(pack: FrameworkPack):
    requirements = load_requirements_map(pack.requirements)
    assert requirements
    known = _known_refs()
    is_eu = pack.id == EU_AI_ACT
    for rid, config in requirements.items():
        if is_eu:
            assert ":" not in rid
        else:
            assert rid.startswith(f"{pack.id}:")
            assert len(rid) > len(pack.id) + 1
            assert isinstance(config["title"], str)
            assert config["title"].strip()
            ttl = config["default_ttl_days"]
            assert ttl is None or (isinstance(ttl, int) and ttl > 0)
            assert config["sources"], f"{rid} has no sources"
        for source in config["sources"]:
            kind, ref = source["kind"], source["ref"]
            allowed = NATIVE_KINDS | EU_ONLY_KINDS if is_eu else NATIVE_KINDS
            assert kind in allowed, f"{rid}: kind {kind!r}"
            assert not (is_eu and kind == "attestation")
            if kind == "attestation":
                # The attestation is looked up by the requirement's own id.
                assert ref == rid
            else:
                assert ref in known[kind], f"{rid}: unknown {kind} ref {ref!r}"


@pytest.mark.parametrize(
    "pack", [p for p in ALL_PACKS if p.derive is not None], ids=lambda p: p.id
)
def test_derived_rows_are_prefixed(pack: FrameworkPack):
    derived = pack.derive(build_gap_report("sys", "HEAD"))
    assert derived.articles
    assert all(row.article.startswith(f"{pack.id}:") for row in derived.articles)
    assert len({row.article for row in derived.articles}) == len(derived.articles)
    assert all(path.is_file() for path in pack.data_files)


@pytest.mark.parametrize("pack", ALL_PACKS, ids=lambda p: p.id)
def test_data_version_is_a_stable_short_hash(pack: FrameworkPack):
    version = data_version(pack)
    assert version == data_version(pack)
    assert re.fullmatch(r"[0-9a-f]{12}", version)


def test_data_version_ignores_line_endings_and_changes_with_content(tmp_path: Path):
    text = FIXTURE_REQUIREMENTS.read_text(encoding="utf-8").replace("\r\n", "\n")
    crlf = tmp_path / "crlf.json"
    crlf.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    edited = tmp_path / "edited.json"
    edited.write_text(text.replace("Risk register", "Risk log"), encoding="utf-8")

    base = data_version(FIXTURE_PACK)
    assert data_version(FrameworkPack("FIXTURE", "x", requirements=crlf)) == base
    assert data_version(FrameworkPack("FIXTURE", "x", requirements=edited)) != base


def test_data_version_ignores_key_order(tmp_path: Path):
    parsed = json.loads(FIXTURE_REQUIREMENTS.read_text(encoding="utf-8"))
    reordered = tmp_path / "reordered.json"
    reordered.write_text(
        json.dumps(
            {rid: dict(reversed(c.items())) for rid, c in reversed(parsed.items())}
        ),
        encoding="utf-8",
    )
    assert list(json.loads(reordered.read_text(encoding="utf-8"))) != list(parsed)
    assert data_version(
        FrameworkPack("FIXTURE", "x", requirements=reordered)
    ) == data_version(FIXTURE_PACK)


def test_registry_data_versions_differ():
    assert data_version(FRAMEWORKS[EU_AI_ACT]) != data_version(
        FRAMEWORKS["NIST_AI_RMF"]
    )


@pytest.mark.parametrize(
    ("requirement_id", "framework"),
    [
        ("Art. 9", EU_AI_ACT),
        ("Art. 17(1)(a)", EU_AI_ACT),
        ("NIST_AI_RMF:GOVERN 1.1", "NIST_AI_RMF"),
        ("FIXTURE:REQ-1", "FIXTURE"),
    ],
)
def test_framework_of(requirement_id: str, framework: str):
    assert framework_of(requirement_id) == framework


def _manifest(**overrides: object) -> SystemManifest:
    return SystemManifest(
        system_id="sys", intended_purpose="credit scoring", **overrides
    )


def test_resolve_targets_cli_flags_replace_the_manifest():
    manifest = _manifest(compliance_targets=["NIST_AI_RMF"])
    assert resolve_targets(manifest, [EU_AI_ACT]) == [EU_AI_ACT]


def test_resolve_targets_prefers_compliance_targets_over_compliance_target():
    manifest = _manifest(
        compliance_target="NIST_AI_RMF", compliance_targets=[EU_AI_ACT, "NIST_AI_RMF"]
    )
    assert resolve_targets(manifest, None) == [EU_AI_ACT, "NIST_AI_RMF"]
    assert resolve_targets(manifest, []) == [EU_AI_ACT, "NIST_AI_RMF"]


@pytest.mark.parametrize("target", [EU_AI_ACT, "NIST_AI_RMF"])
def test_resolve_targets_falls_back_to_compliance_target(target: str):
    assert resolve_targets(_manifest(compliance_target=target)) == [target]


def test_resolve_targets_drops_duplicates_in_order():
    manifest = _manifest(compliance_targets=["NIST_AI_RMF", EU_AI_ACT, "NIST_AI_RMF"])
    assert resolve_targets(manifest) == ["NIST_AI_RMF", EU_AI_ACT]


def test_resolve_targets_rejects_unknown_frameworks():
    with pytest.raises(ValueError, match="ISO_42001"):
        resolve_targets(_manifest(compliance_targets=["ISO_42001"]))
    with pytest.raises(ValueError, match="FIXTURE"):
        resolve_targets(_manifest(), ["FIXTURE"])


def test_resolve_targets_accepts_a_registered_fixture_pack(monkeypatch):
    monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)
    assert resolve_targets(_manifest(), [EU_AI_ACT, "FIXTURE"]) == [
        EU_AI_ACT,
        "FIXTURE",
    ]
