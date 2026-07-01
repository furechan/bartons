# Considered alternatives

Designs that were explored for the plugin surface and deliberately **not** taken,
recorded so they aren't re-litigated. None of these are bugs or TODOs — the
current design is the intended one; this is the "why not" context.

## Native `plugin.indicators` submodule — rejected

**Idea:** instead of exposing the eager pyfunctions flat as `bartons.plugin.<name>`,
group them under a native submodule so they read as `bartons.plugin.indicators.<name>`
(mirroring the Rust `indicators/` source dir).

**Built and reverted.** It was implemented fully: `lib.rs` converted to the
declarative `#[pymodule] mod plugin` form, with a `#[pymodule] pub mod indicators`
block in `indicators/mod.rs` re-exporting the kernels via `#[pymodule_export] use`.

**Why rejected:**

- PyO3 0.28 does **not** auto-register nested declarative submodules in
  `sys.modules`, and an extension module (`.so`) is not a package (no `__path__`).
  So `import bartons.plugin.indicators` / `from bartons.plugin.indicators import ema`
  raise `ModuleNotFoundError` out of the box — only *attribute* access
  (`bartons.plugin.indicators.ema`) works.
- Making the `import` form work requires a manual `#[pymodule_init]` that sets the
  submodule's `__name__` and inserts it into `sys.modules` under the fully qualified
  name. That's non-obvious machinery living in Rust, in service of an import form
  that's rarely used — `bartons.plugin` is private plumbing reached via
  `import bartons.plugin as p; p.…`, and codegen/introspection uses attribute access
  too. The hack wasn't earning its keep.

The reorg of the *source* into `bartons/src/indicators/` (Step 1) was kept; only
the *Python-facing submodule* (Step 2) was reverted. The revert was a `git reset`,
so it leaves no trace in history — hence this note.

## DRY the `lib.rs` registration list — deferred

`lib.rs` currently lists seven `m.add_function(wrap_pyfunction!(indicators::<name>::<name>, m)?)?;`
lines. Two ways to remove the repetition were considered:

- **A local `macro_rules!`** driving both the `pub mod <name>;` declarations and the
  registration from a single `indicators!(ema, sma, …)` name list — one source of
  truth, no dependency. Name appears once.
- **Link-time self-registration** (`inventory` / `linkme`): each kernel file
  registers itself and `lib.rs` iterates. Gives per-file locality but adds a
  dependency, and can't remove the `pub mod` roster (Rust has no file
  auto-discovery), so the name ends up in two places.

**Deferred:** at seven indicators the explicit list is readable and greppable; the
macro is a clean future option if the count grows.

## Python eager-function wrapper / metadata layer — deferred

The eager `#[pyfunction]`s are `builtin_function_or_method` objects: they carry a
signature (`inspect.signature` works, from `#[pyo3(signature = …)]`) and a docstring
(from `///` comments), but **no type annotations, no output dtype, and no `__dict__`**
— so you cannot attach arbitrary metadata (`fn.output_dtype = …`) to them.

If a richly-introspectable / typed surface is ever wanted (e.g. codegen of stubs or
factories), the place for it is a Python module (`bartons.functions` or similar) that
wraps the raw pyfunctions with `functools.wraps` — a Python function *does* hold
annotations and custom attributes, and being part of the real `bartons` package it
imports cleanly with no native tricks. Not built yet; noted as the natural home if
the need arises.
