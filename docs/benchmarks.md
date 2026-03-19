# Benchmarks

## Pandas Validation Throughput

Use the reproducible benchmark script:

```bash
python scripts/benchmark_pandas_validate.py --rows 1000000 --target-seconds 10.0 --output-json benchmark.json
```

Optional strict mode (exit code `1` on target miss):

```bash
python scripts/benchmark_pandas_validate.py --rows 1000000 --target-seconds 10.0 --strict-target
```

The script validates a synthetic `Trade` DataFrame and reports:

- elapsed seconds
- rows per second
- score/pass status
- Python/platform/CPU metadata

## Baseline Methodology

- Dataset: 1,000,000 `Trade` rows generated in-memory.
- Schema: `Trade`.
- Validation path: `DataFrame.finschema.validate("Trade")`.
- Run each benchmark at least 3 times and compare median elapsed time.
- Record environment metadata (CPU model, RAM, OS, Python version).

## Release Check Guidance

- Run benchmark as a dedicated release check (manual trigger or tag pipeline), not as a strict PR gate.
- In CI, run benchmark informationally on PR/main and enforce `--strict-target` on release tags.
- Keep performance target at 10 seconds for 1M rows on baseline hardware.
- If target misses, compare rows/sec and inspect regression in profile output before release.
