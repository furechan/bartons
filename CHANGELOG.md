# Changelog

## 0.1.2

- Publish the public GitHub repository, issue tracker and changelog in package
  metadata, and link the README to the public project resources, supported wheel
  platforms, development workflow and license.

- Adopt the dispatch-only GitHub Actions build and trusted-publishing workflows
  as the sole release path, recording the first partial upload and its recovery.

- Include `LICENSE.txt` in the sdist so its contents satisfy the PEP 639
  `License-File` metadata and PyPI accepts the source archive.

- Add `uv run inv bump` as the explicit post-publish patch-version command and
  have the local publisher reuse it.

- Restore the CI release matrix's macOS x86_64 artifact by moving its build
  from GitHub's retired `macos-13` runner to `macos-15-intel`.

- Harden CI artifact builds by pinning `maturin-action` and Maturin, requiring
  the Cargo lockfile, and enabling Maturin's PyPI compatibility validation.

- Build the Linux aarch64 wheel on a native GitHub ARM64 runner and require it
  to pass the same installation, import, and pytest smoke test as every wheel.

- Express the wheel targets as native YAML matrices instead of generating JSON
  with an inline Python setup job.

- Let the CI publisher skip files already present on PyPI instead of rejecting
  the release version during its guard step.

- Label build runs with their requested scope and resolve publication directly
  to the newest successful full build instead of inspecting every artifact set.

- **Add expression-native `MOM`.** Momentum delegates the difference from a
  lagged value to Polars `diff` and requires no dedicated kernel.

- **Add expression-native `WILLR`.** Williams %R composes native rolling high
  and low extrema and requires no dedicated kernel.

- **Add the `AROON` kernel.** One high/low ring buffer holds `period + 1`
  observations and finds the most recent rolling extremes in one
  oldest-to-newest traversal. It returns an `aroondown`/`aroonup` struct and
  matches TA-Lib's window and tie conventions. The expression-native
  `AROONOSC` indicator subtracts those two fields without another kernel.

- **Add expression-native `ADL` and `ADOSC`.** The Accumulation/Distribution
  Line cumulatively sums HLCV money-flow volume, while the Chaikin oscillator
  composes fast and slow EMA kernels over that line. Neither requires a new
  kernel.

- **Add expression-native `BOP`.** Balance of Power is the unsmoothed per-bar
  `(close - open) / (high - low)` expression. Smoothing remains an explicit
  composition such as `SMA(20, src=BOP())`.

- **Add expression-native `NATR`.** Normalized ATR lives alongside `ATR` and
  returns the raw `ATR / close` ratio. Scaling to percentage points remains
  explicit and no additional kernel is introduced.

- **Add expression-native `PPO`.** The scalar Price Percentage Oscillator
  composes fast and slow EMA kernels and returns their raw fractional spread.
  Scaling to percentage points remains explicit and no dedicated kernel is
  added.

- **Add expression-native `CMF`.** Chaikin Money Flow composes the HLC money
  flow multiplier with volume and native rolling sums. It accepts configurable
  HLCV expressions and requires no dedicated kernel.

- **Add expression-native `DONCHIAN`.** Donchian Channels compose rolling high
  and low extrema into an `upperband`, `middleband`, and `lowerband` struct,
  without wrapping native Polars extrema in dedicated kernels.

- **Add expression-native `OBV`.** On-Balance Volume maps close direction to
  signed volume and delegates accumulation to Polars `cum_sum`. The first row
  and incomplete changes remain null while later rows resume the running sum.

- **Add expression-native `KELTNER`.** Keltner Channels compose the existing
  typical-price, EMA, and ATR expressions into an `upperband`, `middleband`, and
  `lowerband` struct. Its high, low, and close inputs remain configurable,
  without adding a dedicated Rust kernel.

- **Add expression-native `ROC`.** Raw fractional rate of change delegates to
  Polars `pct_change`, supports arbitrary expressions and periods, and preserves
  native null and floating-point behavior without a Rust kernel. Scaling for
  display is deliberately left to callers.

- **Centralize expression input conversion.** `bartons.typing.into_expr` is now
  the runtime counterpart to `IntoExprColumn`, converting column names and
  Series where Python composition requires a concrete `pl.Expr` and replacing
  local `_expr` helpers. Plugin-backed indicators continue passing inputs to
  `register_plugin_function`, which already owns that conversion boundary.

- **Add expression-native `STOCH`.** The slow stochastic oscillator composes
  rolling high/low extrema with successive `%K` and `%D` moving averages and
  returns one Polars struct with `slowk` and `slowd` fields. It accepts custom
  high, low, and close expressions and requires no Rust kernel.

- **Add the expression-native Bollinger Bands family.** `BBANDS` returns one
  Polars struct with `upperband`, `middleband`, and `lowerband` fields; `BBP` and `BBW`
  compose only the scalar expressions they require. All three use population
  standard deviation and remain native Polars query expressions without a Rust
  kernel.

- **Move indicator implementations behind the public facade.** Modules now live
  under `bartons.indicators.lib`, keeping implementation module objects out of
  the `bartons.indicators` namespace. Public imports remain unchanged, and the
  facade now derives exports from implementation provenance rather than an
  uppercase-name convention.

- **Replace the Just workflow with Invoke.** `tasks.py` is now the single readable
  task graph. `uv run inv build` creates an sdist, builds its wheel with a
  persistent Cargo target, and tests that wheel in one phase; `publish` only
  guards and uploads the prepared artifacts. The obsolete `justfile`, separate
  preflight phase, duplicate sdist compilation, and artifact-stamp machinery are
  removed.

- **Add the fused `ALMA` kernel.** Gaussian weights are derived and normalized
  once from `period`, `offset`, and `sigma`; each completed ring-buffer window
  performs only the weighted dot product. Nulls reset the fixed window. Both
  expression and eager Series APIs are available.

- **Add a fused `DMI` struct kernel.** Directional movement, true range, the
  positive and negative directional indices, and ADX now run through one
  streaming filter. The eager kernel and Polars plugin transport one Struct
  series with `adx`, `pdi`, and `mdi` fields, and the public `DMI()` factory
  returns that native struct expression directly.

