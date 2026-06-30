# Changelog

## 0.1.0

- Refactor all indicator kernels onto a streaming-filter pattern. Each indicator
  is now a polars-free struct (`EmaFilter`, `SmaFilter`, `RmaFilter`, `WmaFilter`,
  `TrangeFilter`) with a `new` constructor and a `next` step method, holding its
  own run state.
- Add `bartons/src/utils.rs` with the shared `Filter` trait and the `run_unary`
  and `run_ternary` drivers, which own the cast / iterate / build-with-nulls
  scaffolding. The unary indicators (EMA, SMA, RMA, WMA) implement `Filter` and
  are driven by `run_unary`; TRANGE uses the closure-based `run_ternary`.
- Move period validation out of the kernels: `*Filter::new` returns
  `Result<Self, String>` and the `calc_*` boundary maps the error to
  `PolarsError::ComputeError`, keeping the filters independent of polars.
