# EMA Benchmark: bearta vs polars_talib vs polars ewm_mean

**Date:** 2026-04-25  
**N:** 10,000 values  
**Period:** 20  
**Platform:** macOS Darwin 25.0.0  
**Python polars:** 1.30.0

## Results

| Implementation     | min     | mean    | std    |
|--------------------|---------|---------|--------|
| bearta EMA         | 108.3µs | 139.0µs | 22.3µs |
| polars_talib       |  76.7µs |  84.0µs |  8.0µs |
| polars `ewm_mean`  |  88.6µs |  93.9µs |  6.1µs |

Each figure is the mean over 20 runs, repeated 7 times.

## Observations

**Values are identical.** All three produce the same results to 15 decimal places at N=10,000/period=20 — the EMA has long converged and initialisation differences (SMA seed in TA-Lib vs first-value seed in bearta) are irrelevant at this scale.

**bearta is ~1.5× slower than polars_talib and polars' built-in.** It is also noisier (std=22µs vs 6–8µs), suggesting more variance in the plugin dispatch path.

**polars_talib edges out native `ewm_mean`** — backed by the TA-Lib C library which is hand-tuned for these calculations.

## Likely causes of the bearta gap

1. Element-by-element iteration in `calc_ema` (`into_iter()`) — no SIMD, no chunked parallelism
2. Separate validity bitmap construction + `from_vec_validity` call adds an extra allocation pass over the output buffer

## Algorithmic differences

| | Seed value | Warmup output |
|---|---|---|
| bearta | first valid value | null |
| polars_talib | SMA of first `period` values | NaN |
| polars `ewm_mean` | first valid value | value from row 0 |

## Reproduction

```sh
uv run scripts/bench_ema.py
```

Requires `polars-talib` and `numpy` in dev dependencies.
