"""Speed benchmarks comparing bartons vs polars_talib (Rust plugin wrapping C TA-Lib).

bartons is a Rust polars plugin (single-pass streaming kernels); polars_talib also
stays inside the polars engine, wrapping the C TA-Lib. Two scenarios: single symbol
(~11k rows) and a 500-ticker synthetic dataset with .over(). Each scenario ends with
an "ALL combined" row — every indicator in one df.select(), showing how each backend
parallelises / CSEs across expressions vs the one-by-one sum.

The first OHLC row of each input series is null. The `talib` column is raw
polars_talib, which represents warmup/gaps as NaN in the values buffer (no validity
bitmap) — numpy-style, not polars nulls. bartons instead emits real nulls inline.
So `talib+fill_nan` is the closest output-representation comparison: raw talib plus
`.fill_nan(None)`. `r(raw)` compares against raw talib, `r(fair)` against
talib+fill_nan (both bartons/other, <1 = bartons faster). This exercises only a leading
input null; talib still can't handle *interior* nulls equivalently even with
`fill_nan`.

RMA has no TA-Lib equivalent (Wilder smoothing isn't exposed standalone), so it is
covered only in benchmark-vs-mintalib.py.

IMPORTANT: build the plugin in release mode first (`just develop` /
`maturin develop --release`); a debug build is ~20x slower and misleading.

Usage:
    uv run python scripts/benchmark-vs-talib.py
    uv run python scripts/benchmark-vs-talib.py --indicator RSI
    uv run python scripts/benchmark-vs-talib.py --no-over
"""

import argparse
import timeit

import polars as pl


def _import_polars_talib():
    """Import polars_talib, preloading the bundled TA-Lib C library if needed.

    polars_talib's prebuilt wheel leaves the TA-Lib C symbols undefined and
    expects the library in the *global* symbol namespace. The `ta-lib` package
    ships that C lib, but Python loads extension modules RTLD_LOCAL, so the
    symbols stay invisible. On ImportError, preload it RTLD_GLOBAL and retry.
    """
    try:
        import polars_talib as pta
    except ImportError:
        import ctypes, glob, os, sysconfig

        site = sysconfig.get_paths()["purelib"]
        matches = glob.glob(os.path.join(site, "ta_lib.libs", "libta-lib*.so*"))
        if not matches:
            raise
        ctypes.CDLL(matches[0], mode=ctypes.RTLD_GLOBAL)
        import polars_talib as pta
    return pta


pta = _import_polars_talib()

from bartons.samples import sample_prices, sample_dataset
from bartons.indicators import ATR, CCI, EMA, RSI, SMA, TRANGE, WMA

# ── Benchmark pairs ────────────────────────────────────────────────────────────

