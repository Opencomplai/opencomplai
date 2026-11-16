from __future__ import annotations

from opencomplai_core.common_controls import build_common_controls
from opencomplai_core.frameworks import FrameworkPack


def _pack(key: str, reqs: dict) -> FrameworkPack:
    return FrameworkPack(key, key, requirements_data=reqs)


def _req(sources, title="T"):
    return {"title": title, "sources": sources}


def _packs():
    eu = _pack(
        "EU_AI_ACT",
        {
            "Art. 9": _req(
                [
                    {"kind": "attestation", "ref": "Art. 9"},
                    {"kind": "artifact", "ref": "risk_register", "role": "primary"},
                ]
            ),
        },
    )
    iso = _pack(
        "ISO_IEC_42001",
        {
            "ISO_IEC_42001:6.1": _req(
                [
                    {"kind": "attestation", "ref": "ISO_IEC_42001:6.1"},
                    {"kind": "artifact", "ref": "risk_register"},
                    {"kind": "scan", "ref": "scan.only_iso"},
                ]
            ),
            "ISO_IEC_42001:4.1": _req([{"kind": "artifact", "ref": "risk_register"}]),
        },
    )
    derived = FrameworkPack("DERIVED", "d")
    return {"EU_AI_ACT": eu, "ISO_IEC_42001": iso, "DERIVED": derived}


def test_shared_ref_is_one_control_with_two_frameworks():
    controls = build_common_controls(_packs())
    shared = [c for c in controls if c.ref == "risk_register"]
    assert len(shared) == 1
    c = shared[0]
    assert c.kind == "artifact"
    assert c.frameworks == ["EU_AI_ACT", "ISO_IEC_42001"]
    assert [(r.framework, r.requirement_id) for r in c.rows] == [
        ("EU_AI_ACT", "Art. 9"),
        ("ISO_IEC_42001", "ISO_IEC_42001:4.1"),
        ("ISO_IEC_42001", "ISO_IEC_42001:6.1"),
    ]
    assert c.rows[0].role == "primary"
    assert all(r.status is None for r in c.rows)
    assert c.credited_rows == 0


def test_attestation_sources_give_no_control():
    refs = {c.ref for c in build_common_controls(_packs())}
    assert refs == {"risk_register", "scan.only_iso"}


def test_custom_and_derived_packs_are_skipped():
    packs = _packs()
    packs["CUSTOM_X"] = _pack(
        "CUSTOM_X", {"CUSTOM_X:1": _req([{"kind": "scan", "ref": "c"}])}
    )
    assert "c" not in {c.ref for c in build_common_controls(packs)}


def test_ordering_is_stable():
    controls = build_common_controls(_packs())
    assert [c.ref for c in controls] == ["risk_register", "scan.only_iso"]
    assert controls == build_common_controls(dict(reversed(list(_packs().items()))))


def test_artifact_statuses_and_credited_rows():
    artifact = {
        "gap_report": {"articles": [{"article": "Art. 9", "status": "met"}]},
        "framework_reports": {
            "ISO_IEC_42001": {
                "report": {
                    "articles": [
                        {"article": "ISO_IEC_42001:6.1", "status": "missing"},
                        {"article": "ISO_IEC_42001:4.1", "status": "partial"},
                    ]
                }
            }
        },
    }
    controls = {c.ref: c for c in build_common_controls(_packs(), artifact)}
    shared = controls["risk_register"]
    assert {r.requirement_id: r.status for r in shared.rows} == {
        "Art. 9": "met",
        "ISO_IEC_42001:4.1": "partial",
        "ISO_IEC_42001:6.1": "missing",
    }
    assert shared.credited_rows == 2
    # The other control's row keeps its own verdict, not the shared one.
    assert controls["scan.only_iso"].rows[0].status == "missing"
    assert controls["scan.only_iso"].credited_rows == 0


def test_real_packs_smoke():
    controls = build_common_controls()
    assert controls
    counts = [len(c.frameworks) for c in controls]
    assert counts == sorted(counts, reverse=True)
    assert all(c.rows and c.credited_rows == 0 for c in controls)
    assert not any(f.startswith("CUSTOM_") for c in controls for f in c.frameworks)
