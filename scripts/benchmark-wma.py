"""
WMA benchmark: bartons vs polars rolling_mean (linear weights).

IMPORTANT: build the plugin in release mode first, e.g. `just bench wma`
(or `maturin develop --release`). A debug build (`just build-debug` /
`maturin develop`) is ~20x slower and makes these numbers meaningless.

WMA weights each window value linearly (oldest weight 1 .. newest weight
`period`). The polars equivalent is `rolling_mean(window_size=period,
weights=[1..period])`; talib exposes it directly as `wma`. Warmup handling
differs slightly across implementations, but tail values match.

Unlike the other benchmarks, this one uses a null-free series: polars'
weighted `rolling_mean` raises "weights not yet supported on array with null
values". WMA's null handling is covered by tests/test_wma.py instead.

polars_talib requires the TA-Lib C library: its prebuilt wheel leaves the
TA_* symbols undefined (no DT_NEEDED), so we preload libta-lib with
RTLD_GLOBAL before importing it. Install the lib with e.g.
`sudo apt-get install libta-lib0`. If unavailable, the talib rows are skipped.
"""

import ctypes
import timeit
import numpy as np
import polars as pl
from bartons.wma import WMA

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
WEIGHTS = [float(i) for i in range(1, PERIOD + 1)]  # oldest .. newest

rng = np.random.default_rng(42)
series = rng.standard_normal(N).cumsum() + 100
# Null-free: polars' weighted rolling_mean does not support null inputs.
df = pl.DataFrame({"close": pl.Series("close", series, dtype=pl.Float64)})

# ---- sanity check -----------------------------------------------------------
r_bartons = df.with_columns(WMA(PERIOD))
r_polars  = df.with_columns(pl.col("close").rolling_mean(window_size=PERIOD, weights=WEIGHTS))

print(f"N={N:,}  period={PERIOD}\n")
print("Last 3 values:")
print(f"  bartons:    {r_bartons['close'].tail(3).to_list()}")
print(f"  pl.rolling: {r_polars['close'].tail(3).to_list()}")
if HAVE_TALIB:
    r_talib = df.with_columns(plta.wma(pl.col("close"), timeperiod=PERIOD).alias("close"))
    print(f"  talib:      {r_talib['close'].tail(3).to_list()}")
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
bartons_expr = WMA(PERIOD)
polars_expr  = pl.col("close").rolling_mean(window_size=PERIOD, weights=WEIGHTS)
if HAVE_TALIB:
    talib_expr = plta.wma(pl.col("close"), timeperiod=PERIOD)

print("1. Construction only (build the Expr, no execution):")
bench("bartons WMA()",       "WMA(PERIOD)",                                                dict(WMA=WMA, PERIOD=PERIOD))
bench("polars rolling_mean()", "pl.col('close').rolling_mean(window_size=PERIOD, weights=WEIGHTS)", dict(pl=pl, PERIOD=PERIOD, WEIGHTS=WEIGHTS))
if HAVE_TALIB:
    bench("talib wma()", "plta.wma(pl.col('close'), timeperiod=PERIOD)", dict(plta=plta, pl=pl, PERIOD=PERIOD))
print()

print("2. Execution only (pre-built Expr):")
bench("bartons WMA",         "df.with_columns(bartons_expr)", dict(df=df, bartons_expr=bartons_expr))
bench("polars rolling_mean", "df.with_columns(polars_expr)",  dict(df=df, polars_expr=polars_expr))
if HAVE_TALIB:
    bench("talib wma", "df.with_columns(talib_expr)", dict(df=df, talib_expr=talib_expr))
print()

print("3. Build + execute (naive benchmark, for reference):")
bench("bartons WMA",         "df.with_columns(WMA(PERIOD))",                                                       dict(df=df, WMA=WMA, pl=pl, PERIOD=PERIOD))
bench("polars rolling_mean", "df.with_columns(pl.col('close').rolling_mean(window_size=PERIOD, weights=WEIGHTS))", dict(df=df, pl=pl, PERIOD=PERIOD, WEIGHTS=WEIGHTS))
if HAVE_TALIB:
    bench("talib wma", "df.with_columns(plta.wma(pl.col('close'), timeperiod=PERIOD))", dict(df=df, plta=plta, pl=pl, PERIOD=PERIOD))