- **Standardize multi-output indicators on native Struct expressions.** `MACD()`
  now returns a `macd` Struct expression, matching DMI's expression and eager
  transport. Keeping the struct intact through `.over(...)` and using
  frame-level `unnest` gives callers explicit control over materialization and
  avoids relying on grouped projection CSE. `ExprBundle` remains available as
  an experiment but is no longer returned by shipped indicators.

- **Add fused `DEMA`, `TEMA`, `HMA`, and `ZLEMA` kernels.** These established moving
  averages are first-class expression and eager APIs rather than Python-only
  compositions. DEMA and TEMA cascade the existing EMA state machine; HMA
  cascades the existing WMA state machine using `period // 2` and
  `floor(sqrt(period))`; ZLEMA applies the conventional `(period - 1) // 2`
  de-lagging transform before EMA. This preserves the primitive kernels'
  warmup and null semantics while avoiding intermediate Polars series and
  plugin boundaries.

- **Add the fused `MFI` kernel.** Money Flow Index consumes a price source and
  volume through the unified driver's Float64 pair input, assigning source ×
  volume to rolling positive and negative flow sums. The expression factory
  defaults the source to `TYPPRICE()` while permitting arbitrary composition.
  Integer volume is cast to Float64. Missing source resets both direction and
  the window; missing volume resets the window while retaining the source for
  the next direction comparison.

- **Add the selector-based `QUADREG` kernel.** One centered-grid quadratic
  regression filter serves `QUADREG`, `QUADREG_CURVE`, `QUADREG_SLOPE`,
  `QUADREG_RVALUE`, and `QUADREG_RMSE`. The curve output is the quadratic
  coefficient; slope is the parabola's derivative at the current bar and, like
  forecast, accepts a forward offset. R-value is the partial correlation of the
  quadratic term after removing the linear term. The filter shares LINREG's
  ring-buffer rebasing policy and requires at least three points.

- **Add the selector-based `LINREG` kernel.** One rolling filter and one Polars
  plugin entry point serve `LINREG`, `LINREG_SLOPE`, `LINREG_RVALUE`, and
  `LINREG_RMSE`; the Python factories select a scalar output through stable
  string kwargs. The eager `kernels.linreg` surface exposes the same selector.
  A nonzero `offset` is accepted only for the forecast output, where it has a
  mathematical effect, and rejected for diagnostics rather than silently
  ignored. Nulls reset the regression window. The mintalib comparison benchmark
  covers forecast, slope, and r-value; the TA-Lib comparison covers forecast
  and slope, reflecting the regression statistics each baseline exposes.
  The eager kernel also exposes `rebase_interval=None`, which rebases after
  `max(1000, 2 * period)` bars have contributed to its incrementally maintained
  sums. Rebasing from the current ring buffer bounds floating-point drift. Zero
  disables rebasing; an interval at or below `period` rebases every full-window
  slide.

- **Separate performance work from operational automation.** Comparative Python
  benchmarks and focused Rust microbenchmarks now live in `benchmarks/`, while
  `scripts/` is reserved for commands that generate, install, or maintain
  project state. Cargo example targets, Just recipes, notebook links, and
  documentation now point at the new benchmark paths.

- **Add the Boolean `STREAK` kernel.** `STREAK(condition)` returns the
  non-negative length of the current true run; false and null reset it to zero.
  Direction stays explicit expression composition — for example,
  `STREAK(pl.col("close").diff() > 0)` — rather than being folded into a signed
  price-specific indicator. This is the first non-float pipeline through the
  unified driver: `Option<bool>` input to non-null `i64` output.

- **Add the `SAR` kernel.** Parabolic Stop and Reverse is a trend-flip state
  machine whose extreme point, acceleration factor and projected stop evolve
  from the preceding bar, so it has no natural rolling-polars expression. The
  implementation ports the shared mintalib/bearta algorithm and preserves its
  gap behavior: an invalid high/low bar emits null without resetting state.

- **Introduce the typed `run_filter` path for SAR.** `FilterInput` specializes
  on the exact row type accepted by `Filter::next`, binding it at compile time
  to an exact Polars source signature, casted storage and traversal. A separate
  `FilterOutput` binds output values to their Polars builder. SAR exercised the
  float-pair-to-float path first; the float-triple implementation now moves
  TRANGE and ATR onto the same driver, then the unary implementation moves all
  remaining filters and retires both arity-specific drivers. The design can
  later add `Option<bool>` input and `i64` output for a kernel such as STREAK
  without making the driver itself float-specific.

- **Add the `KER` and `KAMA` kernels.** KAMA is an exponential moving average
  whose smoothing constant is re-derived every bar from the Kaufman efficiency
  ratio — `alpha = (slow + KER * (fast - slow))**2` — so it tracks a clean trend
  closely and goes nearly flat in chop. The coefficient depends on the data, so
  there is no `ewm_mean` spelling to reach for; this is the first kernel added
  for that reason rather than for consistency or speed. `KER` ships as its own
  kernel and `KamaFilter` holds a `KerFilter`, mirroring how `CciFilter` holds a
  `MadFilter`. Unlike typical price, the ratio cannot be hoisted out and passed
  in as a precomputed series — it is stateful over time rather than elementwise —
  so it has to live inside the kernel, and exposing it there is what keeps
  `bartons.indicators.KER` from becoming a second definition of the formula.

- **`KER` is absolute (`0..=1`), not signed.** The numerator is the magnitude of
  the net move over the window, following TA-Lib and Kaufman's original. bearta
  divides the *signed* sum instead, giving `-1..=1`, which reads well for a
  standalone indicator but makes KAMA's smoothing constant asymmetric: a perfect
  downtrend would smooth at `(2*slow - fast)**2` where a perfect rally smooths at
  `fast**2`. One kernel serves both surfaces here, so it takes the definition
  KAMA needs.

