"""Test the (single, default) compiled plugin against both polars engines.

bartons' indicators exchange only numeric (Float64) data, so the same default
build runs on polars-runtime-32 (IdxSize=u32) and polars-runtime-64 (bigidx,
IdxSize=u64) — the FFI boundary carries no IdxSize. These sessions prove that:
one `maturin build --release` wheel runs in both, differing only in which engine
is installed and forced via POLARS_FORCE_PKG. See docs/polars-runtime-libraries.md.

The extension is identical for every engine and every polars version under test
(same polars-rs 0.55.2; the FFI boundary carries no IdxSize), so we compile ONE abi3
wheel and install that same artifact into every session. uv caches and unpacks
the wheel near-instantly, so the 15 compat + rt32 + rt64 sessions share a single
cargo build instead of recompiling (`maturin develop`) in 17 isolated venvs. Only
the installed *polars* wheel differs between sessions.
"""

import glob
import os
import shutil

import nox
from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename

nox.options.default_venv_backend = "uv"

# Keep the session virtualenvs under `.venv/` instead of a second top-level
# `.nox/`, so all throwaway environments live in one place. They are caches: if
# uv ever recreates `.venv`, nox just rebuilds them on the next run.
nox.options.envdir = ".venv/.nox"

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
        if os.environ.get("BARTONS_RELEASE") == "1":
            supported = set(sys_tags())
            wheels = [
                wheel
                for wheel in glob.glob(os.path.abspath("dist/bartons-*.whl"))
                if not parse_wheel_filename(os.path.basename(wheel))[3].isdisjoint(supported)
            ]
            if len(wheels) != 1:
                session.error(
                    f"release mode requires exactly one locally installable dist wheel; found {wheels}"
                )
            _WHEEL = wheels[0]
            session.log(f"using release artifact {_WHEEL}")
            return _WHEEL
        for old in glob.glob("dist/bartons-*.whl"):
            os.remove(old)
        session.install("maturin")
        cargo_bin = _cargo_bin()
        env = {"PATH": cargo_bin + os.pathsep + os.environ["PATH"]} if cargo_bin else None
        session.run("maturin", "build", "--release", "--out", "dist", env=env)
        (_WHEEL,) = glob.glob("dist/bartons-*.whl")  # exactly one after the clean above
    return _WHEEL


def _latest_wheel(session: nox.Session) -> str:
    """Return the newest locally installable wheel in ``dist/`` without building it."""
    supported = set(sys_tags())
    wheels = [
        wheel
        for wheel in glob.glob(os.path.abspath("dist/bartons-*.whl"))
        if not parse_wheel_filename(os.path.basename(wheel))[3].isdisjoint(supported)
    ]
    if not wheels:
        session.error("no locally installable wheel found in dist/; run `just build` first")
    return max(wheels, key=os.path.getmtime)


# --- what the matrix runs -------------------------------------------------------
#
# Two independent things, deliberately kept apart:
#
# COMPAT_VERSIONS is *engine coverage*: one representative polars-py per distinct
# engine crate, so every FFI/Arrow boundary the plugin can meet is exercised.
# Patch releases within a crate group share the engine, so one per group is
# complete. This list only needs revisiting when the **cargo pins change** — that
# is when the compiled artifact changes and coverage actually matters. Gaps
# between it and LATEST_CONFIRMED are expected and fine; walk the version history
# and fill them in at pin-change time if the jump warrants it.
#
# LATEST_CONFIRMED is the *ceiling representative*: the newest polars-py verified
# against the current build. The `pyproject.toml` ceiling is derived from it
# (`< next minor`). `just raise-ceiling` probes a newer release and, if it passes,
# moves this and the ceiling together. It is a single value, not an accumulating
# list — a newer confirmation replaces the older one rather than adding to the
# matrix, because it adds no engine coverage.
#
# Floor is 1.28: the eager kernels.<name> pyfunctions need PySeries._export, which
# polars only exposes from 1.28 (see docs/test-compat-helpers.md). 1.28.0 also
# represents engine crate 0.46.0, whose group spans polars 1.22–1.29.
# version -> crate:  1.28.0→0.46.0  1.30.0→0.48.1  1.32.0→0.49.1  1.32.1→0.50.0
# 1.34.0→0.51.0  1.38.1→0.52.0  1.39.0→0.53.0  1.42.0→0.54.4
#
# Yanked polars-runtime-32 wheels make some polars-py versions uninstallable, so a
# representative is picked around them: 1.36.0 (crate 0.52.0) is yanked -> use
# 1.38.1; 1.43.0 and 1.43.1 are yanked -> use 1.43.2. `nox -s probe -- <ver>`
# surfaces this immediately as an unsatisfiable resolution, not a test failure.
COMPAT_VERSIONS = [
    "1.28.0", "1.30.0", "1.32.0", "1.32.1", "1.34.0", "1.38.1", "1.39.0", "1.42.0",
]

