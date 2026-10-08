"""D-B1: the base install names neither transformers nor onnxruntime (offline)."""

import ast
import re
import sys
import tomllib
from pathlib import Path

import pytest
from opencomplai_ai.registry import ModelRegistry

PKG = Path(__file__).resolve().parents[1]
ML = {"transformers", "onnxruntime", "optimum"}


def _norm(req: str) -> str:
    return (
        re.split(r"[\[<>=!~; ]", req.strip(), maxsplit=1)[0].lower().replace("_", "-")
    )


def test_base_dependencies_do_not_name_the_ml_stack():
    project = tomllib.loads((PKG / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    names = {_norm(d) for d in project["dependencies"]}
    assert not names & {"transformers", "onnxruntime"}
    assert "huggingface-hub" in names
    assert any(
        d.startswith("optimum[onnxruntime]")
        for d in project["optional-dependencies"]["onnx"]
    )


def test_ml_libs_are_imported_only_inside_the_export_function():
    offenders = []
    for path in (PKG / "src" / "opencomplai_ai").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        inside = {
            id(n)
            for f in ast.walk(tree)
            if isinstance(f, ast.FunctionDef) and f.name == "_ensure_onnx_export"
            for n in ast.walk(f)
        }
        for n in ast.walk(tree):
            mods = (
                [a.name for a in n.names]
                if isinstance(n, ast.Import)
                else [n.module or ""]
                if isinstance(n, ast.ImportFrom) and n.level == 0
                else []
            )
            if any(m.split(".")[0] in ML for m in mods) and id(n) not in inside:
                offenders.append(f"{path.name}:{n.lineno}")
    assert offenders == []


@pytest.fixture
def clean_registry():
    ModelRegistry.clear_cache()
    yield
    ModelRegistry.clear_cache()


def test_codebert_onnx_classifies_without_transformers_or_onnxruntime(
    monkeypatch, clean_registry
):
    for name in ("transformers", "onnxruntime", "optimum", "optimum.onnxruntime"):
        monkeypatch.setitem(sys.modules, name, None)
    backend = ModelRegistry.resolve("codebert-onnx")
    result = backend.classify("risk_score = scorecard.predict(applicant)")
    assert result.model_id == "codebert-onnx"
    assert result.annex_iii_area == 5
