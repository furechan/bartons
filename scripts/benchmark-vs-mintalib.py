"""Speed benchmarks comparing bartons vs mintalib expressions.

bartons is a Rust polars plugin (single-pass streaming kernels); mintalib wraps
Cython kernels. Two scenarios: single symbol (~11k rows) and a 500-ticker synthetic
dataset with .over(). Each scenario ends with an "ALL combined" row — every indicator
in one df.select(), showing how each backend parallelises / CSEs across expressions vs
the one-by-one sum.

IMPORTANT: build the plugin in release mode first (`just develop` /
`maturin develop --release`); a debug build is ~20x slower and misleading.

Usage:
    uv run python scripts/benchmark-vs-mintalib.py
    uv run python scripts/benchmark-vs-mintalib.py --indicator RMA
    uv run python scripts/benchmark-vs-mintalib.py --no-over
"""

import argparse
import timeit

import polars as pl

from bartons.samples import sample_prices, sample_dataset
from bartons.indicators import EMA, SMA, RMA, WMA, RSI, TRANGE, ATR
from mintalib.expressions import (
    SMA as M_SMA, EMA as M_EMA, WMA as M_WMA, RMA as M_RMA,
    RSI as M_RSI, TRANGE as M_TRANGE, ATR as M_ATR,
)

# ── Benchmark pairs ────────────────────────────────────────────────────────────

PAIRS = [
    ("SMA(20)", SMA(20),  M_SMA(20)),
    ("EMA(20)", EMA(20),  M_EMA(20)),
    ("WMA(20)", WMA(20),  M_WMA(20)),
    ("RMA(20)", RMA(20),  M_RMA(20)),
    ("RSI(14)", RSI(14),  M_RSI(14)),
    ("TRANGE",  TRANGE(), M_TRANGE()),
    ("ATR(14)", ATR(14),  M_ATR(14)),
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
    hdr = f"  {'indicator':<12}  {'bartons':>10}  {'mintalib':>10}  {'ratio':>7}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    bs, ms, ratios = [], [], []
    for name, b_expr, m_expr in pairs:
        try:
            t_b = runner(df, b_expr, repeat=repeat, number=number)
            t_m = runner(df, m_expr, repeat=repeat, number=number)
        except Exception as e:
            print(f"  {name:<12}  skipped ({e})")
            continue
        bs.append(t_b); ms.append(t_m); ratios.append(t_b / t_m)
        print(f"  {name:<12}  {fmt_ms(t_b):>10}  {fmt_ms(t_m):>10}  {t_b / t_m:>7.2f}")
    if len(ratios) > 1:
        def mean(xs):
            return sum(xs) / len(xs)

        # Average and combined: two summary rows, column-aligned with the rows above.
        print("  " + "-" * (len(hdr) - 2))
        print(f"  {'Average':<12}  {fmt_ms(mean(bs)):>10}  {fmt_ms(mean(ms)):>10}  {mean(ratios):>7.2f}")

        # Combined: all indicators in one select (alias so names stay unique).
        # Shows whether each backend parallelises / CSEs across expressions vs
        # the one-by-one sum above.
        b_exprs = [b.alias(n) for n, b, _ in pairs]
        m_exprs = [m.alias(n) for n, _, m in pairs]
        try:
            t_b = bench_combined(df, b_exprs, over=over, repeat=repeat, number=number)
            t_m = bench_combined(df, m_exprs, over=over, repeat=repeat, number=number)
            print(f"  {'ALL combined':<12}  {fmt_ms(t_b):>10}  {fmt_ms(t_m):>10}  {t_b / t_m:>7.2f}")
        except Exception as e:
            print(f"  {'ALL combined':<12}  skipped ({e})")

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--indicator", help="Filter to one indicator (case-insensitive prefix, e.g. RMA)")
    parser.add_argument("--no-over",  action="store_true", help="Skip the .over('ticker') scenario")
    parser.add_argument("--repeat",   type=int, default=5,  help="timeit repeat (default: 5)")
    parser.add_argument("--number",   type=int, default=10, help="timeit number per repeat (default: 10)")
    args = parser.parse_args()

    pairs = PAIRS
    if args.indicator:
        key = args.indicator.upper()
        pairs = [(n, b, m) for n, b, m in PAIRS if n.upper().split("(")[0] == key]
        if not pairs:
            raise SystemExit(f"No benchmark found for {args.indicator!r}")

    prices = sample_prices()

    print("\nWarming up ...")
    for _, b_expr, m_expr in pairs:
        prices.select(b_expr)
        prices.select(m_expr)

    print(f"\nScenario 1 — single symbol  ({len(prices):,} rows)"
          f"  repeat={args.repeat}  number={args.number}\n")
    run(prices, pairs, runner=bench, over=False, repeat=args.repeat, number=args.number)

    if not args.no_over:
        sp = sample_dataset()
        n_tickers = sp["ticker"].n_unique()

        print(f"\nWarming up .over() ...")
        for _, b_expr, m_expr in pairs:
            sp.select(b_expr.over("ticker"))
            sp.select(m_expr.over("ticker"))

        print(f"\nScenario 2 — {n_tickers} tickers .over()  ({len(sp):,} rows)"
              f"  repeat=3  number=1\n")
        run(sp, pairs, runner=bench_over, over=True, repeat=3, number=1)

    print()


if __name__ == "__main__":
    main()
