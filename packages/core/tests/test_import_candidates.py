"""Import candidates: pure function over ImportRef lists, no scan."""

from __future__ import annotations

from opencomplai_core.models import (
    CANDIDATE_REASON_IMPORTED_NOT_CLASSIFIED,
    EvidenceScope,
)
from opencomplai_core.scanner.feature_types import ImportRef
from opencomplai_core.scanner.import_candidates import (
    EXTRA_LIBRARIES,
    candidate_modules,
    find_import_candidates,
)

_NAMED = ("retinaface", "cv2", "dlib", "mtcnn", "facenet_pytorch", "mediapipe")


def _ref(module: str, location: str = "src/a.py:1", scope=EvidenceScope.PROD):
    return ImportRef(module=module, location=location, scope=scope)


def test_named_libraries_are_candidates():
    refs = [_ref(m, f"src/{m}.py:1") for m in _NAMED]
    got = find_import_candidates(refs, set())
    assert sorted(c.library for c in got) == sorted(_NAMED)
    assert {c.reason for c in got} == {CANDIDATE_REASON_IMPORTED_NOT_CLASSIFIED}


def test_dotted_and_from_imports_match_root_module():
    refs = [
        _ref("cv2.dnn", "src/a.py:3"),
        _ref("facenet_pytorch.models.mtcnn", "src/b.py:2"),
    ]
    got = find_import_candidates(refs, set())
    assert [(c.library, c.file, c.line) for c in got] == [
        ("cv2", "src/a.py", 3),
        ("facenet_pytorch", "src/b.py", 2),
    ]


def test_non_prod_scope_yields_nothing():
    for scope in EvidenceScope:
        if scope == EvidenceScope.PROD:
            continue
        assert find_import_candidates([_ref("cv2", scope=scope)], set()) == []


def test_location_with_finding_is_not_candidate():
    refs = [_ref("face_recognition", "src/a.py:1"), _ref("cv2", "src/a.py:2")]
    got = find_import_candidates(refs, {"src/a.py:1"})
    assert [c.library for c in got] == ["cv2"]
    assert find_import_candidates(refs, {"src/a.py:1", "src/a.py:2"}) == []


def test_one_candidate_per_library_per_file_lowest_line():
    refs = [
        _ref("cv2", "src/a.py:9"),
        _ref("cv2.dnn", "src/a.py:4"),
        _ref("cv2", "src/b.py:7"),
        _ref("dlib", "src/a.py:6"),
    ]
    got = find_import_candidates(refs, set())
    assert [(c.library, c.file, c.line) for c in got] == [
        ("cv2", "src/a.py", 4),
        ("dlib", "src/a.py", 6),
        ("cv2", "src/b.py", 7),
    ]


def test_look_alike_module_is_not_candidate():
    refs = [_ref(m) for m in ("cv2_utils", "mydlib", "retinaface_helpers")]
    assert find_import_candidates(refs, set()) == []


def test_malformed_location_is_skipped():
    refs = [
        _ref("cv2", "src/a.py"),
        _ref("cv2", "src/a.py:x"),
        _ref("cv2", "src/a.py:0"),
        _ref("cv2", ""),
        _ref("cv2", ":5"),
        _ref("dlib", "src/ok.py:2"),
    ]
    got = find_import_candidates(refs, set())
    assert [(c.library, c.file, c.line) for c in got] == [("dlib", "src/ok.py", 2)]


def test_output_is_sorted():
    refs = [
        _ref("dlib", "src/z.py:1"),
        _ref("mtcnn", "src/a.py:5"),
        _ref("cv2", "src/a.py:5"),
        _ref("retinaface", "src/a.py:2"),
    ]
    got = find_import_candidates(refs, set())
    assert [(c.file, c.line, c.library) for c in got] == [
        ("src/a.py", 2, "retinaface"),
        ("src/a.py", 5, "cv2"),
        ("src/a.py", 5, "mtcnn"),
        ("src/z.py", 1, "dlib"),
    ]


def test_every_library_record_carries_source_confidence_review():
    mods = candidate_modules()
    assert {lib.module for lib in EXTRA_LIBRARIES} == set(_NAMED)
    for name in _NAMED:
        assert mods[name].source == "candidate vocabulary; public issue 90"
    dictionary_derived = [m for m in mods.values() if m.module not in _NAMED]
    assert dictionary_derived
    for rec in mods.values():
        assert rec.source
        assert rec.confidence == "medium"
        assert rec.needs_founder_review is True
    assert all(m.source == "ai_signals.json#biometric" for m in dictionary_derived)
    # retinaface is both an extra and a dictionary token: the extra wins.
    assert mods["retinaface"].source == "candidate vocabulary; public issue 90"
