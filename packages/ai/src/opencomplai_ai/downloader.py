"""Model fetch, progress bar, and local cache management."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn, TransferSpeedColumn

from opencomplai_ai.config import get_cache_dir
from opencomplai_ai.models import MODEL_CATALOG


def ensure_model(model_id: str) -> Path:
    """Return the local path to *model_id*, downloading if not cached."""
    if model_id not in MODEL_CATALOG:
        raise ValueError(f"Unknown model '{model_id}'")

    spec = MODEL_CATALOG[model_id]
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
            f"Model download cancelled. Re-run with --ai-model codebert-onnx to skip download."
        )

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        raise RuntimeError(
            "huggingface-hub is required to download models. "
            "Run: pip install huggingface-hub"
        )

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
