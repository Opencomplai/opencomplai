"""Golden statuses for recorded attestations.

``fixtures/attestation_golden_statuses.json`` holds what the engine says about a fixed set of recorded
attestations (active, draft, revoked, expired, not applicable, organisation-wide and for one
system, on rows an attestation alone decides and on rows a scan also decides), plus the ids that
only an attestation can decide. A second implementation of the status rule that cannot import
the engine is held to the same file.

This test regenerates the file in memory (``scripts/generate_attestation_golden.py``) and fails when
the committed copy differs, so the file can only change together with the engine. It also states
the expected statuses outright, so a regenerated file that changed them cannot pass unnoticed.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from opencomplai_core.frameworks import (
    FRAMEWORKS,
    attestable_ids,
    attestation_only_ids,
)

FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "attestation_golden_statuses.json"
)
SCRIPT = (
    Path(__file__).resolve().parents[3] / "scripts" / "generate_attestation_golden.py"
)

_spec = importlib.util.spec_from_file_location("generate_attestation_golden", SCRIPT)
assert _spec is not None
assert _spec.loader is not None
generator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generator)

EXPECTED = {
    "active": "met",
    "last-good-day": "met",
    "expired-before-issue": "unverified",
    "expired-after-issue": "unverified",
    "draft": "unverified",
    "revoked": "unverified",
    "not-applicable": "excluded",
    "system-record-beats-organisation": "met",
    "draft-does-not-hide-active": "met",
    "other-systems-record": "unverified",
    "system-record-only": "met",
    "no-record": "unverified",
    "eu-art-4": "met",
    "mixed-evaluator-fails": "missing",
    "mixed-evaluator-silent": "met",
    "mixed-not-applicable": "unverified",
    "mixed-artifact-no-record": "unverified",
    "mixed-eu-article": "unverified",
}


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return data


def test_committed_fixture_is_what_the_engine_gives_now(golden: dict[str, Any]) -> None:
    assert golden == json.loads(generator.render()), (
        "attestation_golden_statuses.json is stale: run `python scripts/generate_attestation_golden.py` "
        "and commit the result"
    )


def test_generating_twice_gives_the_same_bytes() -> None:
    assert generator.render() == generator.render()


def test_expected_statuses_are_stated_outright(golden: dict[str, Any]) -> None:
    assert {r["case"]: r["engine_status"] for r in golden["rows"]} == EXPECTED


def test_the_record_the_engine_cites_is_the_one_a_system_should_see(
    golden: dict[str, Any],
) -> None:
    cited = {r["case"]: r["engine_record_id"] for r in golden["rows"]}
    assert cited["system-record-beats-organisation"] == "rec-system"
    assert cited["draft-does-not-hide-active"] == "rec-organisation-active"
    assert (
        cited["expired-after-issue"] == "rec-expired-after-issue"
    )  # judged expired on the day
    assert [cited[c] for c in ("draft", "revoked", "other-systems-record")] == [
        None
    ] * 3


def test_the_bundle_holds_only_what_an_issuer_ships(golden: dict[str, Any]) -> None:
    bundle = golden["bundle"]
    shipped = {
        rec["record_id"]
        for rows in bundle["attestations"].values()
        for rec in rows.values()
    }
    assert shipped.isdisjoint(
        {
            "rec-draft",
            "rec-revoked",
            "rec-other-system",
            "rec-system-draft",
            "rec-organisation",
        }
    )
    assert "rec-expired-before-issue" not in shipped
    assert {"rec-expired-after-issue", "rec-last-good-day", "rec-art-4"} <= shipped
    assert bundle["excluded"]["SOC_2"] == {"SOC_2:CC1.1": "The company has no office."}
    assert (
        "Art. 4" in bundle["attestations"]["EU_AI_ACT"]
    )  # the engine's spelling, no prefix


def test_no_email_reaches_the_bundle(golden: dict[str, Any]) -> None:
    assert "@" not in json.dumps(golden["bundle"])
    assert all("@" not in r["attested_by"] for r in golden["records"])


def test_attestation_only_ids_are_the_engines_for_every_pack(
    golden: dict[str, Any],
) -> None:
    native = [fw for fw, pack in FRAMEWORKS.items() if pack.requirements is not None]
    assert list(golden["attestation_only"]) == native
    for fw in native:
        assert golden["attestation_only"][fw] == sorted(attestation_only_ids(fw)), fw
    assert golden["attestation_only"]["EU_AI_ACT"] == ["Art. 4"]
    packs = sum(
        len(v) for fw, v in golden["attestation_only"].items() if fw != "EU_AI_ACT"
    )
    assert packs == 557


def test_mixed_rows_are_attestable_but_not_attestation_only(
    golden: dict[str, Any],
) -> None:
    mixed = golden["mixed_attestable"]
    assert sum(len(v) for v in mixed.values()) == 8
    assert "EU_AI_ACT" not in mixed  # an EU article but Art. 4 takes no attestation
    for fw, ids in mixed.items():
        assert ids == sorted(attestable_ids(fw) - attestation_only_ids(fw)), fw
