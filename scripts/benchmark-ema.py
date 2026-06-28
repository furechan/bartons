"""
EMA benchmark: bartons vs polars built-in ewm_mean.

IMPORTANT: build the plugin in release mode first, e.g. `just bench`
(or `maturin develop --release`). A debug build (`just build` /
`maturin develop`) is ~20x slower and makes these numbers meaningless.

Note: bartons, polars ewm, and talib use different initialisation strategies:
  - bartons:    seeds EMA with first value, outputs after `period` steps
  - polars ewm: seeds with first value, outputs from row 0
  - talib ema:  seeds with the SMA of the first `period` values

Results are not numerically identical, but all are valid EMA variants.

polars_talib requires the TA-Lib C library: its prebuilt wheel leaves the
TA_* symbols undefined (no DT_NEEDED), so we preload libta-lib with
RTLD_GLOBAL before importing it. Install the lib with e.g.
`sudo apt-get install libta-lib0`. If unavailable, the talib rows are skipped.
"""

import ctypes
import timeit
import numpy as np
import polars as pl
from bartons.ema import EMA

# Preload TA-Lib so polars_talib's undefined TA_* symbols resolve, then import.
try:
    for _soname in ("libta-lib.so.0", "libta-lib.so", "libta_lib.so.0", "libta-lib.dylib"):
        try:
            ctypes.CDLL(_soname, mode=ctypes.RTLD_GLOBAL)
            break
        except OSError:
            continue
    import polars_talib as plta
    HAVE_TALIB = True
except ImportError as e:
    HAVE_TALIB = False
    print(f"(polars_talib unavailable, skipping talib rows: {e})\n")

PERIOD = 20
N = 10_000

rng = np.random.default_rng(42)
series = rng.standard_normal(N).cumsum() + 100
values = series.tolist()
values[0] = None  # force a null so the nullable code path is exercised
df = pl.DataFrame({"close": pl.Series("close", values, dtype=pl.Float64)})

# ---- sanity check -----------------------------------------------------------
r_bartons = df.with_columns(EMA(PERIOD))
r_polars  = df.with_columns(pl.col("close").ewm_mean(span=PERIOD, adjust=False))

print(f"N={N:,}  period={PERIOD}\n")
print("Last 3 values:")
print(f"  bartons: {r_bartons['close'].tail(3).to_list()}")
print(f"  pl.ewm:  {r_polars['close'].tail(3).to_list()}")
if HAVE_TALIB:
    r_talib = df.with_columns(plta.ema(pl.col("close"), timeperiod=PERIOD).alias("close"))
    print(f"  talib:   {r_talib['close'].tail(3).to_list()}")
print()

# ---- benchmark --------------------------------------------------------------
# We decompose the cost into:
#   1. construction  — building the Expr object (no data touched)
#   2. execution     — running a pre-built Expr over the data
#   3. build+execute — both together (what a naive benchmark measures)
# This isolates how much of bartons' cost is the plugin/expression boundary
# (paid once per Expr) vs the actual EMA computation.
REPEAT = 7
NUMBER = 20

def bench(label, stmt, globs):
    times = np.array(
        timeit.Timer(stmt, globals=globs).repeat(REPEAT, NUMBER)
    ) / NUMBER
    us = times * 1e6
    print(f"{label:<24}  min={min(us):8.1f}µs  mean={np.mean(us):8.1f}µs  std={np.std(us):6.1f}µs")

# Build the expressions once, outside the timed loop.
bartons_expr = EMA(PERIOD)
polars_expr  = pl.col("close").ewm_mean(span=PERIOD, adjust=False)
if HAVE_TALIB:
    talib_expr = plta.ema(pl.col("close"), timeperiod=PERIOD)

print("1. Construction only (build the Expr, no execution):")
bench("bartons EMA()",    "EMA(PERIOD)",                                         dict(EMA=EMA, PERIOD=PERIOD))
bench("polars ewm_mean()", "pl.col('close').ewm_mean(span=PERIOD, adjust=False)", dict(pl=pl, PERIOD=PERIOD))
if HAVE_TALIB:
    bench("talib ema()", "plta.ema(pl.col('close'), timeperiod=PERIOD)", dict(plta=plta, pl=pl, PERIOD=PERIOD))
print()

print("2. Execution only (pre-built Expr):")
bench("bartons EMA",    "df.with_columns(bartons_expr)", dict(df=df, bartons_expr=bartons_expr))
bench("polars ewm_mean", "df.with_columns(polars_expr)",  dict(df=df, polars_expr=polars_expr))
if HAVE_TALIB:
    bench("talib ema", "df.with_columns(talib_expr)", dict(df=df, talib_expr=talib_expr))
print()

print("3. Build + execute (naive benchmark, for reference):")
bench("bartons EMA",    "df.with_columns(EMA(PERIOD))",                                          dict(df=df, EMA=EMA, pl=pl, PERIOD=PERIOD))
bench("polars ewm_mean", "df.with_columns(pl.col('close').ewm_mean(span=PERIOD, adjust=False))", dict(df=df, pl=pl, PERIOD=PERIOD))
if HAVE_TALIB:
    bench("talib ema", "df.with_columns(plta.ema(pl.col('close'), timeperiod=PERIOD))", dict(df=df, plta=plta, pl=pl, PERIOD=PERIOD))
