"""
RSI benchmark: bartons vs a native-polars composition vs talib.

IMPORTANT: build the plugin in release mode first, e.g. `just bench rsi`
(or `maturin develop --release`). A debug build (`just build-debug` /
`maturin develop`) is ~20x slower and makes these numbers meaningless.

polars has no built-in RSI, so the native baseline composes one from `ewm_mean`:
Wilder-smoothed average gain / loss with `alpha = 1/period`, then
`100 * avg_gain / (avg_gain + avg_loss)`. bartons and talib seed the averages
with the SMA of the first `period` changes; the polars composition seeds
`ewm_mean` from the first value, so early rows differ but the tails converge.
bartons and talib should agree closely (both Wilder RSI).

polars_talib requires the TA-Lib C library: its prebuilt wheel leaves the
TA_* symbols undefined (no DT_NEEDED), so we preload libta-lib with
RTLD_GLOBAL before importing it. The `ta-lib` dev dependency bundles that C
library inside its wheel (auditwheel-vendored under `ta_lib.libs/`), so no
system install is needed — we locate and preload it. A system libta-lib is
tried first if present. If neither is found, the talib rows are skipped.
"""

import ctypes
import glob
import importlib.util
import os
import timeit
import numpy as np
import polars as pl
from bartons.rsi import RSI


def _preload_libta_lib():
    """Load libta-lib with global symbol visibility so polars_talib's undefined
    TA_* symbols resolve. Tries a system install first, then the copy bundled in
    the `ta-lib` wheel (whose filename auditwheel hashes, so we glob for it)."""
    for soname in ("libta-lib.so.0", "libta-lib.so", "libta_lib.so.0", "libta-lib.dylib"):
        try:
            ctypes.CDLL(soname, mode=ctypes.RTLD_GLOBAL)
            return
        except OSError:
            continue
    spec = importlib.util.find_spec("talib")
    if spec and spec.origin:
        root = os.path.dirname(os.path.dirname(spec.origin))
        for path in glob.glob(os.path.join(root, "ta_lib.libs", "libta-lib*.so*")):
            ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
            return


# Preload TA-Lib so polars_talib's undefined TA_* symbols resolve, then import.
try:
    _preload_libta_lib()
    import polars_talib as plta
    HAVE_TALIB = True
except (ImportError, OSError) as e:
    HAVE_TALIB = False
    print(f"(polars_talib unavailable, skipping talib rows: {e})\n")

PERIOD = 14
N = 10_000

rng = np.random.default_rng(42)
series = rng.standard_normal(N).cumsum() + 100
values = series.tolist()
values[0] = None  # force a null so the nullable code path is exercised
df = pl.DataFrame({"close": pl.Series("close", values, dtype=pl.Float64)})


def polars_rsi(period):
    """Native-polars RSI composed from ewm_mean (Wilder alpha = 1/period)."""
    alpha = 1.0 / period
    delta = pl.col("close").diff()
    gain = delta.clip(lower_bound=0.0).ewm_mean(alpha=alpha, adjust=False)
    loss = (-delta).clip(lower_bound=0.0).ewm_mean(alpha=alpha, adjust=False)
    return (100.0 * gain / (gain + loss)).alias("close")


# ---- sanity check -----------------------------------------------------------
r_bartons = df.with_columns(RSI(PERIOD))
r_polars  = df.with_columns(polars_rsi(PERIOD))

print(f"N={N:,}  period={PERIOD}\n")
print("Last 3 values:")
print(f"  bartons: {r_bartons['close'].tail(3).to_list()}")
print(f"  pl.ewm:  {r_polars['close'].tail(3).to_list()}")
if HAVE_TALIB:
    r_talib = df.with_columns(plta.rsi(pl.col("close"), timeperiod=PERIOD).alias("close"))
    print(f"  talib:   {r_talib['close'].tail(3).to_list()}")
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
bartons_expr = RSI(PERIOD)
polars_expr  = polars_rsi(PERIOD)
if HAVE_TALIB:
    talib_expr = plta.rsi(pl.col("close"), timeperiod=PERIOD)

print("1. Construction only (build the Expr, no execution):")
bench("bartons RSI()",       "RSI(PERIOD)",           dict(RSI=RSI, PERIOD=PERIOD))
bench("polars rsi (compose)", "polars_rsi(PERIOD)",   dict(polars_rsi=polars_rsi, PERIOD=PERIOD))
if HAVE_TALIB:
    bench("talib rsi()", "plta.rsi(pl.col('close'), timeperiod=PERIOD)", dict(plta=plta, pl=pl, PERIOD=PERIOD))
print()

print("2. Execution only (pre-built Expr):")
bench("bartons RSI",        "df.with_columns(bartons_expr)", dict(df=df, bartons_expr=bartons_expr))
bench("polars rsi (compose)", "df.with_columns(polars_expr)", dict(df=df, polars_expr=polars_expr))
if HAVE_TALIB:
    bench("talib rsi", "df.with_columns(talib_expr)", dict(df=df, talib_expr=talib_expr))
print()

print("3. Build + execute (naive benchmark, for reference):")
bench("bartons RSI",        "df.with_columns(RSI(PERIOD))",            dict(df=df, RSI=RSI, PERIOD=PERIOD))
bench("polars rsi (compose)", "df.with_columns(polars_rsi(PERIOD))",   dict(df=df, polars_rsi=polars_rsi, PERIOD=PERIOD))
if HAVE_TALIB:
    bench("talib rsi", "df.with_columns(plta.rsi(pl.col('close'), timeperiod=PERIOD))", dict(df=df, plta=plta, pl=pl, PERIOD=PERIOD))
