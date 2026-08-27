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
    LABBENCH2_COST_MODEL        e.g. "openai/gpt-5.6-sol"
    LABBENCH2_COST_INPUT        $/million input tokens          (default 1.0)
    LABBENCH2_COST_OUTPUT       $/million output tokens         (default 1.0)
    LABBENCH2_COST_CACHE_READ   $/million cached-read tokens    (default 0.0)
    LABBENCH2_COST_CACHE_WRITE  $/million cache-write tokens    (default 0.0)
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def register_from_env() -> str | None:
    """Apply pricing from the environment. Returns the model name if applied."""
    model = os.environ.get("LABBENCH2_COST_MODEL")
    if not model:
        return None
    try:
        from inspect_ai.model import ModelCost
        from inspect_ai.model._model_info import set_model_cost

        cost = ModelCost(
            input=float(os.environ.get("LABBENCH2_COST_INPUT", "1.0")),
            output=float(os.environ.get("LABBENCH2_COST_OUTPUT", "1.0")),
            input_cache_read=float(os.environ.get("LABBENCH2_COST_CACHE_READ", "0.0")),
            input_cache_write=float(os.environ.get("LABBENCH2_COST_CACHE_WRITE", "0.0")),
        )
        set_model_cost(model, cost)
    except Exception as exc:  # never let pricing break a run
        logger.warning(f"could not register cost for {model}: {exc}")
        return None
    logger.info(f"registered cost for {model}: {cost}")
    return model
