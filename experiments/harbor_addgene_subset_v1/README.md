# Harbor taskset — Addgene CloningQA subset

Generator: `tools/package_addgene_harbor_tasks.py`

```bash
uv run python tools/package_addgene_harbor_tasks.py \
  --output-dir experiments/harbor_addgene_subset_v1/tasks
```

Each subdirectory is a Harbor task. Zip the `tasks/` folder (the 55
task directories at the zip root) for DataVendor → Harbor tasksets.

Verifier notes: `../cloning_addgene_subset_v1/VERIFIER_FAULTS.md`

Local tests:

```bash
uv run pytest tests/lab_bench_2/test_generated_addgene_subset_questions.py \
  tests/lab_bench_2/test_harbor_addgene_pack.py \
  tests/lab_bench_2/test_cloning_simulators_v2.py \
  tests/lab_bench_2/test_scorers.py
```
