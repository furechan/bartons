# Polars expression-plugin CSE regression

Recorded 2026-09-16. Upstream status was checked on that date; version-test results below come from the original issue report and were not rerun while writing this note.

## Upstream issue

[Polars #29165: Expression plugins lost CSE in 1.41 with no way to declare an FFI plugin deterministic](https://github.com/pola-rs/polars/issues/29165), opened by `furechan` on 2026-09-04. Versions here refer to polars-py, not polars-rs. The regression boundary is **1.41**, not 1.14.

The report identifies unconditional classification of `IRFunctionExpr::FfiPlugin` as inherently nondeterministic as the reason expression common-subexpression elimination (CSE) excludes plugins. At the time of the investigation, `register_plugin_function` exposed no determinism option for plugins to opt back in.

## Recorded evidence

The issue's reproduction uses `bartons==0.1.7` and compares optimized lazy plans. Reusing a single `SMA(2)` expression under two aliases produces one plugin occurrence through 1.40.1, but two starting with the tested 1.41 releases. Separately constructed equivalent expressions behave the same way. Selecting multiple fields from a reused `DMI` struct expression also duplicates the plugin subtree.

| Tested polars-py versions | Reported plugin CSE |
|---|---|
| 1.28.0, 1.30.0, 1.32.0, 1.34.0, 1.38.1, 1.39.0, 1.40.0, 1.40.1 | Applied |
| 1.41.1, 1.41.2, 1.42.0, 1.43.2 | Not applied |

The report did not test 1.41.0 because its PyPI runtime wheel was yanked. These are optimized-plan observations, not direct runtime invocation counts or timing measurements.

Local examples live in [playground/cse-findings.ipynb](../../playground/cse-findings.ipynb), added in commit `6483af5` on 2026-09-07. They cover repeated native expressions, repeated SMA plugins, DMI field extraction, window boundaries, and explicit intermediate columns. The notebook does not contain the cross-version test matrix.

## Discussion and status

- 2026-09-06: [`webdevsamran` volunteered](https://github.com/pola-rs/polars/issues/29165#issuecomment-5560817748) to implement `FunctionFlags::DETERMINISTIC`, expose `is_deterministic=False`, and add plugin integration tests.
- 2026-09-07: [maintainer `orlp` supported the flag](https://github.com/pola-rs/polars/issues/29165#issuecomment-5571980857), with allowance for negligible floating-point ordering differences.
- 2026-09-12: [`furechan` asked for restoration of the prior behavior](https://github.com/pola-rs/polars/issues/29165#issuecomment-5645713781), pointing to #26253 and #27687 and the CSE exception for opaque Python UDFs. The follow-up asks whether FFI plugins could receive the same exception pending a consistent determinism API.
- As checked on 2026-09-16: open, unassigned, and no reply to the September 12 follow-up. No linked implementation PR was found in the issue timeline or the PR search performed that day. Maintainer support for a flag does not establish agreement to restore the old default behavior.

## Workaround and limits

Materialize a shared plugin result as an intermediate column before selecting its fields:

```python
from bartons.indicators import DMI
import polars as pl

query = (
    prices.with_columns(DMI(14).alias("_dmi"))
    .select(
        pl.col("_dmi").struct.field("adx"),
        pl.col("_dmi").struct.field("pdi"),
    )
)
```

Here `prices` is a LazyFrame containing the required OHLC columns. The intermediate column expresses sharing explicitly; reusing a Python `Expr` object alone does not. Use a temporary name that does not collide with an existing column.

Do not mark stateful indicators `is_elementwise=True` to seek CSE: elementwise semantics and determinism are different contracts. The notebook also records `.over(...)` as a separate CSE traversal boundary, so restoring plugin eligibility would not by itself establish sharing across windows.

Before revisiting a workaround or adopting a future determinism flag, check the issue and linked implementation again and rerun the notebook against the actual installed Polars version. This note records an investigation, not a guarantee about later releases.
