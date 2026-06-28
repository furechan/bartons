"""
RMA benchmark: bartons vs polars ewm_mean (alpha = 1/period).

IMPORTANT: build the plugin in release mode first, e.g. `just bench rma`
(or `maturin develop --release`). A debug build (`just build-debug` /
`maturin develop`) is ~20x slower and makes these numbers meaningless.

RMA (Wilder's moving average) is an EMA with `alpha = 1/period`, so the closest
native baseline is `ewm_mean(alpha=1/period, adjust=False)`. They use different
seeding (bartons: SMA of the first `period`; polars: first value, output from
row 0), so early values differ but the tails converge — both valid variants.

There is no talib RMA (Wilder smoothing isn't exposed standalone), so talib is
not included here.
"""

import timeit
import numpy as np
import polars as pl
from bartons.rma import RMA

PERIOD = 20
N = 10_000
ALPHA = 1.0 / PERIOD

rng = np.random.default_rng(42)
series = rng.standard_normal(N).cumsum() + 100
values = series.tolist()
values[0] = None  # force a null so the nullable code path is exercised
df = pl.DataFrame({"close": pl.Series("close", values, dtype=pl.Float64)})

# ---- sanity check -----------------------------------------------------------
r_bartons = df.with_columns(RMA(PERIOD))
r_polars  = df.with_columns(pl.col("close").ewm_mean(alpha=ALPHA, adjust=False))

print(f"N={N:,}  period={PERIOD}  (alpha={ALPHA})\n")
print("Last 3 values:")
print(f"  bartons: {r_bartons['close'].tail(3).to_list()}")
print(f"  pl.ewm:  {r_polars['close'].tail(3).to_list()}")
print()

# ---- benchmark --------------------------------------------------------------
# We decompose the cost into:
#   1. construction  — building the Expr object (no data touched)
#   2. execution     — running a pre-built Expr over the data
#   3. build+execute — both together (what a naive benchmark measures)
REPEAT = 7
NUMBER = 20

def bench(label, stmt, globs):
    times = np.array(
        timeit.Timer(stmt, globals=globs).repeat(REPEAT, NUMBER)
    ) / NUMBER
    us = times * 1e6
    print(f"{label:<26}  min={min(us):8.1f}µs  mean={np.mean(us):8.1f}µs  std={np.std(us):6.1f}µs")

# Build the expressions once, outside the timed loop.
bartons_expr = RMA(PERIOD)
polars_expr  = pl.col("close").ewm_mean(alpha=ALPHA, adjust=False)

print("1. Construction only (build the Expr, no execution):")
bench("bartons RMA()",   "RMA(PERIOD)",                                      dict(RMA=RMA, PERIOD=PERIOD))
bench("polars ewm_mean()", "pl.col('close').ewm_mean(alpha=ALPHA, adjust=False)", dict(pl=pl, ALPHA=ALPHA))
print()

print("2. Execution only (pre-built Expr):")
bench("bartons RMA",     "df.with_columns(bartons_expr)", dict(df=df, bartons_expr=bartons_expr))
bench("polars ewm_mean", "df.with_columns(polars_expr)",  dict(df=df, polars_expr=polars_expr))
print()

print("3. Build + execute (naive benchmark, for reference):")
bench("bartons RMA",     "df.with_columns(RMA(PERIOD))",                                       dict(df=df, RMA=RMA, pl=pl, PERIOD=PERIOD))
bench("polars ewm_mean", "df.with_columns(pl.col('close').ewm_mean(alpha=ALPHA, adjust=False))", dict(df=df, pl=pl, ALPHA=ALPHA))
