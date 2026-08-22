"""Speed benchmarks comparing bartons vs mintalib expressions.

bartons is a Rust polars plugin (single-pass streaming kernels); mintalib wraps
Cython kernels. Two scenarios: single symbol (~11k rows) and a 500-ticker synthetic
dataset with .over(). Each is measured twice with an explicit controlled chunk
count and after `.rechunk()` outside the timed region. Each scenario ends with an
"ALL combined" row — every indicator in one df.select(), showing how each backend
parallelises / CSEs across expressions vs the one-by-one sum. The first OHLC row of
each input series is null, so the benchmark does not give either backend a
clean-input-only fast path.

IMPORTANT: build the plugin in release mode first (`just develop` /
`maturin develop --release`); a debug build is ~20x slower and misleading.

Usage:
    uv run python benchmarks/benchmark-vs-mintalib.py
    uv run python benchmarks/benchmark-vs-mintalib.py --indicator RMA
    uv run python benchmarks/benchmark-vs-mintalib.py --no-over
"""

import argparse
import timeit

import polars as pl

from bartons.samples import random_prices
from bartons.indicators import ATR, CCI, EMA, KAMA, KER, RMA, RSI, SAR, SMA, TRANGE, WMA
from mintalib.expressions import (
    SMA as M_SMA, EMA as M_EMA, WMA as M_WMA, RMA as M_RMA,
    RSI as M_RSI, TRANGE as M_TRANGE, ATR as M_ATR, CCI as M_CCI,
    KER as M_KER, KAMA as M_KAMA, SAR as M_SAR,
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
    ("CCI(20)", CCI(20),  M_CCI(20)),
    # KER/KAMA are timing pairs only: mintalib's calc_ker spans period-1 changes
    # in the numerator against period in the denominator, so its numbers differ
    # from these. See CHANGELOG 0.1.2.
    ("KER(10)", KER(10),  M_KER(10)),
    ("KAMA(10)", KAMA(10), M_KAMA(10)),
    ("SAR", SAR(), M_SAR()),
]

SINGLE_ROWS = 11_006
SINGLE_CHUNKS = 178
OVER_TICKERS = 500
OVER_CHUNKS = 11

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

    prices_fragmented = random_prices(
        SINGLE_ROWS, n_chunks=SINGLE_CHUNKS, null_first=True
    )
    prices_contiguous = prices_fragmented.rechunk()

    print("\nWarming up ...")
    for _, b_expr, m_expr in pairs:
        prices_fragmented.select(b_expr)
        prices_fragmented.select(m_expr)
        prices_contiguous.select(b_expr)
        prices_contiguous.select(m_expr)

    for label, prices in (
        ("fragmented", prices_fragmented),
        ("rechunked", prices_contiguous),
    ):
        chunks = prices["close"].n_chunks()
        chunk_label = "chunk" if chunks == 1 else "chunks"
        print(
            f"\nScenario 1 — single symbol, {label}"
            f"  ({len(prices):,} rows, {chunks} {chunk_label})"
            f"  repeat={args.repeat}  number={args.number}\n"
        )
        run(prices, pairs, runner=bench, over=False, repeat=args.repeat, number=args.number)

    if not args.no_over:
        sp_fragmented = random_prices(
            SINGLE_ROWS,
            n_chunks=OVER_CHUNKS,
            n_tickers=OVER_TICKERS,
            null_first=True,
        )
        sp_contiguous = sp_fragmented.rechunk()
        n_tickers = sp_fragmented["ticker"].n_unique()

        print(f"\nWarming up .over() ...")
        for _, b_expr, m_expr in pairs:
            sp_fragmented.select(b_expr.over("ticker"))
            sp_fragmented.select(m_expr.over("ticker"))
            sp_contiguous.select(b_expr.over("ticker"))
            sp_contiguous.select(m_expr.over("ticker"))

        for label, sp in (
            ("fragmented", sp_fragmented),
            ("rechunked", sp_contiguous),
        ):
            chunks = sp["close"].n_chunks()
            chunk_label = "chunk" if chunks == 1 else "chunks"
            print(
                f"\nScenario 2 — {n_tickers} tickers .over(), {label}"
                f"  ({len(sp):,} rows, {chunks} {chunk_label})"
                "  repeat=3  number=1\n"
            )
            run(sp, pairs, runner=bench_over, over=True, repeat=3, number=1)

    print()


if __name__ == "__main__":
    main()
