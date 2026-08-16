# EMA Benchmark: bartons vs polars_talib vs polars ewm_mean

**Date:** 2026-04-25  
**N:** 10,000 values  
**Period:** 20  
**Platform:** macOS Darwin 25.0.0  
**polars-py:** 1.30.0

## Results

| Implementation     | min     | mean    | std    |
|--------------------|---------|---------|--------|
| bartons EMA        | 108.3µs | 139.0µs | 22.3µs |
| polars_talib       |  76.7µs |  84.0µs |  8.0µs |
| polars `ewm_mean`  |  88.6µs |  93.9µs |  6.1µs |

Each figure is the mean over 20 runs, repeated 7 times.

## Observations

**Values are identical.** All three produce the same results to 15 decimal places at N=10,000/period=20 — the EMA has long converged and initialisation differences (SMA seed in TA-Lib vs first-value seed in bartons) are irrelevant at this scale.

**bartons is ~1.5× slower than polars_talib and polars' built-in.** It is also noisier (std=22µs vs 6–8µs), suggesting more variance in the plugin dispatch path.

**polars_talib edges out native `ewm_mean`** — backed by the TA-Lib C library which is hand-tuned for these calculations.

## Likely causes of the bartons gap

1. Element-by-element iteration in the EMA kernel (`into_iter()`, since moved into `run_unary`) — no SIMD, no chunked parallelism
2. Separate validity bitmap construction + `from_vec_validity` call adds an extra allocation pass over the output buffer

## Algorithmic differences

| | Seed value | Warmup output |
|---|---|---|
| bartons | first valid value | null |
| polars_talib | SMA of first `period` values | NaN |
| polars `ewm_mean` | first valid value | value from row 0 |

## Reproduction

```sh
just bench vs-talib      # or: uv run scripts/benchmark-vs-talib.py
```

Requires `polars-talib` and `numpy` in dev dependencies.

The figures above were produced by the per-indicator `scripts/benchmark-ema.py`,
which has since been replaced by the per-baseline `benchmark-vs-*.py` scripts, so
absolute numbers may not line up exactly — the relative picture is the point.