- **`KER` deliberately does not match mintalib's `calc_ker`.** mintalib spans
  `period - 1` changes in the numerator against `period` in the denominator, so
  its ratio comes out systematically low and its KAMA correspondingly slow. A
  monotone ramp is the tell: it is perfectly efficient by definition, so the
  ratio must be exactly 1.0, and mintalib returns 0.833 at `period = 3`, drifting
  further down as the period grows. This is the one place bartons knowingly
  departs from mintalib's numbers rather than its conventions; the two are still
  paired in `benchmarks/benchmark-vs-mintalib.py`, which times them rather than
  comparing them.

- **`KER` resets on a null, diverging from both mintalib and bearta.** Both
  references carry the previous value across a gap and let the window span it.
  `KER` is windowed, so it takes the windowed family's convention (SMA, WMA,
  MAD) and drops the window *and* the previous value, which means no change is
  ever formed across a gap. That is also what makes the kernel agree row for row
  — including which rows are null — with the natural polars spelling,
  `diff().rolling_sum(period, min_samples=period)`; `test_ker_matches_native_polars`
  pins it. KAMA is the hybrid: the ratio's window resets while the running
  average carries across the gap like EMA and RMA, so smoothing resumes from the
  pre-gap value once the ratio has warmed up again.

- Defaults follow mintalib: `KER(period=10)` and `KAMA(period=10, fastn=2,
  slown=30)`. bearta defaults KAMA's period to 20.

- **Replace `scripts/check-release-version.py` with a `just release-guard`
  recipe.** The script was ~200 lines sized for a job that is three checks. Two
  are the load-bearing ones: a wheel built from a dirty tree, or from a commit
  that never reached the remote, corresponds to no public revision, and since
  PyPI never permits reusing a version or filename that can never be corrected —
  only superseded and yanked. The third is a PyPI lookup catching a forgotten
  bump, now two lines because `/pypi/{name}/{version}/json` returns 404 when
  nothing is published, so no JSON parsing is needed; testing for `== 404` also
  fails closed on a timeout or 5xx. Both `preflight` and `publish` call the
  recipe, so the checks still run twice — the tree can change between the two
  commands. Dropped with the script: the plain-`X.Y.Z` format assertion, which
  only fires if the version was hand-edited, and the post-upload SHA-256
  verification, which detected a **partial upload** — twine sends files
  sequentially, so a mid-upload failure can leave some files permanently
  occupying their filenames. `maturin upload` still reports a failed upload, so
  nothing is silently missed; the independent confirmation is the accepted cost.

- Delete the orphaned `scripts/bump-version.py`. Nothing referenced it: `just
  bump` runs `uv version --bump patch --no-sync`, which also refreshes
  `uv.lock`, where the script only rewrote `pyproject.toml`. Its docstring still
  claimed "Used by `just bump`", so it read as the live implementation of an
  operation it had stopped performing.

- Unpack `archive/github-workflow.zip` into `archive/github-workflow/`. The
  workflows were archived as a zip, which made them unreadable on GitHub,
  invisible to grep, and undiffable — so the stale `.devN` ritual in
  `release.yml`'s header went unnoticed until it was extracted by hand. As plain
  files they can be read and edited in place, and git history still holds the
  original zip, so the 2026-08-17 record survives. The `.yml` files are inert
  where they sit: GitHub only runs workflows under `.github/workflows/`.

- **Install the CI workflows.** `build.yml` and `release.yml` move from
  `archive/github-workflow/` into `.github/workflows/`, and the archive README
  becomes [docs/github-workflow.md](docs/github-workflow.md). They are
  **experimental and have never run** — `just publish` still owns releases. Both
  are **dispatch-only** — no push, pull-request, tag, schedule or `workflow_call`
  trigger — and `release.yml` defaults to a dry run that resolves and reports
  without publishing. Nothing has ever run: `workflow_dispatch` is resolved from
  the default branch, so these could not be exercised until they landed. Note
  that `just publish` and `release.yml` are now two upload paths for the same
  artifacts, and only one may own a given release.

- Rename `release.yml` to `publish.yml`. The workflow builds nothing — it resolves
  an earlier `build.yml` run and uploads its artifacts — so "release" overstated
  it, and `build.yml` / `publish.yml` names the two halves for what they each do.
  The rename costs nothing on the PyPI side: the trusted publisher registered on
  2026-08-17 naming `release.yml` has since been removed, so there is no stale
  entry to correct — only one to create, naming `publish.yml`, before any upload.
  The GitHub `pypi` environment is gone too (the API reports zero environments),
  so both halves of the server-side configuration are absent rather than
  mismatched.
  [docs/github-workflow.md](docs/github-workflow.md) now records it as such,
  alongside the pipeline's status (experimental, inactive, private repo, releases
  still local), what public would buy, and the next steps.

- **Stop publishing the cross-compiled Linux AMD64 wheel.** It was built here with
  zig and could not be imported on this ARM64 host, so 0.1.0 and 0.1.1 both shipped
  a binary nobody had ever run — the one caveat the release workflow carried as a
  standing IOU. Releases now ship the native ARM64 wheel and the sdist. Every
  machine in use here is ARM64, and this is reversible: the wheel returns when CI
  can smoke-test it on a native AMD64 runner, which is the first thing that
  pipeline would buy. The narrowing is real and deliberate — x86_64 users fall back
  to the sdist, which needs a Rust toolchain `pyproject` cannot declare plus a full
  polars build measured at ~12½ minutes. `just build` loses its `full` mode and the
  `maturin[zig]` cross-compile, `just preflight` gets shorter, and `just publish`
  now expects one wheel rather than two.

## 0.1.1

