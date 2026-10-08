"""requirement_title: human text for native and derived framework rows."""

from pathlib import Path

from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack, requirement_title
from opencomplai_core.nist_ai_rmf_subcategories import get_subcategories

FIXTURE_PACK = FrameworkPack(
    "FIXTURE",
    "Fixture framework",
    requirements=Path(__file__).parent
    / "fixtures"
    / "framework_pack"
    / "requirements.json",
)


def test_nist_subcategory_has_title():
    title = requirement_title("NIST_AI_RMF:GOVERN 1.1")
    assert title
    assert title == get_subcategories()["GOVERN 1.1"].outcome


def test_unknown_id_returns_none():
    assert requirement_title("NIST_AI_RMF:NOPE 9.9") is None
    assert requirement_title("NOPE:REQ-1") is None
    assert requirement_title("FIXTURE:REQ-1") is None  # pack not registered


def test_native_pack_title_unchanged(monkeypatch):
    monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)
    assert requirement_title("FIXTURE:REQ-1") == "Risk register maintained"
