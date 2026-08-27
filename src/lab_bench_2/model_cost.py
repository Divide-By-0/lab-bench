"""Register per-model token pricing so `--cost-limit` becomes a usable ceiling.

REASON: Inspect's `--token-limit` counts `ModelUsage.total_tokens`, which includes cache
reads. On an agentic run those dominate -- 14.6M cache against 5.0M novel on one cloning
batch -- so a total-token cap mostly measures transcript length, not work done. It
mis-fired repeatedly: one sample was killed at 268k novel purely for having accumulated
775k of cache reads, while another finished having produced 430k novel.

`--cost-limit` is checked against Inspect's own cost formula:

    cost = input*input_rate + output*output_rate
         + cache_write*cache_write_rate + cache_read*cache_read_rate   ($/million)

so pricing cache at 0 and input/output at 1.0 makes cost == novel_tokens / 1e6, i.e.
`--cost-limit 0.1` is exactly a 100,000-novel-token budget. Supply real $/million rates
instead and the same flag becomes a true dollar ceiling with cache priced correctly.

Inspect ships no cost data for newer models (`gpt-5.6-sol` has `total_cost=None`), which
means an unregistered model silently never accumulates cost and `--cost-limit` never
fires -- worse than no limit, because it looks like one. Registering here makes the
ceiling real.

Env vars (all optional; nothing happens unless LABBENCH2_COST_MODEL is set):
    LABBENCH2_COST_MODEL        comma-separated, e.g. "openai/gpt-5.6-sol"
    LABBENCH2_COST_FREE_MODELS  comma-separated, priced at 0 so they do not consume the
                                budget. Inspect refuses --cost-limit unless EVERY model
                                in the run has cost data, including the grader -- and the
                                grader is not what we are budgeting (for cloning it never
                                runs at all, the scorer is deterministic).
    LABBENCH2_COST_INPUT        $/million input tokens          (default 1.0)
    LABBENCH2_COST_OUTPUT       $/million output tokens         (default 1.0)
    LABBENCH2_COST_CACHE_READ   $/million cached-read tokens    (default 0.0)
    LABBENCH2_COST_CACHE_WRITE  $/million cache-write tokens    (default 0.0)
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _split(name: str) -> list[str]:
    return [m.strip() for m in os.environ.get(name, "").split(",") if m.strip()]


def register_from_env() -> list[str]:
    """Apply pricing from the environment. Returns the models registered."""
    metered, free = _split("LABBENCH2_COST_MODEL"), _split("LABBENCH2_COST_FREE_MODELS")
    if not metered and not free:
        return []
    done: list[str] = []
    try:
        from inspect_ai.model import ModelCost
        from inspect_ai.model._model_info import set_model_cost

        priced = ModelCost(
            input=float(os.environ.get("LABBENCH2_COST_INPUT", "1.0")),
            output=float(os.environ.get("LABBENCH2_COST_OUTPUT", "1.0")),
            input_cache_read=float(os.environ.get("LABBENCH2_COST_CACHE_READ", "0.0")),
            input_cache_write=float(os.environ.get("LABBENCH2_COST_CACHE_WRITE", "0.0")),
        )
        zero = ModelCost(input=0.0, output=0.0, input_cache_read=0.0, input_cache_write=0.0)
        for model, cost in [(m, priced) for m in metered] + [(m, zero) for m in free]:
            try:
                set_model_cost(model, cost)
                done.append(model)
            except Exception as exc:
                logger.warning(f"could not register cost for {model}: {exc}")
    except Exception as exc:  # never let pricing break a run
        logger.warning(f"cost registration unavailable: {exc}")
    logger.info(f"registered cost for: {done}")
    return done
