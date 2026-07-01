"""Speed benchmarks comparing bartons vs native polars expressions.

bartons is a Rust polars plugin (single-pass streaming kernels); the baselines here
are built-in polars expressions — `rolling_mean`, `ewm_mean`, `rolling_mean(weights=)`
— or, where no single native method exists (RSI, TRANGE), a composition of native
exprs. Two scenarios: single symbol (~11k rows) and a 500-ticker synthetic dataset
with .over(). Each scenario ends with an "ALL combined" row — every indicator in one
df.select(), showing how each backend parallelises / CSEs across expressions vs the
one-by-one sum.

Seeding/warmup differs between bartons and the native baselines (e.g. bartons emits
null until `period` values; ewm_mean outputs from row 0), so early rows differ — this
measures speed, not equality. See benchmark-rsi.py for the value cross-check.

IMPORTANT: build the plugin in release mode first (`just build` /
`maturin develop --release`); a debug build is ~20x slower and misleading.

Usage:
    uv run python scripts/benchmark-vs-native.py
    uv run python scripts/benchmark-vs-native.py --indicator RSI
    uv run python scripts/benchmark-vs-native.py --no-over
"""

import argparse
import timeit

import polars as pl

from bartons.samples import sample_prices, sample_dataset
from bartons.expressions import EMA, SMA, RMA, WMA, RSI, TRANGE, ATR


# ── Native polars equivalents ───────────────────────────────────────────────────

def native_rsi(period: int) -> pl.Expr:
    """Wilder RSI composed from ewm_mean (alpha = 1/period)."""
    alpha = 1.0 / period
    delta = pl.col("close").diff()
    gain = delta.clip(lower_bound=0.0).ewm_mean(alpha=alpha, adjust=False)
    loss = (-delta).clip(lower_bound=0.0).ewm_mean(alpha=alpha, adjust=False)
    return 100.0 * gain / (gain + loss)


def native_trange() -> pl.Expr:
    """True Range composed from native exprs."""
    high, low, close = pl.col("high"), pl.col("low"), pl.col("close")
    prev_close = close.shift(1)
    return pl.max_horizontal(
        high - low, (high - prev_close).abs(), (low - prev_close).abs()
    )


def native_atr(period: int) -> pl.Expr:
    """ATR = Wilder RMA (ewm_mean alpha = 1/period) of the native True Range."""
    return native_trange().ewm_mean(alpha=1.0 / period, adjust=False)


# ── Benchmark pairs ────────────────────────────────────────────────────────────

PAIRS = [
    ("SMA(20)", SMA(20),  pl.col("close").rolling_mean(20)),
    ("EMA(20)", EMA(20),  pl.col("close").ewm_mean(span=20, adjust=False)),
    ("RMA(20)", RMA(20),  pl.col("close").ewm_mean(alpha=1.0 / 20, adjust=False)),
    ("WMA(20)", WMA(20),  pl.col("close").rolling_mean(20, weights=list(range(1, 21)))),
    ("RSI(14)", RSI(14),  native_rsi(14)),
    ("TRANGE",  TRANGE(), native_trange()),
    ("ATR(14)", ATR(14),  native_atr(14)),
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


def bench_combined(
    df: pl.DataFrame, exprs: list, *, over: bool, repeat: int, number: int
) -> float:
    """Time a single df.select() of all exprs at once (polars batches them)."""
    sel = [e.over("ticker") for e in exprs] if over else exprs
    times = timeit.repeat(lambda: df.select(sel), repeat=repeat, number=number)
    return min(times) / number


def run(df: pl.DataFrame, pairs: list, *, runner, over: bool, repeat: int, number: int) -> None:
    hdr = f"  {'indicator':<12}  {'bartons':>10}  {'native':>10}  {'ratio':>7}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    bs, ns, ratios = [], [], []
    for name, b_expr, n_expr in pairs:
        try:
            t_b = runner(df, b_expr, repeat=repeat, number=number)
            t_n = runner(df, n_expr, repeat=repeat, number=number)
        except Exception as e:
            print(f"  {name:<12}  skipped ({e})")
            continue
        bs.append(t_b); ns.append(t_n); ratios.append(t_b / t_n)
        print(f"  {name:<12}  {fmt_ms(t_b):>10}  {fmt_ms(t_n):>10}  {t_b / t_n:>7.2f}")
    if len(ratios) > 1:
        def mean(xs):
            return sum(xs) / len(xs)

        # Average and combined: two summary rows, column-aligned with the rows above.
        print("  " + "-" * (len(hdr) - 2))
        print(f"  {'Average':<12}  {fmt_ms(mean(bs)):>10}  {fmt_ms(mean(ns)):>10}  {mean(ratios):>7.2f}")

        # Combined: all indicators in one select (alias so names stay unique).
        # Shows whether each backend parallelises / CSEs across expressions vs
        # the one-by-one sum above.
        b_exprs = [b.alias(n) for n, b, _ in pairs]
        n_exprs = [e.alias(n) for n, _, e in pairs]
        try:
            t_b = bench_combined(df, b_exprs, over=over, repeat=repeat, number=number)
            t_n = bench_combined(df, n_exprs, over=over, repeat=repeat, number=number)
            print(f"  {'ALL combined':<12}  {fmt_ms(t_b):>10}  {fmt_ms(t_n):>10}  {t_b / t_n:>7.2f}")
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
        pairs = [(n, b, e) for n, b, e in PAIRS if n.upper().split("(")[0] == key]
        if not pairs:
            raise SystemExit(f"No benchmark found for {args.indicator!r}")

    prices = sample_prices()

    print("\nWarming up ...")
    for _, b_expr, n_expr in pairs:
        prices.select(b_expr)
        prices.select(n_expr)

    print(f"\nScenario 1 — single symbol  ({len(prices):,} rows)"
          f"  repeat={args.repeat}  number={args.number}\n")
    run(prices, pairs, runner=bench, over=False, repeat=args.repeat, number=args.number)

    if not args.no_over:
        sp = sample_dataset()
        n_tickers = sp["ticker"].n_unique()

        print(f"\nWarming up .over() ...")
        for _, b_expr, n_expr in pairs:
            sp.select(b_expr.over("ticker"))
            sp.select(n_expr.over("ticker"))

        print(f"\nScenario 2 — {n_tickers} tickers .over()  ({len(sp):,} rows)"
              f"  repeat=3  number=1\n")
        run(sp, pairs, runner=bench_over, over=True, repeat=3, number=1)

    print()


if __name__ == "__main__":
    main()
