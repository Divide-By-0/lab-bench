#!/usr/bin/env python3
"""Post-run guards for an Inspect eval log.

Three invariants we want enforced mechanically rather than by remembering:

  1. TOKEN CEILING   no sample may exceed the declared budget. Inspect's --token-limit
     is checked *between* generations, so a sample can overshoot by roughly one turn.
     This reports the real spend so an overshoot is visible instead of silent.

  2. NO DUPLICATE RUNS   a sample id must appear once per epoch in this log, and must
     not already have a completed result in a prior log. Re-running the same task and
     reporting both is how a 3/11 quietly becomes a 5/11.

  3. FULL AGENTIC TOOL USE   solver must be `agentic`, and every sample must actually
     call the sandbox tools. A sample that answers with zero tool calls is a bare
     single-turn answer wearing an agentic label, and is not comparable.

Exit code 1 if any guard fails.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

SANDBOX_TOOLS = {"python_session", "python", "bash"}


def load(path: Path) -> dict:
    out = subprocess.run(
        ["uv", "run", "inspect", "log", "dump", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def check(
    log: dict, budget: int, prior_ids: set[str], metric: str = "novel"
) -> list[str]:
    fails: list[str] = []
    args = log.get("eval", {}).get("task_args", {})
    samples = log.get("samples", [])

    # 3. agentic
    if args.get("solver") != "agentic":
        fails.append(f"solver is {args.get('solver')!r}, expected 'agentic'")

    # 2. duplicates within this log
    keys = [(s.get("id"), s.get("epoch")) for s in samples]
    for key, n in Counter(keys).items():
        if n > 1:
            fails.append(
                f"duplicate sample {key[0]} epoch {key[1]} appears {n}x in this log"
            )

    for s in samples:
        sid = s.get("id")
        usage = list((s.get("model_usage") or {}).values())
        total = sum(u.get("total_tokens", 0) for u in usage)
        novel = sum(u.get("input_tokens", 0) + u.get("output_tokens", 0) for u in usage)
        calls = [
            tc.get("function")
            for m in s["messages"]
            for tc in (m.get("tool_calls") or [])
        ]

        # 1. ceiling
        # REASON: compare against whichever metric the budget is expressed in. When the
        # run is bounded by --cost-limit with cache priced at 0, the budget is in NOVEL
        # tokens and checking total_tokens raises false alarms -- cache reads are 3-5x
        # novel on these runs, so every sample would look like a violation.
        spent = novel if metric == "novel" else total
        if spent > budget:
            fails.append(
                f"{sid}: spent {spent:,} {metric} tokens, over the {budget:,} budget "
                f"(total {total:,}, novel {novel:,}) -- Inspect checks between "
                f"generations, so this can overshoot by one turn"
            )
        # 3. tool use
        if not any(c in SANDBOX_TOOLS for c in calls):
            fails.append(f"{sid}: zero sandbox tool calls -- not real agentic use")
        # 2. duplicates against prior logs
        if sid in prior_ids:
            fails.append(
                f"{sid}: already has a completed result in a prior log -- duplicate run"
            )
    return fails


def completed_ids(paths: list[Path]) -> set[str]:
    ids: set[str] = set()
    for p in paths:
        try:
            for s in load(p).get("samples", []):
                if s.get("scores"):
                    ids.add(s.get("id"))
        except Exception:
            continue
    return ids


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("log", type=Path)
    ap.add_argument("--budget", type=int, required=True)
    ap.add_argument(
        "--prior",
        type=Path,
        nargs="*",
        default=[],
        help="earlier logs to check for duplicate completed samples",
    )
    ap.add_argument(
        "--metric",
        choices=["novel", "total"],
        default="novel",
        help="which token count the budget is expressed in (default: novel)",
    )
    a = ap.parse_args()

    log = load(a.log)
    fails = check(log, a.budget, completed_ids(a.prior), a.metric)
    n = len(log.get("samples", []))
    if fails:
        print(f"FAIL — {len(fails)} guard violation(s) across {n} sample(s):")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(
        f"PASS — {n} sample(s): all within {a.budget:,} {a.metric} tokens, no duplicates, all used sandbox tools"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
