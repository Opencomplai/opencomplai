"""Model fetch, progress bar, and local cache management."""

from __future__ import annotations

from dataclasses import replace
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
from opencomplai_ai.egress import require_online, stdin_is_interactive
from opencomplai_ai.integrity import (
    UnpinnedModelError,
    describe_pin,
    verify_artifact,
)
from opencomplai_ai.models import MODEL_CATALOG, ModelNotInstalledError


def _confirm(console: Console, prompt: str, *, operation: str) -> None:
    """
    Ask for confirmation, or refuse when nobody can answer.

    The download prompt used to call ``console.input`` unconditionally. On a
    non-interactive stdin that either raises ``EOFError`` or — the behaviour
    actually seen in this repo's test suite — blocks forever (finding 78).
    Refusing outright is the only safe answer: silently proceeding would treat
    "no human present" as consent to a multi-GB download.
    """
    if not stdin_is_interactive():
        raise RuntimeError(
            f"{operation} needs confirmation but stdin is not interactive.\n"
            f"  Pre-download the model on an interactive machine, or set "
            f"OPENCOMPLAI_OFFLINE=1 to make this fail fast and explicitly."
        )
    if console.input(prompt).strip().lower() in ("n", "no"):
        raise RuntimeError(f"{operation} cancelled.")


def _guard_pin(spec, console: Console) -> None:
    """
    Refuse to fetch an unpinned model without an interactive acknowledgement.

    An unpinned fetch resolves the upstream branch head, so a repo that is
    compromised or changes hands silently yields different weights. That is
    tolerable for a human who has just been told about it; it is not tolerable
    unattended, which is exactly where a swap goes unnoticed. Non-interactive
    runs therefore fail closed.
    """
    if spec.revision:
        return
    message = (
        f"{spec.display_name} has no pinned revision, so this fetches whatever "
        f"the upstream branch head currently points at."
    )
    if not stdin_is_interactive():
        raise UnpinnedModelError(
            f"{message}\n"
            f"  Refusing to do that unattended — an upstream swap would go "
            f"unnoticed. Run this once interactively, or pin "
            f"'{spec.model_id}' in MODEL_CATALOG."
        )
    console.print(f"[yellow]Warning:[/yellow] {message}")


def ensure_model(model_id: str) -> Path:
    """Return the local path to *model_id*, downloading if not cached."""
    if model_id not in MODEL_CATALOG:
        raise ValueError(f"Unknown model '{model_id}'")

    spec = MODEL_CATALOG[model_id]

    # CodeBERT ships no prebuilt ONNX artifact on the Hub, so the codebert-onnx
    # export is produced from the official PyTorch checkpoint on first use.
    # Keyed on the id, not spec.runtime: that entry's runtime label is
    # "deterministic" (it classifies without a model), and any other runtime
    # would fall through to the plain-file download below.
    if model_id == "codebert-onnx":
        return _ensure_onnx_export(spec)

    if not spec.filename:
        raise ValueError(f"Model '{model_id}' has no downloadable file")

    cache_dir = get_cache_dir()
    cached_path = cache_dir / spec.filename

    if cached_path.exists():
        # Re-verified on every reuse, not just at download time — otherwise a
        # later local modification of the cached file is never noticed.
        verify_artifact(cached_path, spec.sha256, context="cached artifact")
        return cached_path

    # Fail fast on the missing hard dependency *before* pulling the file.
    # This used to be checked only in registry.resolve(), which runs after
    # the backend is constructed — for the default model that meant a base
    # install downloaded the full ~1GB GGUF file and only then discovered it
    # had no way to run it (finding 48.10). Same error type and message as
    # registry.resolve() so the actionable text is identical either way.
    if spec.requires_deep:
        try:
            import llama_cpp  # noqa: F401
        except ImportError:
            raise ModelNotInstalledError(
                f"Model '{model_id}' requires llama-cpp-python.\n"
                f"Run: pip install 'opencomplai-ai[deep]'\n"
                f"Or choose a lighter model: opencomplai ai configure"
            ) from None

    require_online(f"Downloading {spec.display_name}")

    cache_dir.mkdir(parents=True, exist_ok=True)

    console = Console()
    console.print(
        f"\n[bold]Downloading[/bold] {spec.display_name} (~{spec.size_mb} MB)\n"
        f"  Repo: {spec.hf_repo}\n"
        f"  File: {spec.filename}\n"
        f"  Pin:  {describe_pin(spec.revision, spec.sha256)}\n"
        f"  Cache: {cached_path}\n"
    )

    _guard_pin(spec, console)
    _confirm(console, "Download now? [Y/n]: ", operation="Model download")

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
            # Pins the fetch to an immutable commit when the catalog carries
            # one. None means the branch head, already warned about above.
            revision=spec.revision or None,
        )
        progress.update(task, completed=100, total=100)

    downloaded_path = Path(downloaded)
    if downloaded_path != cached_path:
        cached_path = downloaded_path

    verify_artifact(cached_path, spec.sha256, context="freshly downloaded")
    return cached_path


def _ensure_onnx_export(spec) -> Path:
    """Export the PyTorch checkpoint to ONNX on first use and cache it.

    Python-API-only: this is reachable solely through ``ensure_model`` called
    from user code. No CLI command calls it (``opencomplai ai configure`` only
    saves the chosen id; the scan preload skips ``codebert-onnx``), and
    nothing reads the ``model.onnx`` it writes. It is not used for
    classification — ``IntentClassifier`` is a deterministic code-signal
    matcher with no model artifact (see ``classifier.py``) and never calls
    ``ensure_model``. It needs the ``[onnx]`` extra (``optimum[onnxruntime]``)
    installed separately.
    """
    cache_dir = get_cache_dir()
    model_dir = cache_dir / "codebert-base"
    onnx_file = model_dir / "model.onnx"

    if onnx_file.exists():
        return onnx_file

    # The catalog display_name describes the deterministic classifier, not
    # this export, so name the export itself in the prompts below.
    spec = replace(spec, display_name=f"CodeBERT ONNX export ({spec.hf_repo})")
    require_online(f"Exporting {spec.display_name}")

    console = Console()
    console.print(
        f"\n[bold]Preparing[/bold] {spec.display_name}\n"
        f"  Source: {spec.hf_repo} (PyTorch checkpoint)\n"
        f"  Export: ONNX -> {onnx_file}\n"
        f"  Pin:    {describe_pin(spec.revision, spec.sha256)}\n"
        f"  This runs once; the export is cached at the path above. Scans do not use it.\n"
    )
    _guard_pin(spec, console)
    _confirm(console, "Download and export now? [Y/n]: ", operation="Model export")

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
        model = ORTModelForFeatureExtraction.from_pretrained(
            spec.hf_repo, export=True, revision=spec.revision or None
        )
        model.save_pretrained(model_dir)
        AutoTokenizer.from_pretrained(
            spec.hf_repo, revision=spec.revision or None
        ).save_pretrained(model_dir)

    if not onnx_file.exists():
        raise RuntimeError(
            f"ONNX export completed but {onnx_file} was not produced. "
            f"Contents: {sorted(p.name for p in model_dir.iterdir())}"
        )
    return onnx_file
