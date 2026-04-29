"""
EMA benchmark: bearta vs polars_talib vs polars built-in ewm_mean.

Note: bearta and polars_talib use different initialisation strategies:
  - bearta:       seeds EMA with first value, outputs after `period` steps
  - polars_talib: seeds EMA with SMA of first `period` values (TA-Lib convention)
  - polars ewm:   seeds with first value, outputs from row 0

Results are not numerically identical, but all are valid EMA variants.
"""

import timeit
import numpy as np
import polars as pl
import polars_talib as ta
from bearta.ema import EMA

PERIOD = 20
N = 10_000

rng = np.random.default_rng(42)
series = rng.standard_normal(N).cumsum() + 100
df = pl.DataFrame({"close": series})

# ---- sanity check -----------------------------------------------------------
r_bearta  = df.with_columns(EMA(pl.col("close"), period=PERIOD))
r_talib   = df.with_columns(ta.ema(pl.col("close"), timeperiod=PERIOD))
r_polars  = df.with_columns(pl.col("close").ewm_mean(span=PERIOD, adjust=False))

print(f"N={N:,}  period={PERIOD}\n")
print("Last 3 values:")
print(f"  bearta:  {r_bearta['close'].tail(3).to_list()}")
print(f"  talib:   {r_talib['close'].tail(3).to_list()}")
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
bench("bearta EMA",    "df.with_columns(EMA(pl.col('close'), period=PERIOD))",                     dict(df=df, EMA=EMA, pl=pl, PERIOD=PERIOD))
bench("polars_talib",  "df.with_columns(ta.ema(pl.col('close'), timeperiod=PERIOD))",              dict(df=df, ta=ta, pl=pl, PERIOD=PERIOD))
bench("polars ewm_mean","df.with_columns(pl.col('close').ewm_mean(span=PERIOD, adjust=False))",    dict(df=df, pl=pl, PERIOD=PERIOD))