LATEST_CONFIRMED = "1.43.2"

# The matrix is the union, order-preserving and deduped — LATEST_CONFIRMED may
# coincide with an engine representative.
MATRIX = list(dict.fromkeys([*COMPAT_VERSIONS, LATEST_CONFIRMED]))


def _locked_polars() -> str:
    """The polars-py version pinned in `uv.lock` — what the dev venv actually runs."""
    import tomllib

    with open("uv.lock", "rb") as fh:
        for pkg in tomllib.load(fh)["package"]:
            if pkg["name"] == "polars":
                return pkg["version"]
    raise RuntimeError("no polars entry in uv.lock")


def _run_against(session: nox.Session, plv: str) -> None:
    """Install the prebuilt wheel, pin polars-py to `plv`, run the suite."""
    session.install(_wheel(session), "pytest")  # prebuilt extension; pulls a default polars
    session.run("uv", "pip", "install", f"polars=={plv}")  # pin the version under test
    session.run("pytest")


@nox.session(python=PY)
@nox.parametrize("plv", MATRIX)
def compat(session: nox.Session, plv: str) -> None:
    """Run the suite against one polars-py from the matrix (same prebuilt wheel)."""
    _run_against(session, plv)


# default=False: `probe` requires a version argument, so a bare `nox` must not
# select it — it would abort and make the whole run look failed.
@nox.session(python=PY, default=False)
def probe(session: nox.Session) -> None:
    """Run the suite against an arbitrary polars-py, not necessarily in the matrix:

        uv run nox -s probe -- 1.44.0

    For trying a release before deciding to adopt it. `compat` is the adopted set
    and is fixed at collection time by `@nox.parametrize`, so it cannot take a
    version off the command line — this session exists for exactly that.

    Note `uv pip install polars==<plv>` does not enforce the installed wheel's
    `Requires-Dist`, so a version above the current ceiling can be probed. That is
    deliberate: it is what lets `just raise-ceiling` verify *before* declaring.
    """
    if len(session.posargs) != 1:
        session.error("usage: nox -s probe -- <polars-py version>, e.g. 1.44.0")
    _run_against(session, session.posargs[0])


@nox.session(python=PY)
def locked(session: nox.Session) -> None:
    """Run the suite against the polars-py pinned in `uv.lock`.

    This is the version daily development actually uses — but exercised against
    the **built wheel in a clean env**, rather than the editable install `just
    test` uses. Catches packaging problems the dev env cannot see, and confirms
    the shipped artifact works on the engine the lockfile claims.

    Unlike `compat`/`probe` the version is not chosen: it follows `uv.lock`, so it
    moves whenever `just raise-ceiling` (or a manual `uv lock`) moves it.
    """
    plv = _locked_polars()
    session.log(f"uv.lock pins polars-py {plv}")
    _run_against(session, plv)


@nox.session(python=PY, default=False)
def wheel_smoke(session: nox.Session) -> None:
    """Install the newest existing dist wheel and run one test outside the checkout.

    This deliberately does not build: it checks the artifact currently waiting in
    ``dist/``. Running pytest from Nox's temporary directory prevents ``bartons``
    from being imported from the source tree by accident.

        uv run nox -s wheel_smoke
    """
    wheel = _latest_wheel(session)
    session.log(f"testing {wheel}")
    session.install(wheel, "pytest")
    test = os.path.abspath("tests/test_bartons.py")
    session.chdir(session.create_tmp())
    session.run("pytest", test)


@nox.session(python=PY)
def rt32(session: nox.Session) -> None:
    """Default engine: polars-runtime-32 (IdxSize=u32)."""
    session.install(_wheel(session), "pytest")  # wheel pulls the default (runtime-32) polars
    session.run("pytest", env={"POLARS_FORCE_PKG": "32"})


@nox.session(python=PY)
def rt64(session: nox.Session) -> None:
    """bigidx engine: polars-runtime-64 (IdxSize=u64), same prebuilt plugin wheel."""
    session.install(_wheel(session), "pytest")
    session.run("uv", "pip", "install", "polars[rt64]>=1.43,<1.44")  # add the 64 engine
    session.run("pytest", env={"POLARS_FORCE_PKG": "64"})
