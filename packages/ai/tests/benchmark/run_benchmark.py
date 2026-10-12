"""Measure how well the deterministic code signals point to an Annex III area.

Two paths are measured over the labelled fixtures in ``fixtures.py``:

* intent path: ``run_scan(..., ai_intent=True, ai_model="codebert-onnx")``, the path
  behind ``scan --ai-intent``; a project is predicted for an area when any call
  site yields a high-risk finding for it.
* default scan path: ``run_scan`` without intent analysis, read from
  ``report.detected_categories``, the path ``check --scan`` compares with the
  declared purpose.

Everything is offline: the matcher is deterministic and downloads no model.

Run from a source checkout: ``python packages/ai/tests/benchmark/run_benchmark.py``
"""

from __future__ import annotations

import contextlib
import importlib.util
import tempfile
import time
import warnings
from pathlib import Path

from opencomplai_ai.knowledge.annex_iii import lookup_by_area
from opencomplai_core.scan_engine import run_scan
from opencomplai_core.scanner.mapping import _AREA_TO_TAXONOMY

AREAS = tuple(range(1, 9))
_TAXONOMY_TO_AREA = {key: area for area, key in _AREA_TO_TAXONOMY.items()}


def _load_fixtures() -> list[dict]:
    path = Path(__file__).resolve().parent / "fixtures.py"
    spec = importlib.util.spec_from_file_location("annex_iii_benchmark_fixtures", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FIXTURES


def _scan_fixture(fixture: dict) -> tuple[list[int], bool, list[int]]:
    """Return (intent areas, art5 flag, default-scan areas) for one fixture."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in fixture["files"].items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        # Finding locations are relative to the scan root and the snippet reader
        # opens them relative to the working directory, so scan from the root as a
        # developer does in a checkout; otherwise the matcher sees no code at all.
        with contextlib.chdir(root):
            return _scan_root(fixture["name"], root, fixture["purpose"])


def _scan_root(
    name: str, root: Path, purpose: str
) -> tuple[list[int], bool, list[int]]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report = run_scan(
            name, "HEAD", root, purpose, ai_intent=True, ai_model="codebert-onnx"
        )
    failed = [str(w.message) for w in caught]
    failed = [m for m in failed if m.startswith("AI intent analysis")]
    if failed or report.eu_ai_scan is None:
        raise RuntimeError(
            f"intent analysis did not run for {name}: {failed or 'no eu_ai_scan'}"
        )
    intent = sorted(
        {
            f.annex_iii_area
            for f in report.eu_ai_scan.high_risk
            if f.annex_iii_area is not None
        }
    )
    art5 = bool(report.eu_ai_scan.prohibited)

    scan_report = run_scan(name, "HEAD", root, purpose)
    if scan_report.scan_errors or scan_report.detector_errors:
        raise RuntimeError(
            f"incomplete default scan for {name}: "
            f"{scan_report.scan_errors} {scan_report.detector_errors}"
        )
    scan = sorted(
        {
            _TAXONOMY_TO_AREA[c]
            for c in scan_report.detected_categories
            if c in _TAXONOMY_TO_AREA
        }
    )
    return intent, art5, scan


def _tally(rows: list[tuple[str, int | None, list[int]]]) -> dict:
    per_area = {a: {"fixtures": 0, "tp": 0, "fp": 0, "fn": 0} for a in AREAS}
    misses, spurious = [], []
    for name, label, predicted in rows:
        if label is not None:
            per_area[label]["fixtures"] += 1
        for area in AREAS:
            if area in predicted:
                per_area[area]["tp" if label == area else "fp"] += 1
            elif label == area:
                per_area[area]["fn"] += 1
        if label is not None and label not in predicted:
            misses.append(f"{name}: {label} -> {predicted}")
        if set(predicted) - {label}:
            spurious.append(f"{name}: {label} -> {predicted}")
    overall = {k: sum(per_area[a][k] for a in AREAS) for k in ("tp", "fp", "fn")}
    none_clean = sum(1 for _, label, pred in rows if label is None and not pred)
    return {
        "per_area": per_area,
        "overall": overall,
        "none_clean": none_clean,
        "misses": misses,
        "spurious": spurious,
    }


def measure(fixtures: list[dict] | None = None) -> dict:
    """Run both paths over the fixtures and return counts and predictions."""
    fixtures = _load_fixtures() if fixtures is None else fixtures
    started = time.monotonic()
    predictions: dict[str, dict] = {}
    art5_names: list[str] = []
    intent_rows, scan_rows = [], []
    for fx in fixtures:
        intent, art5, scan = _scan_fixture(fx)
        predictions[fx["name"]] = {"intent": intent, "scan": scan}
        if art5:
            art5_names.append(fx["name"])
        intent_rows.append((fx["name"], fx["area"], intent))
        scan_rows.append((fx["name"], fx["area"], scan))

    intent_t, scan_t = _tally(intent_rows), _tally(scan_rows)
    result = {
        "fixtures": len(fixtures),
        "predictions": predictions,
        "none_fixtures": sum(1 for fx in fixtures if fx["area"] is None),
        "art5_on_non_art5": len(art5_names),
        "art5_names": art5_names,
        "elapsed_s": round(time.monotonic() - started, 2),
    }
    for key, value in intent_t.items():
        result[key] = value
    for key, value in scan_t.items():
        result[f"scan_{key}"] = value
    return result


def _pct(num: int, den: int) -> str:
    return "n/a" if den == 0 else f"{100 * num / den:.1f}%"


def _row(label: str, name: str, fixtures: int, c: dict) -> str:
    precision = _pct(c["tp"], c["tp"] + c["fp"])
    recall = _pct(c["tp"], c["tp"] + c["fn"])
    return (
        f"| {label} | {name} | {fixtures} | {c['tp']} | {c['fp']} | {c['fn']} "
        f"| {precision} | {recall} |"
    )


def format_table(metrics: dict, path: str = "intent") -> str:
    """Markdown table of precision and recall per area and overall."""
    prefix = "" if path == "intent" else "scan_"
    per_area = metrics[f"{prefix}per_area"]
    lines = [
        "| Area | Name | Fixtures | TP | FP | FN | Precision | Recall |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for area in AREAS:
        name = lookup_by_area(area)[0].area_name
        lines.append(_row(str(area), name, per_area[area]["fixtures"], per_area[area]))
    total = sum(per_area[a]["fixtures"] for a in AREAS)
    lines.append(_row("Overall", "all areas", total, metrics[f"{prefix}overall"]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    metrics = measure()
    print("Intent path")
    print(format_table(metrics, "intent"))
    print()
    print("Default scan path")
    print(format_table(metrics, "scan"))
    print()
    n_none = metrics["none_fixtures"]
    print(f"none_clean: {metrics['none_clean']} of {n_none}")
    print(f"scan_none_clean: {metrics['scan_none_clean']} of {n_none}")
    print(f"art5_on_non_art5: {metrics['art5_on_non_art5']}")
    print(f"fixtures: {metrics['fixtures']}")
    print(f"elapsed_s: {metrics['elapsed_s']}")
    for title, key in (
        ("Misses, intent path", "misses"),
        ("Spurious, intent path", "spurious"),
        ("Misses, default scan path", "scan_misses"),
        ("Spurious, default scan path", "scan_spurious"),
    ):
        print()
        print(f"{title} ({len(metrics[key])})")
        for line in metrics[key]:
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
