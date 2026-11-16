"""Tests for the parity check: a pass and a fail per decided capability."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import pack_doc
import parity_check as pc
import validate_pack
from opencomplai_core import pack_registry

KEY = "TEST_PACK"


def ctx(tmp_path: Path, **over) -> pc.Ctx:
    base = {"key": KEY, "pack_path": tmp_path / "pack", "golden": tmp_path / "golden"}
    base.update(over)
    (tmp_path / "pack").mkdir(parents=True, exist_ok=True)
    (tmp_path / "golden").mkdir(parents=True, exist_ok=True)
    return pc.Ctx(**base)


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def gaps(*rows, key: str = KEY) -> dict:
    return {"payload": {"frameworks": {key: {"report": {"articles": list(rows)}}}}}


# P1 ---------------------------------------------------------------------


APP = {
    "default": "applies",
    "questions": [],
    "outcomes": [{"when": {"a": True}, "outcome": "voluntary", "reason": "r"}],
}


def test_p1_passes_with_goldens_and_listed_files(tmp_path):
    c = ctx(tmp_path, applicability=APP, meta={"data_files": ["applicability.json"]})
    (c.pack_path / "applicability.json").write_text("{}")
    for outcome in ("applies", "voluntary"):
        write(c.golden / f"applicability_{outcome}.json", {})
    assert pc.check_p1(c)[0] == "pass"


def test_p1_fails_without_golden_for_an_outcome(tmp_path):
    c = ctx(tmp_path, applicability=APP)
    write(c.golden / "applicability_applies.json", {})
    result, detail = pc.check_p1(c)
    assert result == "fail"
    assert "voluntary" in detail


def test_p1_fails_when_a_present_file_is_not_listed(tmp_path):
    c = ctx(tmp_path, applicability={**APP, "outcomes": []}, meta={"data_files": []})
    (c.pack_path / "timeline.json").write_text("{}")
    write(c.golden / "applicability_applies.json", {})
    result, detail = pc.check_p1(c)
    assert result == "fail"
    assert "timeline.json" in detail


def test_p1_fails_without_file_or_when_unreadable(tmp_path):
    assert pc.check_p1(ctx(tmp_path))[0] == "fail"
    assert pc.check_p1(ctx(tmp_path, applicability_error="bad"))[0] == "fail"


# P2 ---------------------------------------------------------------------


def test_p2_no_scoped_rows_passes(tmp_path):
    assert pc.check_p2(ctx(tmp_path, rows={f"{KEY}:1": {}})) == (
        "pass",
        "no scoped rows",
    )


def test_p2_passes_when_a_golden_lists_an_exclusion(tmp_path):
    c = ctx(tmp_path, rows={f"{KEY}:1": {"scope_out": ["k"]}}, scope_keys={"k"})
    write(
        c.golden / "gaps_empty.json",
        gaps() | {"payload": {"frameworks": {KEY: {"excluded": {f"{KEY}:1": "why"}}}}},
    )
    assert pc.check_p2(c)[0] == "pass"


def test_p2_fails_on_undeclared_key_and_on_missing_exclusion(tmp_path):
    rows = {f"{KEY}:1": {"scope_out": [["k", "zz"]]}}
    result, detail = pc.check_p2(ctx(tmp_path, rows=rows, scope_keys={"k"}))
    assert result == "fail"
    assert "zz" in detail
    result, detail = pc.check_p2(
        ctx(tmp_path, rows={f"{KEY}:1": {"scope_out": ["k"]}}, scope_keys={"k"})
    )
    assert result == "fail"
    assert "excluded" in detail


# P3 and P7 ----------------------------------------------------------------


def test_p3_and_p7_read_only_their_own_problems(tmp_path):
    c = ctx(
        tmp_path,
        strict_problems=[
            "X: strict: evidence_class is required",
            "X: default_ttl_days must be one of",
        ],
    )
    assert pc.check_p3(c)[0] == "fail"
    assert pc.check_p7(c)[0] == "fail"
    assert (
        pc.check_p3(
            ctx(tmp_path, strict_problems=["X: default_ttl_days must be one of"])
        )[0]
        == "pass"
    )
    assert (
        pc.check_p7(
            ctx(tmp_path, strict_problems=["X: why_attestation must be one line"])
        )[0]
        == "pass"
    )
    assert pc.check_p3(ctx(tmp_path))[0] == pc.check_p7(ctx(tmp_path))[0] == "pass"


# P4 ---------------------------------------------------------------------


def machine_row(kind="evaluator", ref="ok"):
    return {
        "evidence_class": "machine",
        "sources": [{"kind": "attestation", "ref": "x"}, {"kind": kind, "ref": ref}],
    }


def test_p4_passes_at_target(tmp_path):
    rows = {f"{KEY}:{i}": machine_row() for i in range(3)} | {
        f"{KEY}:o": {"evidence_class": "organisational"}
    }
    c = ctx(tmp_path, rows=rows, meta={"target_machine_share": 3}, evaluators={"ok"})
    assert pc.check_p4(c)[0] == "pass"


def test_p4_share_floor_rounds_down_and_needs_a_note_below_target(tmp_path):
    rows = {f"{KEY}:{i}": machine_row() for i in range(8)}  # target 10: floor 8
    c = ctx(tmp_path, rows=rows, meta={"target_machine_share": 10}, evaluators={"ok"})
    result, detail = pc.check_p4(c)
    assert result == "fail"
    assert "machine_share_note" in detail
    c.meta["machine_share_note"] = "Two rows wait on a probe."
    assert pc.check_p4(c)[0] == "pass"
    rows.popitem()  # 7 < floor 8
    assert pc.check_p4(c)[0] == "fail"


def test_p4_fails_on_unresolved_or_missing_source(tmp_path):
    c = ctx(
        tmp_path,
        rows={f"{KEY}:1": machine_row(ref="nope")},
        meta={"target_machine_share": 1},
        evaluators={"ok"},
    )
    assert "does not resolve" in pc.check_p4(c)[1]
    row = {"evidence_class": "hybrid", "sources": [{"kind": "attestation", "ref": "x"}]}
    assert "no non-attestation" in pc.check_p4(ctx(tmp_path, rows={f"{KEY}:1": row}))[1]


# P5 ---------------------------------------------------------------------


def write_gaps(c, empty, scaffolded, evidenced):
    write(c.golden / "gaps_empty.json", gaps(*empty))
    write(c.golden / "gaps_scaffolded.json", gaps(*scaffolded))
    write(c.golden / "gaps_evidenced.json", gaps(*evidenced))


MISSING = {
    "article": "a",
    "status": "missing",
    "source": "attestation",
    "confidence": None,
}
LOW = {"article": "a", "status": "partial", "source": "artifact", "confidence": 0.35}
HIGH = {"article": "a", "status": "partial", "source": "artifact", "confidence": 0.6}


def test_p5_passes_on_confidence_and_on_corroborated_met(tmp_path):
    c = ctx(tmp_path)
    write_gaps(c, [MISSING], [LOW], [HIGH])
    assert pc.check_p5(c)[0] == "pass"
    met = {
        "article": "a",
        "status": "met",
        "source": "attestation",
        "corroborated": True,
    }
    write_gaps(c, [MISSING], [LOW], [met])
    assert pc.check_p5(c)[0] == "pass"


def test_p5_passes_on_scaffolded_rows_below_the_evidenced_level(tmp_path):
    c = ctx(tmp_path)
    missing = dict(LOW, status="missing", confidence=0.4)
    partial = dict(LOW, status="partial", confidence=0.55)
    write_gaps(c, [MISSING], [missing, partial], [HIGH])
    assert pc.check_p5(c)[0] == "pass"


def test_p5_fails_on_each_golden(tmp_path):
    c = ctx(tmp_path)
    assert "no golden" in pc.check_p5(c)[1]
    write_gaps(c, [LOW], [LOW], [HIGH])
    assert "no missing row" in pc.check_p5(c)[1]
    write_gaps(c, [MISSING], [dict(LOW, confidence=0.6)], [HIGH])
    assert "gaps_scaffolded" in pc.check_p5(c)[1]
    write_gaps(c, [MISSING], [LOW], [dict(HIGH, confidence=0.5)])
    assert "gaps_evidenced" in pc.check_p5(c)[1]


# whole tool -----------------------------------------------------------------


def test_all_fifteen_capabilities_are_decided():
    assert list(pc.CHECKS) == [f"P{n}" for n in range(1, 16)]
    assert not hasattr(pc, "_pending")


# P6, P8 to P14 -----------------------------------------------------------


def row(article="a", status="met"):
    return {"article": article, "status": status}


def put_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_p6_passes_on_verdict_words(tmp_path):
    c = ctx(tmp_path)
    for stem in pc.GAP_GOLDENS:
        write(
            c.golden / f"{stem}.json", gaps(row(status="Missing"), row("b", "partial"))
        )
    assert pc.check_p6(c)[0] == "pass"


def test_p6_fails_on_other_word_and_on_missing_file(tmp_path):
    c = ctx(tmp_path)
    write(c.golden / "gaps_empty.json", gaps(row(status="compliant")))
    result, detail = pc.check_p6(c)
    assert result == "fail"
    assert "compliant" in detail
    c2 = ctx(tmp_path / "x")
    assert pc.check_p6(c2) == ("fail", "no golden gaps_empty.json")


def test_p8_passes_on_failing_gate(tmp_path):
    c = ctx(tmp_path)
    put_text(c.golden / "gate_empty.txt", f"exit=1\n{KEY}:1 missing\n")
    assert pc.check_p8(c)[0] == "pass"


def test_p8_fails_on_exit_code_ids_and_missing_file(tmp_path):
    c = ctx(tmp_path)
    assert "gate_empty.txt" in pc.check_p8(c)[1]
    put_text(c.golden / "gate_empty.txt", f"exit=0\n{KEY}:1\n")
    assert pc.check_p8(c)[0] == "fail"
    put_text(c.golden / "gate_empty.txt", "exit=10\n" + f"{KEY}:1\n")
    assert pc.check_p8(c)[0] == "fail"
    put_text(c.golden / "gate_empty.txt", "exit=1\nnothing listed\n")
    assert pc.check_p8(c)[0] == "fail"


def write_reports(c, classname=KEY):
    put_text(
        c.golden / "check_reports.junit.xml",
        f'<testcase classname="opencomplai.{classname}"/>',
    )
    put_text(c.golden / "check_reports.sarif.json", "{}")
    put_text(c.golden / "check_reports.summary.md", "x")


def test_p9_passes_with_three_reports(tmp_path):
    c = ctx(tmp_path)
    write_reports(c)
    assert pc.check_p9(c)[0] == "pass"


def test_p9_fails_on_missing_report_or_classname(tmp_path):
    c = ctx(tmp_path)
    write_reports(c, "OTHER")
    assert pc.check_p9(c)[0] == "fail"
    (c.golden / "check_reports.sarif.json").unlink()
    result, detail = pc.check_p9(c)
    assert result == "fail"
    assert "check_reports.sarif.json" in detail


MACHINE_ROWS = {f"{KEY}:1": {"evidence_class": "machine"}, f"{KEY}:2": {}}


def test_p10_passes_with_template_files(tmp_path):
    c = ctx(tmp_path, rows=MACHINE_ROWS)
    write(
        c.pack_path / "templates" / "template_map.json", {f"{KEY}:1": {"file": "t.md"}}
    )
    put_text(c.pack_path / "templates" / "t.md", "x")
    assert pc.check_p10(c)[0] == "pass"


def test_p10_fails_on_missing_map_row_or_file(tmp_path):
    c = ctx(tmp_path, rows=MACHINE_ROWS)
    assert "template_map.json" in pc.check_p10(c)[1]
    assert pc.check_p10(c)[0] == "fail"
    write(c.pack_path / "templates" / "template_map.json", {})
    assert "not in template_map" in pc.check_p10(c)[1]
    write(
        c.pack_path / "templates" / "template_map.json", {f"{KEY}:1": {"file": "t.md"}}
    )
    assert "t.md" in pc.check_p10(c)[1]


def scaffold_pack(monkeypatch, tmp_path, docs, texts):
    packs = tmp_path / "packs"
    monkeypatch.setattr(pack_registry, "PACKS_DIR", packs)
    d = packs / KEY / "scaffolds"
    write(d / "scaffolds.json", docs)
    for name, text in texts.items():
        put_text(d / name, text)
    return pc.Ctx(key=KEY, pack_path=packs / KEY)


GOOD_PROBE = "provider_qms_17_1_a"


def test_p11_passes_with_resolving_documents(monkeypatch, tmp_path):
    c = scaffold_pack(
        monkeypatch,
        tmp_path,
        {"doc": {"file": "doc.md", "target": "doc.md", "probe": GOOD_PROBE}},
        {"doc.md": "# T\n_fill in_\n"},
    )
    assert pc.check_p11(c) == ("pass", "1 scaffold document(s) resolve")


def test_p11_fails_on_marker_probe_count_and_file(monkeypatch, tmp_path):
    entry = {"file": "doc.md", "target": "doc.md", "probe": "no-such-probe-ref"}
    c = scaffold_pack(monkeypatch, tmp_path, {"doc": entry}, {"doc.md": "no marker"})
    assert "marker" in pc.check_p11(c)[1]
    put_text(c.pack_path / "scaffolds" / "doc.md", "_fill in_")
    assert "probe" in pc.check_p11(c)[1]
    c = scaffold_pack(monkeypatch, tmp_path / "b", {"doc": entry}, {})
    assert "does not resolve" in pc.check_p11(c)[1]
    c = scaffold_pack(monkeypatch, tmp_path / "c", {}, {})
    assert pc.check_p11(c)[0] == "fail"
    assert pc.check_p11(ctx(tmp_path / "none"))[0] == "fail"


def timeline_pack(monkeypatch, tmp_path, meta, rows=None):
    packs = tmp_path / "packs"
    monkeypatch.setattr(pack_registry, "PACKS_DIR", packs)
    write(packs / KEY / "pack.json", meta)
    return pc.Ctx(key=KEY, pack_path=packs / KEY, meta=meta, rows=rows or {})


def none_meta(reason="No dated obligations apply."):
    return {
        "id": KEY,
        "order": 99,
        "kind": "native",
        "name": "n",
        "short_name": "n",
        "status": "s",
        "disclaimer_ref": "DISCLAIMER_V2",
        "requirements": "requirements.json",
        "data_files": [],
        "legacy_file": None,
        "copyright": "eu_law",
        "row_count": 1,
        "target_machine_share": 0,
        "timeline": "none",
        "timeline_reason": reason,
        "catalogue": True,
    }


def test_p12_passes_for_none_with_reason(monkeypatch, tmp_path):
    c = timeline_pack(
        monkeypatch, tmp_path, none_meta(), {f"{KEY}:1": {"note": "Evidence that x."}}
    )
    assert pc.check_p12(c)[0] == "pass"


def test_p12_fails_on_placeholder_dated_note_or_missing_file(monkeypatch, tmp_path):
    c = timeline_pack(monkeypatch, tmp_path, none_meta("not yet assessed"))
    assert pc.check_p12(c)[0] == "fail"
    for note in ("applies from 2027-01-02", "applies on 2 January 2027"):
        c = timeline_pack(
            monkeypatch, tmp_path, none_meta(), {f"{KEY}:1": {"note": note}}
        )
        assert "note holds a date" in pc.check_p12(c)[1]
    meta = {**none_meta(), "timeline": "file"}
    del meta["timeline_reason"]
    c = timeline_pack(monkeypatch, tmp_path, meta)
    result, detail = pc.check_p12(c)
    assert result == "fail"
    assert "timeline.json" in detail


def test_p13_passes_with_evidence_class(tmp_path):
    c = ctx(tmp_path)
    put_text(c.golden / "report_section.html", "<th>Evidence class</th>")
    assert pc.check_p13(c)[0] == "pass"


def test_p13_fails_without_text_or_file(tmp_path):
    c = ctx(tmp_path)
    assert "report_section.html" in pc.check_p13(c)[1]
    put_text(c.golden / "report_section.html", "<th>Class</th>")
    assert pc.check_p13(c)[0] == "fail"


def full_goldens(c):
    for stem in pc.GAP_GOLDENS:
        write(c.golden / f"{stem}.json", {})
        put_text(c.golden / f"{stem}.txt", "x")
    put_text(c.golden / "gate_empty.txt", "exit=1")
    write_reports(c)
    put_text(c.golden / "report_section.html", "x")
    c.fixtures.mkdir(parents=True, exist_ok=True)
    write(c.fixtures / "manifest.json", {})
    for d in ("empty", "scaffolded", "evidenced"):
        (c.fixtures / d).mkdir(exist_ok=True)


def test_p14_passes_with_everything_present(tmp_path):
    c = ctx(tmp_path, fixtures=tmp_path / "fixtures")
    full_goldens(c)
    assert pc.check_p14(c)[0] == "pass"


def test_p14_fails_naming_each_missing_entry(tmp_path):
    c = ctx(tmp_path, fixtures=tmp_path / "fixtures")
    full_goldens(c)
    (c.golden / "gaps_evidenced.txt").unlink()
    (c.fixtures / "manifest.json").unlink()
    result, detail = pc.check_p14(c)
    assert result == "fail"
    assert "gaps_evidenced.txt" in detail
    assert "manifest.json" in detail


def test_missing_inputs_fail_without_raising(tmp_path):
    c = ctx(tmp_path, fixtures=tmp_path / "nofixtures")
    for n in (6, 8, 9, 11, 13, 14):
        assert getattr(pc, f"check_p{n}")(c)[0] == "fail"
    assert pc.check_p10(ctx(tmp_path, rows=MACHINE_ROWS))[0] == "fail"


# whole tool -----------------------------------------------------------------


def temp_pack(monkeypatch, tmp_path):
    packs = tmp_path / "packs"
    pack = packs / KEY
    pack.mkdir(parents=True)
    meta = {
        "id": KEY,
        "order": 99,
        "kind": "native",
        "name": "n",
        "short_name": "n",
        "status": "s",
        "disclaimer_ref": "DISCLAIMER_V2",
        "requirements": "requirements.json",
        "data_files": [],
        "legacy_file": None,
        "copyright": "eu_law",
        "row_count": 1,
        "target_machine_share": 0,
        "timeline": "none",
        "catalogue": True,
    }
    write(pack / "pack.json", meta)
    row = {
        "title": "T",
        "note": "Evidence that x.",
        "default_ttl_days": 365,
        "sources": [{"kind": "attestation", "ref": f"{KEY}:1"}],
        "eu_ai_act": [],
        "source": "own",
        "confidence": "low",
        "needs_founder_review": True,
    }
    write(pack / "requirements.json", {f"{KEY}:1": row})
    monkeypatch.setattr(pack_registry, "PACKS_DIR", packs)
    monkeypatch.setattr(validate_pack, "PACKS_DIR", packs)
    return pack


def test_temp_pack_without_evidence_class_fails_p3(monkeypatch, tmp_path, capsys):
    temp_pack(monkeypatch, tmp_path)
    report = pc.run(KEY)
    assert report["capabilities"]["P3"]["result"] == "fail"
    assert report["rows"] == 1
    assert report["organisational"] == 1
    assert pc.main([KEY, "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["capabilities"]["P3"]["result"] == "fail"


def test_text_output_has_a_line_per_capability(monkeypatch, tmp_path, capsys):
    temp_pack(monkeypatch, tmp_path)
    assert pc.main([KEY]) == 1
    lines = capsys.readouterr().out.strip().splitlines()
    assert [ln.split()[0] for ln in lines] == [f"P{n}" for n in range(1, 16)]
    assert all(ln.split()[1] in ("pass", "fail", "pending") for ln in lines)


def test_all_json_is_a_list(monkeypatch, tmp_path, capsys):
    temp_pack(monkeypatch, tmp_path)
    assert pc.main(["--all", "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert [r["key"] for r in out] == [KEY]


def test_reference_pack_exits_zero(capsys):
    assert pc.main(["EU_AI_ACT"]) == 0
    assert "reference pack" in capsys.readouterr().out


def test_unknown_pack_exits_two(capsys):
    assert pc.main(["NO_SUCH_PACK"]) == 2


def test_no_argument_is_a_usage_error():
    with pytest.raises(SystemExit):
        pc.main([])


# P15 and the status ----------------------------------------------------------

PAGE = "frameworks/test-pack.md"


def docs_pack(monkeypatch, tmp_path, page_text=None, nav=""):
    pack = temp_pack(monkeypatch, tmp_path)
    docs = tmp_path / "docs"
    monkeypatch.setattr(pack_doc, "DOCS_SRC", docs / "src")
    monkeypatch.setattr(pc, "MKDOCS", docs / "mkdocs.yml")
    (docs).mkdir()
    (docs / "mkdocs.yml").write_text(nav, encoding="utf-8")
    if page_text is not None:
        page = docs / "src" / PAGE
        page.parent.mkdir(parents=True)
        page.write_text(page_text, encoding="utf-8")
    return pack


def p15(gate=False):
    return pc.check_p15(pc.load_ctx(KEY, gate))


def test_p15_passes_for_a_current_page(monkeypatch, tmp_path):
    docs_pack(monkeypatch, tmp_path, "# T\n<!-- rows:start -->\n<!-- rows:end -->\n")
    assert p15()[0] == "fail"  # stale until filled
    assert pack_doc.main([KEY]) == 0
    assert p15()[0] == "pass"


def test_p15_fails_without_page_or_markers(monkeypatch, tmp_path):
    docs_pack(monkeypatch, tmp_path)
    result, detail = p15()
    assert result == "fail"
    assert PAGE in detail
    docs_pack(monkeypatch, tmp_path / "b", "# no markers\n")
    assert p15()[0] == "fail"


def test_p15_gate_needs_the_nav_entry(monkeypatch, tmp_path):
    docs_pack(monkeypatch, tmp_path, "<!-- rows:start -->\n<!-- rows:end -->\n")
    pack_doc.main([KEY])
    assert p15(gate=True)[0] == "fail"
    pc.MKDOCS.write_text(f"nav:\n  - T: {PAGE}\n", encoding="utf-8")
    assert p15(gate=True)[0] == "pass"


def test_docs_page_field_overrides_the_default(monkeypatch, tmp_path):
    pack = docs_pack(monkeypatch, tmp_path)
    meta = json.loads((pack / "pack.json").read_text())
    meta["docs_page"] = "other/page.md"
    write(pack / "pack.json", meta)
    assert pack_doc.docs_page(KEY) == "other/page.md"


def stub_all_pass(monkeypatch):
    monkeypatch.setattr(
        pc, "CHECKS", {f"P{n}": (lambda _c: ("pass", "ok")) for n in range(1, 16)}
    )


def status_of(pack: Path) -> str:
    return json.loads((pack / "pack.json").read_text())["status"]


def test_write_status_sets_evaluated_when_all_pass(monkeypatch, tmp_path):
    pack = temp_pack(monkeypatch, tmp_path)
    stub_all_pass(monkeypatch)
    assert pc.main([KEY, "--write-status"]) == 0
    assert status_of(pack) == "evaluated"
    text = (pack / "pack.json").read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert text.startswith('{\n  "id": "TEST_PACK",')
    assert list(json.loads(text))[:3] == ["id", "order", "kind"]


def test_write_status_reverts_a_failing_evaluated_pack(monkeypatch, tmp_path):
    pack = temp_pack(monkeypatch, tmp_path)
    meta = json.loads((pack / "pack.json").read_text())
    write(pack / "pack.json", {**meta, "status": "evaluated"})
    assert pc.main([KEY, "--write-status"]) == 1
    assert status_of(pack) == "attestation-led"


def test_write_status_reverts_nist_to_derived(monkeypatch, tmp_path):
    pack = temp_pack(monkeypatch, tmp_path)
    meta = json.loads((pack / "pack.json").read_text())
    report = {"capabilities": {"P1": {"result": "fail", "detail": "x"}}}
    nist = pack.parent / "NIST_AI_RMF"
    nist.mkdir()
    write(nist / "pack.json", {**meta, "id": "NIST_AI_RMF", "status": "evaluated"})
    assert pc.write_status("NIST_AI_RMF", report) == "derived"


def test_write_status_leaves_other_statuses_alone(monkeypatch, tmp_path):
    pack = temp_pack(monkeypatch, tmp_path)
    assert pc.main([KEY, "--write-status"]) == 1
    assert status_of(pack) == "s"


def test_write_status_never_writes_the_eu_pack(monkeypatch, tmp_path):
    pack = temp_pack(monkeypatch, tmp_path)
    eu = pack.parent / pc.EU_KEY
    eu.mkdir()
    meta = json.loads((pack / "pack.json").read_text())
    write(eu / "pack.json", {**meta, "id": pc.EU_KEY, "status": "reference"})
    before = (eu / "pack.json").read_bytes()
    clean = {"capabilities": {"P1": {"result": "pass", "detail": "ok"}}}
    assert pc.write_status(pc.EU_KEY, clean) is None
    assert pc.main([pc.EU_KEY, "--write-status"]) == 0
    stub_all_pass(monkeypatch)
    assert pc.main(["--all", "--write-status"]) == 0
    assert (eu / "pack.json").read_bytes() == before
    assert status_of(pack) == "evaluated"


def test_gate_flag_works_with_all(monkeypatch, tmp_path, capsys):
    docs_pack(monkeypatch, tmp_path, "<!-- rows:start -->\n<!-- rows:end -->\n")
    pack_doc.main([KEY])
    assert pc.main(["--all", "--gate", "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out[0]["capabilities"]["P15"]["result"] == "fail"
