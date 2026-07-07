"""Model fetch, progress bar, and local cache management."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from opencomplai_ai.config import get_cache_dir
from opencomplai_ai.models import MODEL_CATALOG


def ensure_model(model_id: str) -> Path:
    """Return the local path to *model_id*, downloading if not cached."""
    if model_id not in MODEL_CATALOG:
        raise ValueError(f"Unknown model '{model_id}'")

    spec = MODEL_CATALOG[model_id]

    # CodeBERT ships no prebuilt ONNX artifact on the Hub, so the ONNX runtime
    # path is produced by exporting the official PyTorch checkpoint on first use.
    if spec.runtime == "onnxruntime":
        return _ensure_onnx_export(spec)

    if not spec.filename:
        raise ValueError(f"Model '{model_id}' has no downloadable file")

    cache_dir = get_cache_dir()
    cached_path = cache_dir / spec.filename

    if cached_path.exists():
        return cached_path

    cache_dir.mkdir(parents=True, exist_ok=True)

    console = Console()
    console.print(
        f"\n[bold]Downloading[/bold] {spec.display_name} (~{spec.size_mb} MB)\n"
        f"  Repo: {spec.hf_repo}\n"
        f"  File: {spec.filename}\n"
        f"  Cache: {cached_path}\n"
    )

    if console.input("Download now? [Y/n]: ").strip().lower() in ("n", "no"):
        raise RuntimeError(
            "Model download cancelled. Re-run with --ai-model codebert-onnx to skip download."
        )

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        raise RuntimeError(
            "huggingface-hub is required to download models. "
            "Run: pip install huggingface-hub"
        ) from None

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(f"Downloading {spec.filename}", total=None)
        downloaded = hf_hub_download(
            repo_id=spec.hf_repo,
            filename=spec.filename,
            local_dir=str(cache_dir),
        )
        progress.update(task, completed=100, total=100)

    downloaded_path = Path(downloaded)
    if downloaded_path != cached_path:
        cached_path = downloaded_path

    return cached_path


def _ensure_onnx_export(spec) -> Path:
    """Export the PyTorch checkpoint to ONNX on first use and cache it.

    The classifier loads ``<cache>/codebert-base/model.onnx`` (see
    ``IntentClassifier._load``), so we export the official ``spec.hf_repo``
    checkpoint into that directory once and reuse it thereafter.
    """
    cache_dir = get_cache_dir()
    model_dir = cache_dir / "codebert-base"
    onnx_file = model_dir / "model.onnx"

    if onnx_file.exists():
        return onnx_file

    console = Console()
    console.print(
        f"\n[bold]Preparing[/bold] {spec.display_name} (~{spec.size_mb} MB)\n"
        f"  Source: {spec.hf_repo} (PyTorch checkpoint)\n"
        f"  Export: ONNX -> {onnx_file}\n"
        f"  This runs once; the exported model is cached for future scans.\n"
    )
    if console.input("Download and export now? [Y/n]: ").strip().lower() in ("n", "no"):
        raise RuntimeError("Model export cancelled by user.")

    try:
        from optimum.onnxruntime import ORTModelForFeatureExtraction
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "Exporting CodeBERT to ONNX requires 'optimum[onnxruntime]'.\n"
            "  Run: pip install 'optimum[onnxruntime]'\n"
            "  Or choose a llama-cpp model: opencomplai ai configure"
        ) from exc

    model_dir.mkdir(parents=True, exist_ok=True)
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TimeRemainingColumn(),
    ) as progress:
        progress.add_task(f"Exporting {spec.hf_repo} to ONNX", total=None)
        model = ORTModelForFeatureExtraction.from_pretrained(spec.hf_repo, export=True)
        model.save_pretrained(model_dir)
        AutoTokenizer.from_pretrained(spec.hf_repo).save_pretrained(model_dir)

    if not onnx_file.exists():
        raise RuntimeError(
            f"ONNX export completed but {onnx_file} was not produced. "
            f"Contents: {sorted(p.name for p in model_dir.iterdir())}"
        )
    return onnx_file