- **Every indicator now names its output after itself.** Polars names a plugin
  or arithmetic expression after its leftmost input column, so `EMA(20)`
  returned a column called `close` and `ATR(14)` one called `high`:
  `with_columns(EMA(20))` overwrote the very column it read, and
  `with_columns(EMA(20), SMA(20))` failed as a duplicate name. A `_named` step
  in the prelude decorators aliases each result with the factory's own
  lowercased name, and a new `@wrap_indicator` covers the multi-input factories
  (TRANGE, ATR, the price transforms) that were previously undecorated. An
  outer `.alias` still wins, and `MACD`'s `ExprBundle` is left alone since its
  members already name themselves. This is at the expression layer rather than
  in Rust: the kernels already name their output — `kernels.ema` returns a
  series called `ema` — but the expression engine discards it, so naming there
  would not reach the affected surface and would miss the five kernel-free
  factories. The name is the bare factory name, so `EMA(20)` and `EMA(50)`
  still collide by design and still want an explicit alias.

- **Add the TA-Lib price transforms: `AVGPRICE`, `MEDPRICE`, `WCLPRICE`.**
  Native expression factories with no kernel behind them, joining `TYPPRICE` in
  a new `indicators/price.py` — grouped in one module because the
  one-file-per-indicator rule tracks kernels and these have none. They stay
  re-exported flat from `bartons.indicators`, so there is still one import path.
  Named after TA-Lib rather than bearta and mintalib, which call `(high + low)
  / 2` *midprice*: TA-Lib reserves `MIDPRICE` for the rolling midpoint of the
  highest high and lowest low over a period, a different indicator, and bartons
  is benchmarked against both libraries. All four agree with TA-Lib to within
  one ULP; `MEDPRICE` and `WCLPRICE` are bit-identical.

- **Add `TYPPRICE()` and make `CCI` single-source.** `(high + low + close) / 3`
  had two implementations — a polars expression on the lazy path and
  `HlcCciFilter` inside the kernel for the eager one — kept in step by a comment
  asserting they agreed bit for bit. It now has one, the new `TYPPRICE()`
  expression factory, which `CCI` supplies as its default `src`. `kernels.cci`
  takes a single series like the kernel it wraps, so the eager caller writes
  `kernels.cci((high + low + close) / 3, period=20)`; `HlcCciFilter` and CCI's
  use of `run_ternary` are gone. `CCI(period, *, src=...)` replaces the
  `high`/`low`/`close` keywords — `CCI(20)` is unchanged, other column names go
  through `CCI(20, src=TYPPRICE(high=..., ...))` — and CCI joins the `.pipe`
  family. No kernel backs `TYPPRICE`: the reduction is elementwise and
  stateless, so polars computes it vectorized on both surfaces, and a kernel
  would only re-add the plugin boundary the single-input design avoids.
  `docs/architecture.md` records the rule and where it stops (ATR's true range
  reaches back a bar, so it stays ternary).

- Reimplement CCI as a Rust kernel instead of a native expression composition.
  The SMA and MAD terms previously kept two separate windows over the same data
  and computed the same window mean twice; `MadFilter::next_stats` now yields
  `(mean, mad)` from one window, so the SMA term is free. The kernel takes
  typical price as its single input rather than the three raw columns — that
  reduction is elementwise and stateless, unlike ATR's true range, so leaving it
  to Polars keeps one column crossing the plugin boundary instead of three,
  which is what `.over()` partitions per group. About 2.2x faster on a single
  symbol and 1.7x under `.over()` at period 20; the gain narrows as the period
  grows, since MAD's per-row window rescan comes to dominate. Values are
  bit-identical to the composition it replaces.
- Make bundled `sample_prices` frames contiguous at load time. The mintalib
  chunk-sensitivity benchmark no longer depends on the CSV reader's accidental
  physical layout: it uses `random_prices` with explicit row, ticker and chunk
  counts for both scenarios.

## 0.1.0

- Make PyPI publishing a fail-closed, exact-artifact pipeline split at its
  irreversible boundary. `just preflight` requires a clean synchronized branch
  and unpublished stable version, builds once, validates that exact wheel through
  the full matrix and smoke test, and writes a local success stamp only at the
  end. `just publish` never compiles: it accepts only the stamped artifact set,
  verifies the uploaded PyPI filenames and SHA-256 hashes, then bumps both project
  metadata and the lockfile for the next release.
- Rename the compiled and eager materialized API from `bartons.plugin` to
  `bartons.kernels`. The direct public namespace now describes what it contains,
  matches the Rust source layout, and avoids exposing build-system terminology.
- Add MACD as native composition over the EMA kernel. Multi-output native
  indicators use Bartons' local `ExprBundle`: a tuple of independently named
  expressions that Polars expands into ordinary columns and that can be scoped
  together with `.over(...)`. MACD returns `macd`, `macdsignal` and `macdhist`.
- Add a Rust rolling mean absolute deviation (`MAD`) kernel and compose Commodity
  Channel Index (`CCI`) natively from typical price, SMA and MAD. MAD follows the
  other windowed kernels: null input resets its window and warmup emits nulls.
- Add a deterministic Rust `random_prices` generator for tests and benchmarks.
  It produces OHLCV `DataFrame`s with an exact requested chunk count, optional
  ticker groups and leading nulls. The same implementation is public through
  `bartons.samples.random_prices` and the crate's `rlib` target, allowing Python
  plugin-boundary benchmarks and native Rust micro-benchmarks to share a fixture.
  Physical layout is a separate `with_n_chunks(frame, n_chunks)` utility, so the
  same controlled fragmentation can be applied to generated or real datasets.
- Give the `evcxr/` notebooks versionless `:dep` cells and move the kernel's build
  settings to the dotfiles repo. A bare `:dep polars` resolves to whatever is newest
  rather than tracking `bartons/Cargo.toml`, which is the intended behaviour: these
  notebooks compare patterns and methods, where the crate version is rarely the
  variable, and pinning them is exactly what rotted last time — polars 0.54.4 in the
  notebooks against 0.55.1 in the crate, with nothing to say so. Pin a single line
  when an experiment needs one. Every notebook that needs crates declares the same
  block (`polars`, `itertools`, `serde`), because evcxr's build cache is keyed on the
  *complete* dependency set rather than per crate: identical sets share one build,
  while a set differing by a single crate pays its own ~80s. `:cache 2048` and
  `:opt 3` now live in `~/.config/evcxr/init.evcxr`, stowed from the dotfiles repo as
  machine-level build settings; without them notebooks still work, at ~80s per
  session instead of ~2s.
