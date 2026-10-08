"""Bundled prompt-injection seed corpus for a zero-config `opencomplai eval`.

Prompts only. Canned "resistant" outputs would be fabricated evidence, so without real
outputs the adversarial evaluator honestly returns SKIPPED. Results are heuristic.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from opencomplai_core.models import EvalSampleSet

_SEED_PATH = Path(__file__).parent / "data" / "prompt_injection_seed.json"

SEED_EVAL_SET_ID = "SEED_PROMPT_INJECTION_V1"


@lru_cache(maxsize=1)
def load_seed_corpus() -> dict:
    return json.loads(_SEED_PATH.read_text(encoding="utf-8"))


def seed_sample_set(
    system_id: str, commit_ref: str, outputs: list[str] | None = None
) -> EvalSampleSet:
    prompts = list(load_seed_corpus()["prompts"])
    if outputs is not None and len(outputs) != len(prompts):
        raise ValueError(
            f"outputs ({len(outputs)}) must match the seed prompts ({len(prompts)})"
        )
    return EvalSampleSet(
        eval_set_id=SEED_EVAL_SET_ID,
        system_id=system_id,
        commit_ref=commit_ref,
        task_type="prompt_injection",
        prompts=prompts,
        outputs=list(outputs or []),
    )
