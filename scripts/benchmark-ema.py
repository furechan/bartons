"""
EMA benchmark: bartons vs polars built-in ewm_mean.

Note: bartons and polars ewm use different initialisation strategies:
  - bartons:    seeds EMA with first value, outputs after `period` steps
  - polars ewm: seeds with first value, outputs from row 0

Results are not numerically identical, but both are valid EMA variants.
"""

import timeit
import numpy as np
import polars as pl
from bartons.ema import EMA

PERIOD = 20
N = 10_000

rng = np.random.default_rng(42)
series = rng.standard_normal(N).cumsum() + 100
df = pl.DataFrame({"close": series})

# ---- sanity check -----------------------------------------------------------
r_bartons = df.with_columns(EMA(PERIOD))
r_polars  = df.with_columns(pl.col("close").ewm_mean(span=PERIOD, adjust=False))

print(f"N={N:,}  period={PERIOD}\n")
print("Last 3 values:")
print(f"  bartons: {r_bartons['close'].tail(3).to_list()}")
print(f"  pl.ewm:  {r_polars['close'].tail(3).to_list()}")
print()

# ---- benchmark --------------------------------------------------------------
REPEAT = 7
NUMBER = 20

def bench(label, stmt, globs):
    times = np.array(
        timeit.Timer(stmt, globals=globs).repeat(REPEAT, NUMBER)
    ) / NUMBER
    us = times * 1e6
    print(f"{label:<22}  min={min(us):7.1f}µs  mean={np.mean(us):7.1f}µs  std={np.std(us):6.1f}µs")

print("Benchmarks (each = mean over 20 runs, repeated 7 times):")
bench("bartons EMA",   "df.with_columns(EMA(PERIOD))",                                             dict(df=df, EMA=EMA, pl=pl, PERIOD=PERIOD))
bench("polars ewm_mean","df.with_columns(pl.col('close').ewm_mean(span=PERIOD, adjust=False))",    dict(df=df, pl=pl, PERIOD=PERIOD))