PAIRS = [
    ("SMA(20)", SMA(20),  pta.sma(timeperiod=20)),
    ("EMA(20)", EMA(20),  pta.ema(timeperiod=20)),
    ("WMA(20)", WMA(20),  pta.wma(timeperiod=20)),
    ("RSI(14)", RSI(14),  pta.rsi(timeperiod=14)),
    ("TRANGE",  TRANGE(), pta.trange()),
    ("ATR(14)", ATR(14),  pta.atr(timeperiod=14)),
    ("CCI(20)", CCI(20),  pta.cci(timeperiod=20)),
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def bench(df: pl.DataFrame, expr: pl.Expr, *, repeat: int = 5, number: int = 10) -> float:
    times = timeit.repeat(lambda: df.select(expr), repeat=repeat, number=number)
    return min(times) / number


def bench_over(df: pl.DataFrame, expr: pl.Expr, *, repeat: int = 3, number: int = 1) -> float:
    times = timeit.repeat(lambda: df.select(expr.over("ticker")), repeat=repeat, number=number)
    return min(times) / number


def fmt_ms(s: float) -> str:
    return f"{s * 1000:.3f}"


def null_first_ohlc_row(df: pl.DataFrame) -> pl.DataFrame:
    """Set the first chronological OHLC row to null in each input series."""
    time_col = "date" if "date" in df.columns else "datetime"
    first = pl.col(time_col) == (
        pl.col(time_col).min().over("ticker")
        if "ticker" in df.columns
        else pl.col(time_col).min()
    )
    return df.with_columns(
        pl.when(first).then(None).otherwise(pl.col(column)).alias(column)
        for column in ("open", "high", "low", "close")
    )


def bench_combined(
    df: pl.DataFrame, exprs: list, *, over: bool, repeat: int, number: int
) -> float:
    """Time a single df.select() of all exprs at once (polars batches them)."""
    sel = [e.over("ticker") for e in exprs] if over else exprs
    times = timeit.repeat(lambda: df.select(sel), repeat=repeat, number=number)
    return min(times) / number


def run(df: pl.DataFrame, pairs: list, *, runner, over: bool, repeat: int, number: int) -> None:
    hdr = f"  {'indicator':<12}  {'bartons':>10}  {'talib':>10}  {'talib+fill_nan':>14}  {'r(raw)':>7}  {'r(fair)':>7}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    bs, ts, ns, r_raw, r_fair = [], [], [], [], []
    for name, b_expr, t_expr in pairs:
        try:
            t_b = runner(df, b_expr, repeat=repeat, number=number)
            t_t = runner(df, t_expr, repeat=repeat, number=number)
            t_n = runner(df, t_expr.fill_nan(None), repeat=repeat, number=number)
        except Exception as e:
            print(f"  {name:<12}  skipped ({e})")
            continue
        bs.append(t_b); ts.append(t_t); ns.append(t_n)
        r_raw.append(t_b / t_t)
        r_fair.append(t_b / t_n)
        print(f"  {name:<12}  {fmt_ms(t_b):>10}  {fmt_ms(t_t):>10}  {fmt_ms(t_n):>14}  {t_b / t_t:>7.2f}  {t_b / t_n:>7.2f}")
    if len(r_raw) > 1:
        def mean(xs):
            return sum(xs) / len(xs)

        # Average and combined: two summary rows, column-aligned with the rows above.
        print("  " + "-" * (len(hdr) - 2))
        print(f"  {'Average':<12}  {fmt_ms(mean(bs)):>10}  {fmt_ms(mean(ts)):>10}  {fmt_ms(mean(ns)):>14}  {mean(r_raw):>7.2f}  {mean(r_fair):>7.2f}")

        # Combined: all indicators in one select (alias so names stay unique).
        # Shows whether each backend parallelises / CSEs across expressions vs
        # the one-by-one sum above.
        b_exprs = [b.alias(n) for n, b, _ in pairs]
        t_exprs = [t.alias(n) for n, _, t in pairs]
        n_exprs = [t.fill_nan(None).alias(n) for n, _, t in pairs]
        try:
            t_b = bench_combined(df, b_exprs, over=over, repeat=repeat, number=number)
            t_t = bench_combined(df, t_exprs, over=over, repeat=repeat, number=number)
            t_n = bench_combined(df, n_exprs, over=over, repeat=repeat, number=number)
            print(f"  {'ALL combined':<12}  {fmt_ms(t_b):>10}  {fmt_ms(t_t):>10}  {fmt_ms(t_n):>14}  {t_b / t_t:>7.2f}  {t_b / t_n:>7.2f}")
        except Exception as e:
            print(f"  {'ALL combined':<12}  skipped ({e})")

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--indicator", help="Filter to one indicator (case-insensitive prefix, e.g. RSI)")
    parser.add_argument("--no-over",  action="store_true", help="Skip the .over('ticker') scenario")
    parser.add_argument("--repeat",   type=int, default=5,  help="timeit repeat (default: 5)")
    parser.add_argument("--number",   type=int, default=10, help="timeit number per repeat (default: 10)")
    args = parser.parse_args()

    pairs = PAIRS
    if args.indicator:
        key = args.indicator.upper()
        pairs = [(n, b, t) for n, b, t in PAIRS if n.upper().split("(")[0] == key]
        if not pairs:
            raise SystemExit(f"No benchmark found for {args.indicator!r}")

    prices = null_first_ohlc_row(sample_prices())

    print("\nWarming up ...")
    for _, b_expr, t_expr in pairs:
        try:
            prices.select(b_expr)
            prices.select(t_expr)
        except Exception:
            pass

    print(f"\nScenario 1 — single symbol  ({len(prices):,} rows)"
          f"  repeat={args.repeat}  number={args.number}\n")
    run(prices, pairs, runner=bench, over=False, repeat=args.repeat, number=args.number)

    if not args.no_over:
        sp = null_first_ohlc_row(sample_dataset())
        n_tickers = sp["ticker"].n_unique()

        print(f"\nWarming up .over() ...")
        for _, b_expr, t_expr in pairs:
            try:
                sp.select(b_expr.over("ticker"))
                sp.select(t_expr.over("ticker"))
            except Exception:
                pass

        print(f"\nScenario 2 — {n_tickers} tickers .over()  ({len(sp):,} rows)"
              f"  repeat=3  number=1\n")
        run(sp, pairs, runner=bench_over, over=True, repeat=3, number=1)

    print()


if __name__ == "__main__":
    main()
