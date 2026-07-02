"""Test the (single, default) compiled plugin against both polars engines.

bartons' indicators exchange only numeric (Float64) data, so the same default
build runs on polars-runtime-32 (IdxSize=u32) and polars-runtime-64 (bigidx,
IdxSize=u64) — the FFI boundary carries no IdxSize. These sessions prove that:
one `maturin build --release` wheel runs in both, differing only in which engine
is installed and forced via POLARS_FORCE_PKG. See docs/polars-runtime-libraries.md.

The extension is identical for every engine and every polars version under test
(same crate 0.54.4; the FFI boundary carries no IdxSize), so we compile ONE abi3
wheel and install that same artifact into every session. uv caches and unpacks
the wheel near-instantly, so the 15 compat + rt32 + rt64 sessions share a single
cargo build instead of recompiling (`maturin develop`) in 17 isolated venvs. Only
the installed *polars* wheel differs between sessions.
"""

import glob
import os
import shutil

import nox

nox.options.default_venv_backend = "uv"

PY = "3.11"

# Path to the prebuilt extension wheel, populated on first use by `_wheel()` and
# reused by every later session within a single `nox` invocation.
_WHEEL = None


def _cargo_bin() -> str:
    """Locate a cargo/rustc bin dir. cargo is not always on PATH here — the Rust
    toolchain may live in the puccinialin cache that maturin's build backend
    bootstraps. Return a dir to prepend to PATH (empty string if cargo is found)."""
    if shutil.which("cargo"):
        return ""
    candidates = [os.path.expanduser("~/.cargo/bin")]
    candidates += sorted(
        glob.glob(os.path.expanduser("~/.cache/puccinialin/rustup/toolchains/stable-*/bin"))
    )
    for d in candidates:
        if os.path.exists(os.path.join(d, "cargo")):
            return d
    raise OSError("cargo not found on PATH or in ~/.cargo/bin or the puccinialin cache")


def _wheel(session: nox.Session) -> str:
    """Build the bartons abi3 wheel once per `nox` run and return its path (cached).

    The first session to need it compiles via `maturin build --release` against the
    shared `bartons/target` cargo cache; every later session reuses the same wheel,
    which uv installs from its own cache without recompiling.
    """
    global _WHEEL
    if _WHEEL is None:
        for old in glob.glob("dist/bartons-*.whl"):
            os.remove(old)
        session.install("maturin")
        cargo_bin = _cargo_bin()
        env = {"PATH": cargo_bin + os.pathsep + os.environ["PATH"]} if cargo_bin else None
        session.run("maturin", "build", "--release", "--out", "dist", env=env)
        (_WHEEL,) = glob.glob("dist/bartons-*.whl")  # exactly one after the clean above
    return _WHEEL


# One representative polars per *distinct engine crate version* across [1.28, 1.43) —
# every distinct FFI/Arrow boundary in the supported range (patch releases within a
# crate group share the engine, so testing one per group is complete). The plugin is
# built once against crate 0.54.4 (→ polars 1.42) and run against all of them.
# Floor is 1.28: the eager plugin.<name> pyfunctions need PySeries._export, which
# polars only exposes from 1.28 (see docs/test-compat-helpers.md). 1.28.0 also
# represents engine crate 0.46.0, whose group spans polars 1.22–1.29.
# version -> crate:  1.28.0→0.46.0  1.30.0→0.48.1  1.32.0→0.49.1  1.32.1→0.50.0
# 1.34.0→0.51.0  1.38.1→0.52.0  1.39.0→0.53.0  1.42.0→0.54.4
# (1.36.0 is also crate 0.52.0 but its polars-runtime-32 wheel was yanked, so use 1.38.1.)
COMPAT_VERSIONS = [
    "1.28.0", "1.30.0", "1.32.0", "1.32.1", "1.34.0", "1.38.1", "1.39.0", "1.42.0",
]


@nox.session(python=PY)
@nox.parametrize("plv", COMPAT_VERSIONS)
def compat(session: nox.Session, plv: str) -> None:
    """Run the suite against one specific polars version (same prebuilt plugin wheel)."""
    session.install(_wheel(session), "pytest")  # prebuilt extension; pulls a default polars
    session.run("uv", "pip", "install", f"polars=={plv}")  # pin the version under test
    session.run("pytest")


@nox.session(python=PY)
def rt32(session: nox.Session) -> None:
    """Default engine: polars-runtime-32 (IdxSize=u32)."""
    session.install(_wheel(session), "pytest")  # wheel pulls the default (runtime-32) polars
    session.run("pytest", env={"POLARS_FORCE_PKG": "32"})


@nox.session(python=PY)
def rt64(session: nox.Session) -> None:
    """bigidx engine: polars-runtime-64 (IdxSize=u64), same prebuilt plugin wheel."""
    session.install(_wheel(session), "pytest")
    session.run("uv", "pip", "install", "polars[rt64]>=1.42,<1.43")  # add the 64 engine
    session.run("pytest", env={"POLARS_FORCE_PKG": "64"})
