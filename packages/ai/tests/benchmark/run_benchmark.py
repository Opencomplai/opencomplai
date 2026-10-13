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
import math
import tempfile
import time
import warnings
from pathlib import Path

from opencomplai_ai.knowledge.annex_iii import lookup_by_area
from opencomplai_core.scan_engine import run_scan
from opencomplai_core.scanner.mapping import _AREA_TO_TAXONOMY
from opencomplai_core.scanner.proposal import build_classification_proposal

AREAS = tuple(range(1, 9))
_TAXONOMY_TO_AREA = {key: area for area, key in _AREA_TO_TAXONOMY.items()}


def _load_fixtures() -> list[dict]:
    path = Path(__file__).resolve().parent / "fixtures.py"
    spec = importlib.util.spec_from_file_location("annex_iii_benchmark_fixtures", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FIXTURES


def _load_heldout() -> list[dict]:
    path = Path(__file__).resolve().parent / "heldout_fixtures.py"
    spec = importlib.util.spec_from_file_location("annex_iii_benchmark_heldout", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HELDOUT


@contextlib.contextmanager
def _fixture_root(fixture: dict):
    """Write one fixture into a temp directory and yield that root (no chdir)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in fixture["files"].items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        yield root


def _scan_fixture(fixture: dict) -> tuple[list[int], bool, list[int]]:
    """Return (intent areas, art5 flag, default-scan areas) for one fixture."""
    with _fixture_root(fixture) as root:
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


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson score interval for k successes in n trials (None when n is 0)."""
    if n == 0:
        return None
    p = k / n
    scale = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / scale
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / scale
    # Clamp so rounding never leaves the point estimate outside the interval.
    return min(max(centre - half, 0.0), p), max(min(centre + half, 1.0), p)


def _interval_cell(k: int, n: int) -> str:
    interval = wilson_interval(k, n)
    if interval is None:
        return "n/a (n=0)"
    lo, hi = interval
    return f"{100 * k / n:.1f}% (n={n}, 95% CI {100 * lo:.1f}-{100 * hi:.1f}%)"


def measure_top1(fixtures: list[dict]) -> dict:
    """Score the area the classification proposal picks for area-labelled programs."""
    result: dict = {
        "n": 0,
        "correct": 0,
        "none": 0,
        "tie": 0,
        "wrong": 0,
        "per_fixture": {},
    }
    for fx in fixtures:
        if fx["area"] is None:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in fx["files"].items():
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                report = run_scan(
                    fx["name"],
                    "HEAD",
                    root,
                    fx["purpose"],
                    ai_intent=True,
                    ai_model="codebert-onnx",
                )
        failed = [str(w.message) for w in caught]
        failed = [m for m in failed if m.startswith("AI intent analysis")]
        if failed or report.eu_ai_scan is None:
            raise RuntimeError(
                f"intent analysis did not run for {fx['name']}: "
                f"{failed or 'no eu_ai_scan'}"
            )
        proposal = build_classification_proposal(report.eu_ai_scan)
        proposed = proposal.proposed_annex_iii_area
        result["n"] += 1
        result["per_fixture"][fx["name"]] = proposed
        if proposal.tie_areas:
            result["tie"] += 1
        elif proposed is None:
            result["none"] += 1
        elif proposed == fx["area"]:
            result["correct"] += 1
        else:
            result["wrong"] += 1
    return result


def measure_heldout(fixtures: list[dict] | None = None) -> dict:
    """``measure`` over the held-out set plus Art. 5 and per-language counts."""
    fixtures = _load_heldout() if fixtures is None else fixtures
    result = measure(fixtures)
    flagged = set(result["art5_names"])
    labelled = {fx["name"] for fx in fixtures if fx["art5"]}
    result["art5_tp"] = len(flagged & labelled)
    result["art5_fp"] = len(flagged - labelled)
    result["art5_fn"] = len(labelled - flagged)
    by_language: dict[str, dict] = {}
    for fx in fixtures:
        row = by_language.setdefault(
            fx["language"], {"fixtures": 0, "area_tp": 0, "area_fn": 0}
        )
        row["fixtures"] += 1
        if fx["area"] is None:
            continue
        hit = fx["area"] in result["predictions"][fx["name"]]["intent"]
        row["area_tp" if hit else "area_fn"] += 1
    result["by_language"] = by_language
    return result


def format_set_table(label: str, metrics: dict) -> str:
    """Overall counts of one set on both paths, with Wilson intervals."""
    lines = [
        "| Set | Path | n | TP | FP | FN | Precision (95% CI) | Recall (95% CI) |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for path_name, key in (
        ("Intent path", "overall"),
        ("Default scan path", "scan_overall"),
    ):
        c = metrics[key]
        lines.append(
            f"| {label} | {path_name} | {metrics['fixtures']} | {c['tp']} | {c['fp']} "
            f"| {c['fn']} | {_interval_cell(c['tp'], c['tp'] + c['fp'])} "
            f"| {_interval_cell(c['tp'], c['tp'] + c['fn'])} |"
        )
    return "\n".join(lines)


def format_top1_table(training: dict, heldout: dict) -> str:
    lines = [
        "| Set | n | Correct | No proposal | Tie | Wrong | Top-1 accuracy (95% CI) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, t in (("Training", training), ("Held-out", heldout)):
        lines.append(
            f"| {label} | {t['n']} | {t['correct']} | {t['none']} | {t['tie']} "
            f"| {t['wrong']} | {_interval_cell(t['correct'], t['n'])} |"
        )
    return "\n".join(lines)


def format_art5_and_language_lines(heldout: dict) -> str:
    lines = [
        f"heldout_art5: tp={heldout['art5_tp']} fp={heldout['art5_fp']} "
        f"fn={heldout['art5_fn']}"
    ]
    for lang, row in sorted(heldout["by_language"].items()):
        lines.append(
            f"heldout_language_{lang}: fixtures={row['fixtures']} "
            f"detected={row['area_tp']} labelled={row['area_tp'] + row['area_fn']}"
        )
    return "\n".join(lines)


def _load_leads_fixtures() -> list[dict]:
    path = Path(__file__).resolve().parent / "fixtures_leads.py"
    spec = importlib.util.spec_from_file_location("annex_iii_benchmark_leads", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LEADS


load_leads_fixtures = _load_leads_fixtures


def measure_leads(fixtures: list[dict] | None = None) -> dict:
    """``measure`` over the areas 3 to 8 set plus per-language and per-kind counts.

    Every hard negative is exactly an ``area is None`` program, so ``none_clean``
    and ``scan_none_clean`` from ``measure`` are the hard-negative-clean figures.
    """
    fixtures = _load_leads_fixtures() if fixtures is None else fixtures
    result = measure(fixtures)
    by_language: dict[str, dict] = {}
    by_kind: dict[str, int] = {}
    for fx in fixtures:
        row = by_language.setdefault(
            fx["language"], {"fixtures": 0, "area_tp": 0, "area_fn": 0}
        )
        row["fixtures"] += 1
        by_kind[fx["kind"]] = by_kind.get(fx["kind"], 0) + 1
        if fx["area"] is None:
            continue
        hit = fx["area"] in result["predictions"][fx["name"]]["intent"]
        row["area_tp" if hit else "area_fn"] += 1
    result["by_language"] = by_language
    result["by_kind"] = by_kind
    return result


def format_leads_lines(result: dict, top1: dict) -> str:
    """Summary lines and one table for the areas 3 to 8 set (own prefixes)."""
    n_none = result["none_fixtures"]
    kinds = " ".join(f"{k}={v}" for k, v in sorted(result["by_kind"].items()))
    lines = [
        f"leads_none_clean: {result['none_clean']} of {n_none}",
        f"leads_scan_none_clean: {result['scan_none_clean']} of {n_none}",
        f"leads_by_kind: {kinds}",
    ]
    for lang, row in sorted(result["by_language"].items()):
        lines.append(
            f"leads_language_{lang}: fixtures={row['fixtures']} "
            f"detected={row['area_tp']} labelled={row['area_tp'] + row['area_fn']}"
        )
    lines.append(
        f"leads_top1: n={top1['n']} correct={top1['correct']} none={top1['none']} "
        f"tie={top1['tie']} wrong={top1['wrong']}"
    )
    lines.append(format_set_table("Leads set", result))
    return "\n".join(lines)


# Lead tier: the call sites the CLI shows as leads, measured on the three labelled
# sets. A lead is a non-echo call site of the deterministic matcher in areas 3 to 8,
# the same selection ``opencomplai_cli.leads`` makes (it asks the scan engine for
# areas 3 to 8 only, and the engine skips declared-purpose echoes). Areas 1 and 2
# never produce a lead, so they are neither scored nor counted here.
LEAD_AREAS = tuple(range(3, 9))
# Precision of the training intent path overall (22 of 30), as an exact fraction.
LEADS_FLOOR = (22, 30)
_LEAD_SET_ORDER = ("training", "held-out", "areas 3-8")


def _floor_met(tp: int, fp: int) -> bool:
    return tp > 0 and tp * LEADS_FLOOR[1] >= LEADS_FLOOR[0] * (tp + fp)


def measure_lead_tier(fixtures: list[dict]) -> dict:
    """Score the leads one scan per program yields; ``measure_leads`` stays as is."""
    rows: list[tuple[str, int | None, list[int]]] = []
    top1 = {"n": 0, "correct": 0, "none": 0, "tie": 0, "wrong": 0}
    fp_programs: dict[int, list[str]] = {}
    for fx in fixtures:
        with _fixture_root(fx) as root:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                report = run_scan(
                    fx["name"],
                    "HEAD",
                    root,
                    fx["purpose"],
                    ai_intent=True,
                    ai_model="codebert-onnx",
                )
        failed = [str(w.message) for w in caught]
        failed = [m for m in failed if m.startswith("AI intent analysis")]
        if failed or report.eu_ai_scan is None:
            raise RuntimeError(
                f"intent analysis did not run for {fx['name']}: "
                f"{failed or 'no eu_ai_scan'}"
            )
        proposal = build_classification_proposal(report.eu_ai_scan)
        areas = sorted(
            {
                ev.annex_iii_area
                for ev in proposal.supporting_evidence + proposal.minority_evidence
                if ev.annex_iii_area in LEAD_AREAS
            }
        )
        rows.append((fx["name"], fx["area"], areas))
        for area in areas:
            if area != fx["area"]:
                fp_programs.setdefault(area, []).append(fx["name"])
        if fx["area"] is None:
            continue
        top1["n"] += 1
        if proposal.tie_areas:
            top1["tie"] += 1
        elif proposal.proposed_annex_iii_area is None:
            top1["none"] += 1
        elif proposal.proposed_annex_iii_area == fx["area"]:
            top1["correct"] += 1
        else:
            top1["wrong"] += 1
    per_area = {a: v for a, v in _tally(rows)["per_area"].items() if a in LEAD_AREAS}
    overall = {k: sum(per_area[a][k] for a in LEAD_AREAS) for k in ("tp", "fp", "fn")}
    overall["fixtures"] = sum(per_area[a]["fixtures"] for a in LEAD_AREAS)
    return {
        "programs": len(fixtures),
        "per_area": per_area,
        "overall": overall,
        "top1": top1,
        "fp_programs": {a: sorted(n) for a, n in sorted(fp_programs.items())},
    }


def leads_pooled(per_set: dict[str, dict]) -> dict[int, tuple[int, int, int]]:
    """Area -> (tp, fp, fn) summed over the sets."""
    return {
        a: tuple(
            sum(r["per_area"][a][k] for r in per_set.values())
            for k in ("tp", "fp", "fn")
        )
        for a in LEAD_AREAS
    }


def leads_area_policy(pooled: dict[int, tuple[int, int, int]]) -> dict[int, str]:
    """``lead`` at or above the floor, else ``notice_only``; area 5 is always shown."""
    return {
        a: "lowest_confidence"
        if a == 5
        else ("lead" if _floor_met(pooled[a][0], pooled[a][1]) else "notice_only")
        for a in LEAD_AREAS
    }


def leads_default_on(pooled: dict[int, tuple[int, int, int]]) -> bool:
    """Whether the pool of the areas other than 5 meets the floor."""
    tp = sum(pooled[a][0] for a in LEAD_AREAS if a != 5)
    fp = sum(pooled[a][1] for a in LEAD_AREAS if a != 5)
    return tp + fp > 0 and _floor_met(tp, fp)


def _lead_rows(label: str, per_area: dict, programs: dict, policy: dict | None):
    head = "| Set | Area | Name | Programs | TP | FP | FN | Precision | Recall |"
    sep = "|---|---|---|---:|---:|---:|---:|---:|---:|"
    if policy is not None:
        head, sep = head + " Policy |", sep + "---|"
    lines = [head, sep]
    total = {"tp": 0, "fp": 0, "fn": 0}
    for area in LEAD_AREAS:
        c = per_area[area]
        for k in total:
            total[k] += c[k]
        name = lookup_by_area(area)[0].area_name
        cell = f" {policy[area]} |" if policy is not None else ""
        lines.append(_row(f"{label} | {area}", name, programs[area], c) + cell)
    cell = " - |" if policy is not None else ""
    lines.append(
        _row(f"{label} | Overall", "areas 3 to 8", sum(programs.values()), total) + cell
    )
    return lines, total


def format_leads_tables(per_set: dict[str, dict], pooled: dict) -> list[str]:
    """One Markdown table per element: each set, the pool, then top-1 per set."""
    blocks: list[str] = []
    for key in _LEAD_SET_ORDER:
        r = per_set[key]
        programs = {a: r["per_area"][a]["fixtures"] for a in LEAD_AREAS}
        lines, _ = _lead_rows(f"Lead tier {key}", r["per_area"], programs, None)
        blocks.append("\n".join(lines))
    cells = {
        a: dict(zip(("tp", "fp", "fn"), pooled[a], strict=True)) for a in LEAD_AREAS
    }
    programs = {
        a: sum(per_set[k]["per_area"][a]["fixtures"] for k in _LEAD_SET_ORDER)
        for a in LEAD_AREAS
    }
    lines, _ = _lead_rows(
        "Lead tier pooled", cells, programs, leads_area_policy(pooled)
    )
    rest = [a for a in LEAD_AREAS if a != 5]
    total = {k: sum(cells[a][k] for a in rest) for k in ("tp", "fp", "fn")}
    state = "on by default" if leads_default_on(pooled) else "off by default"
    lines.append(
        _row(
            "Lead tier pooled | Overall without 5",
            "areas 3, 4, 6, 7, 8",
            sum(programs[a] for a in rest),
            total,
        )
        + f" {state} |"
    )
    blocks.append("\n".join(lines))
    top = [
        "| Lead tier set | n | Correct | No proposal | Tie | Wrong "
        "| Top-1 accuracy (95% CI) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key in _LEAD_SET_ORDER:
        t = per_set[key]["top1"]
        top.append(
            f"| Lead tier {key} | {t['n']} | {t['correct']} | {t['none']} "
            f"| {t['tie']} | {t['wrong']} | {_interval_cell(t['correct'], t['n'])} |"
        )
    blocks.append("\n".join(top))
    return blocks


def _load_candidate_fixtures() -> list[dict]:
    path = Path(__file__).resolve().parent / "candidate_fixtures.py"
    spec = importlib.util.spec_from_file_location("annex_iii_candidate_fixtures", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CANDIDATE_FIXTURES


def _intent_candidates(name: str, root: Path, purpose: str) -> list[tuple[str, str]]:
    """``(library, file)`` of the intent scan's candidates, in report order."""
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
    return [(c.library, c.file) for c in report.eu_ai_scan.candidates]


def measure_candidates(fixtures: list[dict] | None = None) -> dict:
    """Count candidates (leads, not findings) apart from precision and recall.

    ``scan_areas`` come from the same default-path read as ``measure``; nothing
    here is fed to ``_tally``.
    """
    fixtures = _load_candidate_fixtures() if fixtures is None else fixtures
    rows: dict[str, dict] = {}
    by_library: dict[str, dict] = {}
    total = 0
    for fx in fixtures:
        with _fixture_root(fx) as root:
            found = _intent_candidates(fx["name"], root, fx["purpose"])
            scan_areas = _scan_root(fx["name"], root, fx["purpose"])[2]
        rows[fx["name"]] = {"candidates": found, "scan_areas": scan_areas}
        total += len(found)
        for library in {lib for lib, _ in found}:
            row = by_library.setdefault(library, {"fixtures": 0, "candidates": 0})
            row["fixtures"] += 1
        for library, _ in found:
            by_library[library]["candidates"] += 1
    return {
        "fixtures": len(fixtures),
        "total": total,
        "by_library": by_library,
        "rows": rows,
    }


def format_candidates_table(result: dict) -> str:
    """Markdown table of candidate counts per library (no precision or recall)."""
    lines = ["| Library | Fixtures | Candidates |", "|---|---:|---:|"]
    for library, row in sorted(result["by_library"].items()):
        lines.append(f"| {library} | {row['fixtures']} | {row['candidates']} |")
    lines.append(f"| all libraries | {result['fixtures']} | {result['total']} |")
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

    heldout = measure_heldout()
    training_top1 = measure_top1(_load_fixtures())
    heldout_top1 = measure_top1(_load_heldout())
    print()
    print(f"Training set ({metrics['fixtures']} programs)")
    print(format_set_table("Training", metrics))
    print()
    print(f"Held-out set ({heldout['fixtures']} programs)")
    print(format_set_table("Held-out", heldout))
    n_none = heldout["none_fixtures"]
    print(f"heldout_none_clean: {heldout['none_clean']} of {n_none}")
    print(f"heldout_scan_none_clean: {heldout['scan_none_clean']} of {n_none}")
    print()
    print("Proposal top-1")
    print(format_top1_table(training_top1, heldout_top1))
    print()
    print(format_art5_and_language_lines(heldout))
    print()
    print(f"Misses, held-out intent path ({len(heldout['misses'])})")
    for line in heldout["misses"]:
        print(f"  {line}")

    leads = measure_leads()
    leads_top1 = measure_top1(load_leads_fixtures())
    print()
    print(
        f"Leads set ({leads['fixtures']} programs, areas 3 to 8; "
        "separate from the training and held-out sets)"
    )
    print(format_leads_lines(leads, leads_top1))

    lead_tier = {
        "training": measure_lead_tier(_load_fixtures()),
        "held-out": measure_lead_tier(_load_heldout()),
        "areas 3-8": measure_lead_tier(load_leads_fixtures()),
    }
    pooled = leads_pooled(lead_tier)
    print()
    print("Leads (for a person; not findings)")
    for block in format_leads_tables(lead_tier, pooled):
        print(block)
        print()
    policy = leads_area_policy(pooled)
    print("lead_tier_policy: " + " ".join(f"{a}={policy[a]}" for a in LEAD_AREAS))
    print(f"lead_tier_default_on: {leads_default_on(pooled)}")
    for key, result in lead_tier.items():
        for area, names in result["fp_programs"].items():
            print(f"lead_tier_fp_programs {key} area {area}: {', '.join(names)}")

    candidates = measure_candidates()
    print()
    print(
        "Candidates (leads for a person; not findings, not part of precision or recall)"
    )
    print(format_candidates_table(candidates))
    print(f"candidate_fixtures: {candidates['fixtures']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
