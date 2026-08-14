# Retired: the `.bt` expression namespace

`bartons` used to register a custom polars expression namespace, giving every
`pl.Expr` a `.bt` accessor for the five single-source indicators:

```python
import bartons                       # import registered the namespace

pl.col("close").bt.ema(period=20)    # == EMA(20, src=pl.col("close"))
```

**Removed 2026-08-14.** This note keeps the implementation and the reasoning so
neither has to be reconstructed from git history.

## What it looked like

The whole module, `python/bartons/namespace.py`, as it stood at removal:

```python
import polars as pl

from . import indicators as ind


@pl.api.register_expr_namespace("bt")
class BartonsExprNamespace:
    def __init__(self, expr: pl.Expr):
        self._expr = expr

    def ema(self, period: int) -> pl.Expr:
        return ind.EMA(period, src=self._expr)

    def sma(self, period: int) -> pl.Expr:
        return ind.SMA(period, src=self._expr)

    def rma(self, period: int) -> pl.Expr:
        return ind.RMA(period, src=self._expr)

    def wma(self, period: int) -> pl.Expr:
        return ind.WMA(period, src=self._expr)

    def rsi(self, period: int) -> pl.Expr:
        return ind.RSI(period, src=self._expr)
```

Registration happened as an import side effect, from `bartons/__init__.py`:

```python
from . import namespace  # noqa: F401 — imported for its side effect
```

Every method was a one-line delegation to the corresponding factory, routing the
receiver expression in as `src`. That was deliberate: it kept the
`register_plugin_function` wiring in exactly one place per indicator. Only the
single-source indicators had methods — TRANGE and ATR are multi-input, and there
is no single receiver expression to bind.

## Why it was retired

**It could not be typed.** `@pl.api.register_expr_namespace` attaches the
accessor to `pl.Expr` at runtime. Polars ships `py.typed` with inline types and
no `.pyi` files, and Python stubs have no declaration-merging or partial-class
mechanism — so there is no way to tell a type checker that `pl.Expr` has a `bt`
member without shadowing `polars/expr/expr.pyi` wholesale and re-declaring every
method on `Expr`, which would go stale on each polars release. A PEP 561 partial
stub package does not help either: partial stubs fall back per *module*, not per
*class member*. mypy could paper over it with a plugin; `ty`, this project's
designated checker, has no plugin mechanism.

This is the same wall pandas accessors hit — `pandas-stubs` cannot type a
third-party `register_dataframe_accessor` either.

Concretely, `.bt` accounted for 7 of the 10 remaining `ty` diagnostics, and they
were the only ones with no path to resolution.

**It was the redundant surface.** Everything `.bt` did, the factories do, with
the same one-line call and full static checking:

```python
pl.col("close").bt.ema(20)      # retired
EMA(20, src=pl.col("close"))    # canonical
pl.col("close").pipe(EMA, 20)   # equivalent, and composes
```

The `pipe` form arrived with `wrap_src_indicator`, and it covers the ergonomic
niche `.bt` existed for — reading left-to-right from the source column — while
being an ordinary function call that `ty` can check end to end. Once the
factories became genuinely checkable (via the `SrcIndicator` protocol), keeping
an uncheckable parallel surface for the same five indicators stopped paying for
itself.

## If it is ever wanted back

The module above is complete and self-contained; restoring it means re-adding the
file and the side-effect import in `bartons/__init__.py`. The typing problem is
structural, though, and would come back with it — so the case for return would
have to rest on ergonomics alone, and would need a reason why
`pl.col("close").pipe(EMA, 20)` is not good enough.
