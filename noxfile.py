"""Test the (single, default) compiled plugin against both polars engines.

bartons' indicators exchange only numeric (Float64) data, so the same default
build runs on polars-runtime-32 (IdxSize=u32) and polars-runtime-64 (bigidx,
IdxSize=u64) — the FFI boundary carries no IdxSize. These sessions prove that:
identical `maturin develop --release` in both, differing only in which engine is
installed and forced via POLARS_FORCE_PKG. See docs/polars-runtime-libraries.md.
"""

import glob
import os
import shutil

import nox

nox.options.default_venv_backend = "uv"

PY = "3.11"
POLARS = "polars>=1.42,<1.43"


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


def _build(session: nox.Session) -> None:
    # dev deps into the session venv; build the extension ourselves (release).
    session.run_install("uv", "sync", "--active", "--group", "dev", "--no-install-project")
    cargo_bin = _cargo_bin()
    env = {"PATH": cargo_bin + os.pathsep + os.environ["PATH"]} if cargo_bin else None
    session.run("maturin", "develop", "--release", env=env)  # default build — same in both engines


# One representative polars per *distinct engine crate version* across [1.0, 1.43) —
# every distinct FFI/Arrow boundary in the supported range (patch releases within a
# crate group share the engine, so testing one per group is complete). The plugin is
# built once against crate 0.54.4 (→ polars 1.42) and run against all of them.
# version -> crate:  1.0.0→0.41.2  1.1.0→0.41.3  1.6.0→0.42.0  1.7.0→0.43.0
# 1.7.1→0.43.1  1.13.0→0.44.2  1.17.1→0.45.1  1.22.0→0.46.0  1.30.0→0.48.1
# 1.32.0→0.49.1  1.32.1→0.50.0  1.34.0→0.51.0  1.36.0→0.52.0  1.39.0→0.53.0  1.42.0→0.54.4
COMPAT_VERSIONS = [
    "1.0.0", "1.1.0", "1.6.0", "1.7.0", "1.7.1", "1.13.0", "1.17.1", "1.22.0",
    "1.30.0", "1.32.0", "1.32.1", "1.34.0", "1.36.0", "1.39.0", "1.42.0",
]


@nox.session(python=PY)
@nox.parametrize("plv", COMPAT_VERSIONS)
def compat(session: nox.Session, plv: str) -> None:
    """Run the suite against one specific polars version (same default plugin build)."""
    session.install("maturin", "pytest")
    cargo_bin = _cargo_bin()
    env = {"PATH": cargo_bin + os.pathsep + os.environ["PATH"]} if cargo_bin else None
    session.run("maturin", "develop", "--release", env=env)
    session.run("uv", "pip", "install", f"polars=={plv}")  # pin the version under test
    session.run("pytest")


@nox.session(python=PY)
def rt32(session: nox.Session) -> None:
    """Default engine: polars-runtime-32 (IdxSize=u32)."""
    _build(session)
    session.run("pytest", env={"POLARS_FORCE_PKG": "32"})


@nox.session(python=PY)
def rt64(session: nox.Session) -> None:
    """bigidx engine: polars-runtime-64 (IdxSize=u64), same default plugin build."""
    _build(session)
    session.run("uv", "pip", "install", "polars[rt64]>=1.42,<1.43")  # add the 64 engine
    session.run("pytest", env={"POLARS_FORCE_PKG": "64"})
