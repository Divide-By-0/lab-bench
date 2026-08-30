# Open-source-discovery cloning pilot

This pilot contains two deliberately open-ended, multi-construct design tasks:

- A three-plasmid matched-response reporter system for differentiated HepaRG cells.
- Stable inducible APOE4 expression plus ABCA1 knockout in human iPSC-derived astrocytes.

The first task has no starting sequence inventory. The second supplies only a
451 bp tetracycline-response promoter from NCBI accession `KY053834.1`; all
other parts must be found in public sources.

Both questions require sequence-resolved, executable construction protocols for
every new plasmid using Gibson, Golden Gate, restriction-enzyme assembly, or a
combination. They also require exact source provenance, primers, junctions, and
expected final sequences—not merely conceptual architecture.

## Important scoring limitation

These traces are intentionally unscored. The open solution space includes
components and strategies outside any current deterministic registry. Inspect
therefore records each output as `UNSCORED` with
`review_status=unverified_open_solution`; it does not convert lack of verifier
coverage into an incorrect verdict.

## Internet-enabled OrbStack solver

`agentic_web` combines the normal OrbStack Python/Bash workspace with OpenAI's
server-side web-search tool and a separate network-enabled Compose file for
downloading exact public records. The ordinary `agentic` solver and
`compose.yaml` remain offline.

Do not use `agentic_web` on a public benchmark whose answer key or reference
files are accessible online.

## Run

```bash
OPENAI_API_KEY="$(tr -d '\r\n' < /path/to/openai-key.txt)" \
  .venv/bin/inspect eval \
  experiments/cloning_open_design_pilot_v1/task.py@cloning_open_design_pilot \
  --model openai/gpt-5.6-sol --reasoning-effort max \
  --cost-limit 0.13 --model-cost-config experiments/novel_token_costs.yaml \
  --max-tokens 64000 --message-limit 120 --token-limit 6000000 \
  --max-connections 1 --epochs 1 --no-fail-on-error \
  --log-dir experiments/traces
```

The `$0.13` CLI ceiling reserves room for the forced final-answer turn. The task
then raises only that final turn's ceiling to `$0.20`, which corresponds to the
requested 200,000 novel tokens under the synthetic one-dollar-per-million
input/output configuration in `experiments/novel_token_costs.yaml`; cached
tokens are priced at zero. This two-stage limit is necessary because Inspect
checks a cost ceiling between model calls and a native web-search result can
otherwise overshoot the nominal ceiling by one large turn.
