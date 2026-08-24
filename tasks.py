"""Project workflows. Run ``uv run inv --list`` to see available tasks."""

import os
import shlex
import shutil
import sysconfig
import urllib.error
import urllib.request

from pathlib import Path

from invoke.context import Context
from invoke.exceptions import Exit
from invoke.tasks import task


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
PYPROJECT = ROOT / "pyproject.toml"
BUILD_JOBS = max(1, (os.cpu_count() or 2) // 2)


def cargo_test(c: Context) -> None:
    python_libdir = sysconfig.get_config_var("LIBDIR")
    env = {
        "PYO3_PYTHON": str(ROOT / ".venv/bin/python"),
        "LD_LIBRARY_PATH": os.pathsep.join(
            part
            for part in [python_libdir, os.environ.get("LD_LIBRARY_PATH")]
            if part
        ),
    }
    c.run(
        "cargo test --manifest-path bartons/Cargo.toml --no-default-features",
        env=env,
    )


def clean_dist(c: Context) -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()


def capture_output(c: Context, command: str) -> str:
    return c.run(command, hide=True).stdout.strip()


def check_pypi(c: Context, version: str) -> None:
    url = f"https://pypi.org/pypi/bartons/{version}/json"
    try:
        urllib.request.urlopen(url).close()
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise Exit(
                f"refusing to publish bartons {version}: PyPI returned HTTP {error.code}"
            ) from error
    except urllib.error.URLError as error:
        raise Exit(f"refusing to publish bartons {version}: {error.reason}") from error
    else:
        raise Exit(f"refusing to publish bartons {version}: already on PyPI")


def publish_guard(c: Context) -> None:
    status = capture_output(c, "git status --short --branch").splitlines()
    if len(status) != 1:
        raise Exit("refusing to publish: the working tree is not clean")

    branch_status = status[0].removeprefix("## ")
    if "..." not in branch_status:
        raise Exit("refusing to publish: no upstream branch to compare against")

    branch, upstream = branch_status.split("...", 1)
    if " [" in upstream:
        raise Exit(f"refusing to publish: branch is not synchronized ({branch_status})")

    version = capture_output(c, "uv version --short")

    check_pypi(c, version)

    commit = capture_output(c, "git rev-parse --short HEAD")
    print(f"ok: clean, synchronized {branch} at {commit}")
    print(f"ok: bartons {version} is not yet on PyPI")


@task
def make(c: Context) -> None:
    """Prepare and validate the source tree."""
    c.run("maturin develop --release")
    c.run("python scripts/generate-kernel-stubs.py")
    c.run("python scripts/generate-indicator-stubs.py")
    c.run("uv run python scripts/update-readme.py")
    c.run("uv run ty check")
    test(c)


@task
def build(c: Context, jobs: int = BUILD_JOBS) -> None:
    """Build an sdist and its wheel, then test the wheel."""

    clean_dist(c)

    c.run("maturin sdist --manifest-path bartons/Cargo.toml --out dist")

    sdists = list(DIST.glob("*.tar.gz"))
    if len(sdists) != 1:
        raise Exit(f"expected one sdist in dist/, found {len(sdists)}")
    sdist = shlex.quote(str(sdists[0]))
    c.run(
        f"uv build --wheel {sdist} --out-dir dist "
        "--config-setting 'build-args=--compatibility pypi'",
        env={
            "CARGO_BUILD_JOBS": str(jobs),
            "CARGO_TARGET_DIR": str(ROOT / ".venv/cargo-target/sdist"),
        },
    )
    c.run("nox -s dist_wheel")


@task
def publish(c: Context) -> None:
    """Upload the current dist/ artifacts and bump the patch version."""
    publish_guard(c)
    artifacts = sorted([*DIST.glob("*.whl"), *DIST.glob("*.tar.gz")])
    if not artifacts:
        raise Exit("no artifacts in dist/; run: inv build")
    names = " ".join(path.name for path in artifacts)
    if input(f"Upload {names} to PyPI? [y/N] ") not in {"y", "Y"}:
        raise Exit("publish cancelled")
    quoted = shlex.join(str(path) for path in artifacts)
    c.run(f"uv run maturin upload --non-interactive {quoted}")
    c.run("uv version --bump patch --no-sync")


@task
def test(c: Context) -> None:
    """Run native Rust tests and pytest."""
    c.run("uv run pytest")



@task
def stubs(c: Context) -> None:
    """Regenerate kernel and indicator stubs."""
    c.run("maturin develop --release")
    c.run("python scripts/generate-kernel-stubs.py")
    c.run("python scripts/generate-indicator-stubs.py")


@task
def readme(c: Context) -> None:
    """Regenerate the README indicator catalog."""
    c.run("uv run python scripts/update-readme.py")


@task
def bench(c: Context, baseline: str = "vs-native") -> None:
    """Benchmark against vs-native, vs-talib, or vs-mintalib."""
    c.run("maturin develop --release")
    c.run(f"python {shlex.quote(f'benchmarks/benchmark-{baseline}.py')}")


@task
def dump(c: Context) -> None:
    """List the contents of every sdist in dist/."""
    sdists = sorted(DIST.glob("*.tar.gz"))
    if not sdists:
        raise Exit("no sdist in dist/; run: inv build")
    for sdist in sdists:
        c.run(f"tar -ztvf {shlex.quote(str(sdist))}")


@task
def raise_ceiling(c: Context) -> None:
    """Test the newest Polars and raise the supported ceiling if it passes."""
    c.run("python scripts/raise-ceiling.py")


@task
def clean(c: Context) -> None:
    """Remove Rust targets and compiled extension modules."""
    del c
    target = ROOT / "bartons/target"
    if target.exists():
        print(target)
        shutil.rmtree(target)
    for extension in (ROOT / "python").rglob("*.so"):
        print(extension)
        extension.unlink()
    PYPROJECT.touch()