- Drop `evcxr/evcxr.toml`, `scripts/check-evcxr-pins.py` and the `just evcxr-check`
  recipe, which briefly centralised the notebook pins. The toml turned out to shadow
  `init.evcxr` completely — settings and `:dep` lines alike — and its schema has no
  cache key, so adopting it disabled `:cache` and moved the dependency build from
  first-cell-execution to *kernel startup*, where ~80s exceeded VS Code's 60s
  `jupyter.jupyterLaunchTimeout` and failed as "Failed to start the Kernel" with
  cargo output and no mention of configuration. Neither workaround recovers it:
  `sccache = "sccache"` is genuinely engaged but buys ~8%, and `EVCXR_CACHE_ENABLED`
  is an internal marker with no effect when set. With the pins gone there is nothing
  left for the checker to compare, and the raised launch timeout is no longer needed.
- Record a ternary-driver micro-benchmark in
  [docs/izip-vs-index-benchmark.md](docs/izip-vs-index-benchmark.md), from
  [benchmarks/izip-vs-index.rs](benchmarks/izip-vs-index.rs). `izip!` beats any index loop
  and the margin grows with fragmentation — 8.4× at 64 chunks — so nothing argues
  for indexing. The finding is what beats `izip!`: both `ChunkedArray::get` and
  `get_unchecked` re-derive the array on every element (index `chunks[0]`, deref the
  `Arc<dyn Array>`, downcast), which cannot be hoisted through `&self`. Hoisting it
  once per chunk instead is 2.8× faster than today's `izip!` on single-chunk input
  and 2.0× on fragmented input, with no allocation at any chunking — rechunking,
  which would have copied `3 × n × 8` bytes, turns out to be an expensive way to
  reach the same hoist and is slower than walking chunks. Each contributing term is
  isolated by its own variant rather than argued: `izip!`'s machinery is free
  (advancing the same iterators by hand costs the same), the number of cursors is
  free (one index per array matches one shared index), and what remains is
  per-element chunk-boundary handling. Expressing that cursor as an `Iterator`
  behind a trait made it *faster* than the equivalent macro (347 against 413 at 64
  chunks), since carrying a remaining count supplies an exact `size_hint` the macro
  could not.
  Implement the copy-free cursor as a `FastIter` extension trait used by both
  drivers. A separate unary comparison found the native single-chunk Arrow
  iterator and `FastIter` tied at 286.6µs, so no unary dispatcher is added. The
  separately measured ternary direct-index single-chunk dispatcher remains
  deferred. The script takes `--out <path>` to
  save its report, and its header states it must be
  cargo-built — a notebook of the same source reverses the result, which is a fact
  about evcxr's build profile rather than about the driver, since `maturin
  --release` is what compiles the shipped extension.
- Correct the recorded kernel micro-benchmark, and move it out of the notebook that
  produced it. `evcxr/builder-vs-collect.ipynb` had compared `filter` (using
  `append_option`) against `builder` (using a manual `match`) — two variables down
  one diagonal, so the gap was attributable to neither. Re-run as a 2x2 on the
  current pin, the streaming-filter abstraction is exactly free (355µs, same as a
  hand-inlined loop) and the whole 1.6× it had been charged belongs to
  `append_option` — which `run_unary`/`run_ternary` already avoid, deliberately, and
  should keep avoiding. The corrected experiment is
  [benchmarks/builder-vs-collect.rs](benchmarks/builder-vs-collect.rs) with results and
  provenance in
  [docs/builder-vs-collect-benchmark.md](docs/builder-vs-collect-benchmark.md); the
  notebook keeps a pointer to both and no longer carries stored numbers. It cannot
  be a cargo example: `polars-utils` pulls `numpy` -> `pyo3` and the crate enables
  pyo3's `extension-module`, so no example, test or bin target in that package can
  link. `evcxr/sma-filter.ipynb` is flagged in place as known-incorrect — it
  computes an EMA under an SMA name, with none of the shipped `SmaFilter`'s warmup
  or gap-reset semantics.
- Add the local build/publish path the archived CI never left behind, and rename
  the recipes to mirror maturin's own verbs. `just develop` (was `just build`)
  installs into the `.venv`; `just build` now runs `maturin build`, producing the
  wheel + sdist in `dist/` and installing nothing — so `just <verb>` and
  `maturin <verb>` finally mean the same thing. `just develop-debug` was
  `just build-debug`; `bench` and `stubs` depend on `develop`, the nine references
  across docs and benchmark scripts were updated with them. `build` wipes `dist/`
  first — a stale wheel from an earlier version is indistinguishable from a fresh
  one to any `dist/*` glob, and one was in fact sitting there. `just publish`
  uploads via `maturin upload`. `just dump` is fixed to inspect `dist/*.tar.gz`; it had pointed
  at `target/wheels/`, a path no recipe ever produced. Publishing is guarded by
  [scripts/check-release-version.py](scripts/check-release-version.py), which
  refuses a version already on PyPI — the "forgot to bump" mistake, and one PyPI
  cannot undo, since a version or filename can never be reused even after
  deletion. It fails loudly rather than using `--skip-existing`, which would
  quietly do nothing and let you believe you had published. That is the check
  worth keeping from the deleted tag-guard job.
- Build a full GitHub Actions release pipeline, then archive it unused as
  `archive/github-workflow.zip`. It published five `cp311-abi3`
  wheels plus the sdist to PyPI on a `v*` tag, over OIDC trusted publishing with
  no stored token. It was disproportionate: the repo is private and early, and its
  only consumers are two machines — an OrbStack VM (Ubuntu 25.04, glibc 2.41,
  Python 3.11) and `boston`, an EC2 Graviton box (Ubuntu 24.04, glibc 2.39, Python
  3.12). Both are aarch64 Linux, so one locally-built wheel serves both and four of
  the five CI targets existed for users who do not exist. Building sdists and
  aarch64 wheels from the dev machine is the proportionate answer at this stage.
  The zip carries the workflows, the release handoff, and a README recording what
  the exercise established — `abi3` collapsing the Python axis (one wheel spans the
  fleet's 3.11 and 3.12), the ~195 billed minutes a full private-repo matrix costs
  at the ×10 macOS multiplier, why wheels must be built in one run rather than
  accumulated across runs, and the PyPI facts that outlive CI (immutable
  `Requires-Dist`, filenames never reusable, yank-not-delete).
- Have the in-repo version name the *next* release, plain — no `.devN` suffix,
  matching the convention in mintalib. The tree is therefore publishable at any
  moment: build as often as you like, and on release `just publish` uploads what
  the version already says. Afterwards commit and push at that version, then
  `just bump` (patch increment via
  `scripts/bump-version.py`, since removed) and push again so the repo
  names the next one. A `.devN` scheme was tried first and dropped: it bought
  pip's `--pre` protection and an unambiguous "this tree is ahead of its release"
  marker, at the cost of an edit before every publishable build — not worth it
  when the only consumers are two machines the author controls.
- Make [pyproject.toml](pyproject.toml) the one authoritative version and freeze
  the crate's at `0.0.0`. Both files previously declared `0.1.0` with nothing
  keeping them equal, so the two could drift silently — maturin stamps the wheel
  from pyproject and ignores the crate. Cargo requires the field, so it cannot
  simply be deleted; pinning it at `0.0.0` with a comment marks it dead rather
  than leaving a plausible-looking number that no longer tracks releases. The
  alternative — `dynamic = ["version"]` in pyproject, sourcing from the crate —
  works (verified: a crate bump to `0.1.1` produced `bartons-0.1.1-*.whl`) but
  puts the release number in a nested Rust file that is otherwise irrelevant
  here: the crate is a cdylib built only into the wheel, unpublished on
  crates.io, with no Rust dependents. Revisit if it is ever published on its own.
- Upgrade the binding pins. Turning the single dial to `pyo3-polars 0.28` sets the rest: polars-rs and
  polars-arrow `0.55.1` (resolving `0.55.2`) and pyo3 `0.29` (resolving `0.29.2`).
  The polars-rs minor jump needed **no kernel changes** — no API we use moved.
  The FFI handshake is unchanged at `(0, 1)`, verified by reading the constants
  out of `polars-ffi 0.55.2`, so the ABI story is intact; the version table is
  extended accordingly.
- Widen the polars-py range to `>=1.28,<1.44`, and add `just raise-ceiling` to
  keep it there. The ceiling had gone three releases stale: polars-py `1.43.0`
  through `1.43.2` all resolve to polars-rs `0.54.4`, the same engine crate as
  `1.42.x`, so `<1.43` was excluding releases on an engine the matrix already
  covered. `1.43.2` joins `COMPAT_VERSIONS`, and `rt64` moves to
  `polars[rt64]>=1.43,<1.44`. The new recipe
  ([scripts/raise-ceiling.py](scripts/raise-ceiling.py)) looks up the newest
  polars-py, adds it to the matrix, runs `compat` against it, moves the ceiling
  **only if that passes** — rolling back on failure so the declared range never
  claims more than was tested — then upgrades the dev env to match
  (`uv lock --upgrade-package polars`, `uv sync`) and re-runs the suite, so the
  newly-admitted version is what daily work actually exercises rather than being
  tested once in a throwaway venv. The dev lockfile therefore moves to 1.43.2. Widening to `<2.0` on semver faith was considered
  and rejected: `PySeries._export`, the private API the eager path rides on, first
  appeared at polars-py `1.28` — a minor — which is why the floor is not `1.0`.
  All 11 nox sessions pass, spanning 1.28.0–1.43.2 plus both runtime engines.
- Raise the stable-ABI floor from `abi3-py38` to `abi3-py311`; the wheel tag goes
  from `cp38-abi3` to `cp311-abi3`. `requires-python` is already `>=3.11` and the
  nox matrix only runs 3.11, so the old floor advertised three Python minors that
  were neither installable nor tested. Nothing measurable is given up: `abi3`
  cannot reach the compute path, since `#[polars_expr]` compiles to a
  `#[no_mangle] extern "C"` symbol polars calls directly over the Arrow C
  interface — never through pyo3 — and the eager `plugin.<name>` path crosses pyo3
  once per call to marshal a Series, not once per element. The gain is headroom:
  pyo3 gates ~98 call sites on `Py_3_10` and ~33 on `Py_3_11`, now available if
  wanted. Verified across `rt32`, `rt64`, and `compat` at both ends of the
  supported polars range (1.28.0 and 1.42.0), each installing a freshly built
  wheel.
- Rename the Rust source module `bartons/src/indicators/` to `bartons/src/kernels/`,
  and give each file's three symbols names that say what they are: the **kernel**
  takes the plain name (`ema`), and the two bindings are suffixed by the boundary
  they serve (`ema_expr` for the polars FFI, `ema_py` for the eager one, which
  keeps its Python name via `#[pyo3(name = "ema")]`). The `calc_` prefix is gone —
  it existed to dodge Python's flat namespace, and Rust modules make it redundant.
  The kernel is the vector calculation, series in and series out; the `Filter`
  loop is one way to implement it, not part of the definition.
  **No Python-visible change**: `bartons.kernels.<name>`, `__all__`, signatures and
  docstrings are all byte-identical, and the generated stub regenerates unchanged.
  The rename records a layer distinction that had been left implicit — Rust holds
  materialized primitives, Python composes indicators on top of them. The two sets
  coincide today only by accident; a composite like BBANDS (`SMA ± k·std`) belongs
  in Python with no Rust counterpart, and the directory names now make that
  divergence read as intended rather than as drift.
- Ship type stubs for the compiled extension: `python/bartons/kernels.pyi`, plus
  the PEP 561 `python/bartons/py.typed` marker without which a *consumer's* type
  checker ignores them. `uv run ty check` now passes clean, down from 1394
  diagnostics earlier in this cycle. The stub is generated by `just stubs`
  (`scripts/generate-kernel-stubs.py`), which introspects the
  built module — pyo3 exposes parameter names, keyword-only markers, defaults and
  docstrings, but no types, so those come from a five-entry `PARAM_TYPES` map in
  the script; an unmapped parameter name fails loudly rather than emitting `Any`.
  The Rust-side generator `pyo3-stub-gen` was tried first and does not work here:
  every pyfunction signature is in terms of pyo3-polars' `PySeries`, which does
  not implement its `PyStubType`, and the orphan rule prevents supplying that impl.
- **Behavior change — the eager `bartons.kernels.<name>` functions now raise
  `ValueError`, not `RuntimeError`.** An invalid `period`, or mismatched input
  lengths on TRANGE/ATR, previously surfaced as a bare `RuntimeError` because
  each pyfunction ended in a hand-rolled
  `match … PyRuntimeError::new_err(e.to_string())` that discarded the
  `PolarsError` variant. Those seven blocks are replaced by
  `.map_err(PyPolarsErr::from)?` — `pyo3-polars` already ships the mapping from
  14 `PolarsError` variants onto Python exceptions, so the classification now
  survives to Python. To make it land on a *useful* class, the errors carry
  `InvalidOperation` (→ builtin `ValueError`) rather than `ComputeError` or
  `ShapeMismatch`, whose pyo3-polars classes live in a module Python cannot
  import and are catchable only as bare `Exception`. The full chain went from
  `String → ComputeError → RuntimeError` to `String → InvalidOperation →
  ValueError`. The expression path is unchanged: polars' plugin FFI re-wraps
  whatever a `#[polars_expr]` returns, so `EMA(0)` in a `select` still raises
  `polars.exceptions.ComputeError`. The seven `test_invalid_period_pyfunction`
  tests asserted only `pytest.raises(Exception)` and so would not have noticed
  either behavior; they now assert `ValueError` and match the message.
- **Removed — the `.bt` expression namespace.** `pl.col("close").bt.ema(20)` no
  longer exists; use `EMA(20, src=pl.col("close"))` or
  `pl.col("close").pipe(EMA, 20)`, which are equivalent and, unlike `.bt`,
  statically checkable. `@pl.api.register_expr_namespace` attaches the accessor
  to `pl.Expr` at runtime, and since polars ships inline types with no `.pyi`
  files — and Python stubs have no declaration-merging — there is no way to
  declare `bt` on `pl.Expr` short of shadowing polars' own stubs. It was the only
  surface with no path to type checking, and it duplicated the factories it
  delegated to. `bartons/__init__.py` no longer imports anything for its side
  effect. The implementation and the full reasoning are preserved in
  [docs/namespace-legacy.md](docs/namespace-legacy.md).
- Make the wrapped single-source factories statically checkable. `wrap_src_indicator`
  is now typed `Callable[P, R] -> SrcIndicator[P, R]`, where `SrcIndicator` is a
  `Protocol` declaring both call forms as `__call__` overloads (canonical first,
  expression-first second). Previously the decorator carried no annotations, so
  a checker saw `EMA` and friends as opaque and checked nothing about them —
  `x: int = EMA(20)` passed. Ported from `bearta.prelude`.
- Move the shared factory machinery out of `bartons/indicators/__init__.py` into
  a new `bartons.prelude` module, and rename `wrap_src_expression` to
  `wrap_src_indicator` (matching `bearta.prelude`, which holds the same pieces
  under the same name). `PLUGIN_PATH` moves with it — it had to, because the two
  together were a circular import: each factory did `from . import PLUGIN_PATH,
  …` while `__init__.py` imported the factories at the bottom, so the package
  half-initialized itself and the re-export block could not be moved to the top
  without an `ImportError`. Factories now import `from ..prelude import …`,
  `indicators/__init__.py` is re-exports only, and the cycle is gone.
- **Bug fix — the three-series indicators (TRANGE, ATR) silently truncated on
  mismatched input lengths.** `run_ternary` sized its output builder from the
  first input while `izip!` stopped at the shortest, so unequal inputs produced a
  short result with no error. It now validates up front via a new variadic
  `check_len!(a, b, c)?` macro (a thin wrapper over `utils::check_lengths`),
  raising an error naming the series that disagrees and the two lengths.
  A length-1 input is treated as a mismatch, not a scalar to broadcast — plugin
  inputs arrive un-broadcast, so `pl.lit(100.0)` as an input is now a loud error
  instead of a silent one-row result.
- **API change — `bartons.expressions` is now `bartons.indicators`.** Import
  factories as `from bartons.indicators import EMA`. The `expressions` name was
  inherited from mintalib, where it distinguished the polars surface from the
  pandas `indicators` one; bartons is polars-only, so the contrast it drew does
  not exist here and every public object is an expression regardless. The
  sub-package now matches `bartons/src/indicators/` on the Rust side, giving the
  same seven names on both sides of the FFI boundary. "Expression factory"
  remains the term for what the module contains — only the module name changed.
  The `.bt` accessor is unaffected.
- Generalize the `Filter` trait over its input shape with an associated
  `type Input`, so the multi-input indicators join the same contract as the
  single-series ones. `TrangeFilter` and `AtrFilter` had an inherent `next` while
  `run_ternary` took a closure, leaving the two drivers with nothing in common
  and every ternary call site repeating a `|h, l, c| filter.next(h, l, c)`
  adapter. They now `impl Filter` with `type Input = Hlc` — a new
  `(Option<f64>, Option<f64>, Option<f64>)` alias, spelled `utils::Triple` on the
  driver side (which is arity-generic and assumes nothing about what the three
  series mean) and re-aliased as `indicators::Hlc` on the kernel side (which
  does). `run_ternary` is `run_ternary<F: Filter<Input = Triple>>`, and both call
  sites collapse to
  `run_ternary(h, l, c, name, filter)`. `AtrFilter::next` now passes the bar
  straight through to its inner `TrangeFilter` instead of unpacking and
  respreading it. Internal only — no behavior or API change.
- **Behavior change — nulls now skip instead of reset in the recursive
  indicators.** EMA, RMA (and therefore RSI and ATR, which smooth with the shared
  `RmaFilter`) previously treated a `None` input as a hard break: clear state,
  emit null, re-warm afterward. They now *skip* it — emit null for that row but
  carry the running average across the gap — matching polars/pandas `ewm` and
  mintalib. The windowed indicators (SMA, WMA) are unchanged; their window-reset
  already matches mintalib. RSI additionally keeps `prev` across the gap so the
  next bar measures the real change across it (BRIDGE); this **diverges from
  mintalib**, which re-seeds `prev` — chosen for consistency with the MA skip
  semantics (a null is ignored uniformly across all indicators) rather than
  copying mintalib's internal inconsistency. Filed upstream against mintalib to
  align its RSI. Verified kernel == oracle across all cases (166 tests pass), and
  EMA/RMA/ATR values == mintalib.
- Centralize the per-indicator Python reference oracles into one importable
  `tests/refimpl.py` (`ref_ema`/`ref_sma`/`ref_rma`/`ref_wma`/`ref_rsi`/
  `ref_trange`/`ref_atr`); the test files now `from refimpl import ref_<name>`
  instead of each defining its own inline. Kills the cross-file duplication
  (`ref_rma`/`ref_trange` had been copy-pasted into `test_atr.py`, and Wilder
  smoothing was inlined a third time inside `test_rsi.py`): `ref_atr` now composes
  `ref_rma ∘ ref_trange` and `ref_rsi` reuses `ref_rma`. Behaviour is unchanged
  (166 tests pass); the oracles stay dep-free hand-rolled Python so the lean
  `compat`/`rt` matrix keeps installing only the wheel + pytest + polars.
- Raise the supported `polars` floor from `>=1.0` to `>=1.28`, in both
  `pyproject.toml` and the nox `compat` matrix. The eager `bartons.kernels.<name>`
  pyfunctions marshal a Series into Rust via pyo3-polars 0.27's private
  `PySeries._export`, which polars only exposes from 1.28; on older engines they
  raise `AttributeError: 'PySeries' object has no attribute '_export'`. The
  expression path (`EMA()`, `.bt.ema()`) would work lower, but the package now
  floors at 1.28 so its whole public API is usable. `COMPAT_VERSIONS` drops the
  seven sub-1.28 entries and swaps `1.22.0` → `1.28.0` (both engine crate 0.46.0),
  keeping one representative per distinct engine crate across `[1.28, 1.43)`.
- Remove the `@requires_pyfunction` marker (and its decorators across the eager
  tests). With the `compat` floor now at 1.28, `PySeries._export` is always
  present, so the marker's `skipif` was permanently false. The
  `assert_series_equal` shim in `tests/helpers.py` stays — its `rel_tol`/`abs_tol`
  gate only clears at polars 1.32.3, so the 1.28–1.32.2 compat sessions still need
  it.
- Replace the `tests/conftest.py` source-grepping skip hook with an explicit
  `@requires_pyfunction` marker (defined in `tests/helpers.py`) on the eager
  direct-call tests. The marker skips when `PySeries._export` is absent — the
  eager `plugin.<name>` surface needs it (polars ≥ 1.28 with pyo3-polars 0.27),
  while the expression / `.bt` path is unaffected and runs across the full
  supported range. `conftest.py` removed; verified on the polars 1.22 compat
  session (eager tests skip, everything else passes).
- Make the `.bt` namespace methods delegate to the expression factories
  (`xp.EMA(period, src=self._expr)`, …) instead of re-implementing the
  `register_plugin_function` call. The FFI wiring now lives in one place per
  indicator (the factory); `namespace.py` no longer imports `register_plugin_function`
  or `PLUGIN_PATH`.
- Add `///` doc comments to every eager pyfunction (EMA, SMA, RMA, WMA, RSI,
  TRANGE, ATR), so PyO3 surfaces them as `__doc__` and `help(bartons.kernels.<name>)`
  shows the signature plus an Args/Returns description.
- Move the Rust indicator kernels into a `bartons/src/indicators/` source module
  (`lib.rs` now `mod indicators;`); cross-kernel refs use `super::`. No API
  change — the eager functions stay exposed flat at `bartons.kernels.<name>`.
- Make the single-source factories (EMA, SMA, RMA, WMA, RSI) accept their source
  column as the leading positional argument via a `wrap_src_expression`
  decorator (adapted from bearta's `wrap_expression`), so they compose with `Expr.pipe`:
  `pl.col("close").pipe(EMA, 5).pipe(RSI, 14)`. `EMA(5)` and `EMA(5, src=...)`
  keep working unchanged.
- Add ATR (Average True Range). `AtrFilter` composes a `TrangeFilter` feeding an
  `RmaFilter` (Wilder's RMA of True Range); a multi-input indicator over high /
  low / close. Exposed as `ATR()` and `kernels.atr` (default period 14). Also
  widen the conftest pyfunction-skip pattern to cover `rsi` and `atr`.
- Add a `bartons.samples` subpackage with bundled OHLCV sample prices (daily /
  hourly / minute AAPL CSVs). `sample_prices(freq, max_bars=...)` returns a
  polars DataFrame; `sample_dataset(n_tickers, ...)` stacks them into a synthetic
  multi-ticker frame for `.over()` benchmarks. `scripts/update-samples.py`
  refreshes the CSVs via yfinance (optional `samples` dependency group). Ported
  from python-dev's `barcalc`.
- Add RSI (Wilder's Relative Strength Index). `RsiFilter` composes two
  `RmaFilter`s for the smoothed average gain/loss and emits
  `100 * avg_gain / (avg_gain + avg_loss)`; a flat run yields `0`, matching
  TA-Lib. Exposed as `RSI()`, `.bt.rsi()`, and `kernels.rsi` (default period 14).
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
