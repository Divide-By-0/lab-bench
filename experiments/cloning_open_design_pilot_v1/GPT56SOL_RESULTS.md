# GPT-5.6 Sol max web-enabled pilot results

Run date: 2026-08-28

Both samples were run individually with `openai/gpt-5.6-sol`, reasoning effort
`max`, one concurrent connection, the `agentic_web` OrbStack solver, and the
synthetic novel-token cost configuration. A `$0.13` research-loop threshold
reserved room for a forced final answer under the `$0.20` / 200,000-novel-token
hard target. Cached input tokens were not charged against that target.

The task intentionally records `UNSCORED` results. These are open-world designs
for which the repository does not yet claim a complete deterministic verifier.

| Sample | Novel tokens | Cached input | Output artifact | OpenAI web actions | Sandbox calls | Submitted answer |
|---|---:|---:|---:|---:|---|---|
| HepaRG three-plasmid reporters | 148,541 | 253,888 | 6,199 chars | 10 | 13 Bash, 1 Python | Captured |
| Astrocyte APOE4 + ABCA1 KO | 179,805 | 132,074 | 5,295 chars | 4 | 22 Bash, 2 Python | Captured |

## What happened

The model did not produce a construction-ready answer to either task.

- For the HepaRG task, it proposed a plausible Tet-responsive three-reporter
  architecture and spectral choices, but could not establish all required
  quantitative response matching or obtain all exact public sequence records.
  Its three `<protocol>` blocks explicitly say they are non-executable rather
  than fabricating assemblies.
- For the astrocyte task, it proposed a piggyBac inducible APOE4 donor plus an
  ABCA1 CRISPR editing architecture, but did not complete GRCh38/MANE guide and
  off-target analysis, exact fragment boundaries, primers, checksums, or
  in-silico assemblies. Its manifest is explicitly labeled incomplete.

These are useful hard-task failures: both models used the available research
and sequence-analysis tools, found defensible high-level approaches, and then
failed at evidence-backed sequence resolution. They are not infrastructure
failures or generic refusals.

## Inspect logs

- `experiments/traces/gpt56sol_cloning_open_design_hepatocyte_web_200k.eval`
- `experiments/traces/gpt56sol_cloning_open_design_astrocyte_web_200k.eval`

Two diagnostic HepaRG attempts are retained separately:

- `gpt56sol_cloning_open_design_hepatocyte_web_attempt1_incomplete_226k.eval`
  demonstrates that Inspect can overshoot a cost ceiling by one model turn and
  then spend another final-warning turn.
- `gpt56sol_cloning_open_design_hepatocyte_web_attempt2_submit_not_captured_135k.eval`
  demonstrates the pre-fix state-loss bug: a final `submit` appears in events,
  but the active cost limit prevented it from becoming `output.completion`.

The final-answer reserve added for this pilot fixes the second issue while
keeping both final runs below 200,000 measured novel tokens.

## View

From the repository root:

```bash
.venv/bin/inspect view --log-dir experiments/traces --recursive --port 7575
```

Then open `http://127.0.0.1:7575/` and select either stable log above. Native
web-search activity is embedded within model events; direct downloads and
sequence inspection appear as Bash/Python tool calls.
