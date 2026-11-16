"""Tests for the pack validator: base mode, strict mode and the probe-file check."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import validate_pack

KEY = "TEST_PACK"
SOURCE = {"kind": "attestation", "ref": f"{KEY}:1"}


def row(**over):
    base = {
        "title": "A title",
        "note": "Evidence that a thing is in place.",
        "default_ttl_days": 365,
        "sources": [dict(SOURCE)],
        "eu_ai_act": [],
        "source": "own reading",
        "confidence": "low",
        "needs_founder_review": True,
        "evidence_class": "organisational",
        "why_attestation": "A person has to confirm it.",
    }
    base.update(over)
    return base


def problems(r, *, strict=False, copyright_=None, rid=f"{KEY}:1", key=KEY, scope=None):
    return validate_pack.validate_rows(
        key,
        {rid: r},
        strict=strict,
        copyright_=copyright_,
        scope_keys=scope or {"trains_models"},
    )


def fires(text, r, **kw):
    found = problems(r, **kw)
    assert any(text in p for p in found), found


def test_clean_row_passes_both_modes():
    assert problems(row()) == []
    assert problems(row(), strict=True, copyright_="restricted") == []


def test_all_passes_in_base_mode(capsys):
    assert validate_pack.main(["--all"]) == 0
    assert capsys.readouterr().out.startswith("OK ")


def test_unknown_pack_and_eu_pack_are_reported():
    assert validate_pack.validate("NO_SUCH_PACK")
    assert validate_pack.validate("EU_AI_ACT")


def _write_pack(root: Path, rows: dict, copyright_="restricted") -> None:
    d = root / KEY
    d.mkdir(parents=True)
    (d / "requirements.json").write_text(json.dumps(rows), encoding="utf-8")
    (d / "pack.json").write_text(
        json.dumps({"id": KEY, "copyright": copyright_}), encoding="utf-8"
    )


def test_temp_pack_fails_strict_naming_missing_evidence_class(
    tmp_path, monkeypatch, capsys
):
    r = row()
    del r["evidence_class"], r["why_attestation"]
    _write_pack(tmp_path, {f"{KEY}:1": r})
    monkeypatch.setattr(validate_pack, "PACKS_DIR", tmp_path)
    assert validate_pack.validate(KEY) == []
    assert validate_pack.main([KEY, "--strict"]) == 1
    assert "evidence_class is required" in capsys.readouterr().out


def test_temp_pack_passes_strict_when_complete(tmp_path, monkeypatch):
    _write_pack(tmp_path, {f"{KEY}:1": row()})
    monkeypatch.setattr(validate_pack, "PACKS_DIR", tmp_path)
    assert validate_pack.validate(KEY, strict=True) == []


def test_bad_id():
    fires("id must be", row(), rid="OTHER:1")


def test_unknown_and_missing_fields():
    fires("unknown fields", row(extra=1))
    r = row()
    del r["source"]
    fires("missing", r)


def test_title_length_unless_public_domain():
    long = "x" * 81
    fires("title", row(title=long))
    assert problems(row(title=long), copyright_="public_domain") == []
    fires("title", row(title=" "))


def test_note_one_line():
    fires("note must be one", row(note="a\nb"))
    fires("note must be one", row(note=" "))


@pytest.mark.parametrize("ttl", [1, 364, "365"])
def test_ttl_values(ttl):
    fires("default_ttl_days", row(default_ttl_days=ttl))


@pytest.mark.parametrize("ttl", [30, 90, 180, 365, 730])
def test_ttl_allowed(ttl):
    assert problems(row(default_ttl_days=ttl)) == []


def test_attestation_rules():
    fires("exactly one attestation", row(sources=[]))
    fires("exactly one attestation", row(sources=[dict(SOURCE), dict(SOURCE)]))
    fires("must have ref", row(sources=[{"kind": "attestation", "ref": "x"}]))
    found = validate_pack.validate_rows(
        "NIST_AI_RMF", {"NIST_AI_RMF:1": row(sources=[])}, scope_keys=set()
    )
    assert not any("attestation" in p for p in found)


def test_source_kinds():
    for kind in ("rule", "obligation"):
        fires("not allowed", row(sources=[dict(SOURCE), {"kind": kind, "ref": "x"}]))
    fires("not allowed", row(sources=[dict(SOURCE), {"kind": "crosswalk", "ref": "x"}]))
    for kind in ("scan", "manifest", "record"):
        assert problems(row(sources=[dict(SOURCE), {"kind": kind, "ref": "x"}])) == []


def test_source_roles():
    art = {"kind": "artifact", "ref": "ai_threat_model"}
    assert problems(row(sources=[dict(SOURCE), {**art, "role": "supporting"}])) == []
    assert problems(row(sources=[dict(SOURCE), {**art, "role": "corroborating"}])) == []
    fires("role must be", row(sources=[dict(SOURCE), {**art, "role": "primary"}]))
    fires(
        "corroborating role only",
        row(
            sources=[
                dict(SOURCE),
                {"kind": "record", "ref": "x", "role": "corroborating"},
            ]
        ),
    )


def test_artifact_and_evaluator_refs():
    fires(
        "not a known probe",
        row(sources=[dict(SOURCE), {"kind": "artifact", "ref": "no_such_probe"}]),
    )
    fires(
        "EVALUATOR_REGISTRY",
        row(sources=[dict(SOURCE), {"kind": "evaluator", "ref": "NOPE"}]),
    )
    ok = row(
        sources=[dict(SOURCE), {"kind": "evaluator", "ref": "EVAL_ADVERSARIAL_V1"}]
    )
    assert problems(ok) == []


def test_scope_out_keys():
    fires("scope_out keys", row(scope_out=[["no_such_key"]]))
    assert problems(row(scope_out=[["trains_models"]])) == []


def test_links_resolve():
    fires("eu_ai_act entries", row(eu_ai_act=["Art. 999"]))
    fires("iso_27001 entries", row(iso_27001=["A.9.9"]))
    fires("iso_42001 entries", row(iso_42001=["Nope"]))
    fires("duplicate", row(nist_ai_rmf=["a", "a"]))
    fires("list of strings", row(soc2="CC1.1"))


def test_review_flags_are_not_cleared():
    fires("needs_founder_review", row(needs_founder_review=False))
    fires("review_ref", row(confidence="medium"))
    assert problems(row(confidence="medium", review_ref="REV-1")) == []


def test_new_field_types():
    fires("evidence_class must be", row(evidence_class="other"))
    fires("own_wording", row(own_wording="yes"))
    fires("why_attestation", row(why_attestation="a\nb"))


def test_strict_needs_note_and_class():
    r = row()
    del r["note"]
    fires("note is required", r, strict=True)
    assert problems(r) == []


def test_strict_restricted_wording():
    r = row(note="Plain wording.")
    fires("Evidence that", r, strict=True, copyright_="restricted")
    assert problems(r, strict=True, copyright_="public_domain") == []
    assert (
        problems({**r, "own_wording": True}, strict=True, copyright_="restricted") == []
    )


def test_strict_machine_needs_deciding_source():
    r = row(evidence_class="machine", sources=[dict(SOURCE)])
    fires("neither attestation nor supporting", r, strict=True)
    sup = {"kind": "artifact", "ref": "ai_threat_model", "role": "supporting"}
    fires(
        "neither attestation nor supporting",
        row(evidence_class="hybrid", sources=[dict(SOURCE), sup]),
        strict=True,
    )
    ok = row(
        evidence_class="hybrid",
        sources=[dict(SOURCE), {"kind": "artifact", "ref": "ai_threat_model"}],
    )
    assert problems(ok, strict=True) == []


def test_strict_organisational_why():
    r = row()
    del r["why_attestation"]
    fires("why_attestation", r, strict=True)
    fires("why_attestation", row(why_attestation="x" * 161), strict=True)
    assert problems(row(why_attestation="x" * 160), strict=True) == []


def test_strict_ttl_spread_over_ten_rows():
    rows = {
        f"{KEY}:{i}": row(sources=[{"kind": "attestation", "ref": f"{KEY}:{i}"}])
        for i in range(11)
    }
    found = validate_pack.validate_rows(KEY, rows, strict=True, scope_keys=set())
    assert any("two or more default_ttl_days" in p for p in found)
    rows[f"{KEY}:0"] = {**copy.deepcopy(rows[f"{KEY}:0"]), "default_ttl_days": 180}
    assert validate_pack.validate_rows(KEY, rows, strict=True, scope_keys=set()) == []
    assert validate_pack.validate_rows(KEY, rows, scope_keys=set()) == []


def test_strict_reports_a_broken_applicability_file(monkeypatch):
    def boom(key):
        raise ValueError("applicability.json: bad")

    monkeypatch.setattr(validate_pack.applicability, "declared_scope_keys", boom)
    found = validate_pack.validate("SOC_2", strict=True)
    assert any("applicability.json" in p for p in found)


def _probe_file(tmp_path, probes):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"family": "f", "probes": probes}), encoding="utf-8")
    return path


PROV = {"source": "own heuristic", "confidence": "low", "needs_founder_review": True}


def test_probe_file_checks(tmp_path):
    ok = {"a_probe": {"patterns": ["**/*.py"], "provenance": PROV}}
    assert validate_pack.validate_probe_file(_probe_file(tmp_path, ok)) == []
    no_prov = {"a_probe": {"patterns": ["**/*.py"]}}
    assert any(
        "provenance" in p
        for p in validate_pack.validate_probe_file(_probe_file(tmp_path, no_prov))
    )
    doc = {"a_probe": {"patterns": ["docs/plan.md"], "provenance": PROV}}
    assert any(
        "markers" in p
        for p in validate_pack.validate_probe_file(_probe_file(tmp_path, doc))
    )
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    assert validate_pack.validate_probe_file(bad)


def test_shipped_probe_file_is_valid(capsys):
    shipped = validate_pack.CORE / "probes/ai_security.json"
    assert validate_pack.main(["--probes", str(shipped)]) == 0


def test_nist_hybrid_rows_are_accepted_and_covered_by_all():
    assert "NIST_AI_RMF" in validate_pack.pack_keys()
    assert validate_pack.validate("NIST_AI_RMF") == []


def test_all_covers_a_pack_directory_with_a_requirements_file(
    tmp_path, monkeypatch, capsys
):
    key = validate_pack.NIST_KEY
    d = tmp_path / key
    d.mkdir()
    rid = f"{key}:GOVERN 1.1"
    crosswalk = {"kind": "crosswalk", "ref": rid}
    rows = {rid: row(sources=[crosswalk, {"kind": "attestation", "ref": rid}])}
    (d / "requirements.json").write_text(json.dumps(rows), encoding="utf-8")
    (d / "pack.json").write_text(
        json.dumps({"id": key, "copyright": "public_domain"}), encoding="utf-8"
    )
    monkeypatch.setattr(validate_pack, "PACKS_DIR", tmp_path)
    assert validate_pack.pack_keys() == [key]
    assert validate_pack.main(["--all"]) == 0
    assert capsys.readouterr().out.strip() == "OK 1 packs"
    rows[rid]["sources"][0]["ref"] = "other"
    (d / "requirements.json").write_text(json.dumps(rows), encoding="utf-8")
    assert validate_pack.main(["--all"]) == 1
    assert "crosswalk source must have ref" in capsys.readouterr().out
    rows[rid]["sources"] = [{"kind": "crosswalk", "ref": rid}]
    (d / "requirements.json").write_text(json.dumps(rows), encoding="utf-8")
    assert validate_pack.main(["--all"]) == 0


def test_pack_local_probe_file_takes_folder_prefix(tmp_path):
    probes = {"unit_pack.a_probe": {"patterns": ["**/*.py"], "provenance": PROV}}
    folder = tmp_path / "packs" / "UNIT_PACK"
    folder.mkdir(parents=True)
    local = folder / "probes.json"
    local.write_text(json.dumps({"family": "f", "probes": probes}), encoding="utf-8")
    assert validate_pack.validate_probe_file(local) == []
    assert validate_pack.validate_probe_file(_probe_file(tmp_path, probes))
