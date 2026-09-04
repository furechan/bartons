"""Project workflows. Run ``uv run inv --list`` to see available tasks."""

import json
import os
import re
import shlex
import shutil
import sys
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
VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:\.dev0)?")


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



def latest_pypi_version() -> str:
    url = "https://pypi.org/pypi/bartons/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.load(response)["info"]["version"]
    except urllib.error.HTTPError as error:
        raise Exit(f"could not get the latest PyPI version: HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise Exit(f"could not get the latest PyPI version: {error.reason}") from error
    except (KeyError, TypeError, ValueError) as error:
        raise Exit("could not read the latest version from PyPI's response") from error


@task
def make(c: Context) -> None:
    """Prepare and validate the source tree."""
    c.run("maturin develop --release")
    stubs(c)
    lint(c)
    test(c)


@task
def build(c: Context, jobs: int = BUILD_JOBS) -> None:
    """Legacy: build an sdist and its wheel, then test the wheel locally."""

    print(
        "warning: inv build is a legacy local check; releases are built by the CI release workflow",
        file=sys.stderr,
    )

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
def bump(c: Context) -> None:
    """Move a released patch version to the next patch development version."""
    version = c.run("uv version --short", hide=True).stdout.strip()
    match = VERSION_PATTERN.fullmatch(version)
    if match is None or version.endswith(".dev0"):
        raise Exit(f"expected a plain three-part release version, found {version!r}")
    major, minor, patch = map(int, match.groups())
    next_version = f"{major}.{minor}.{patch + 1}.dev0"
    c.run(f"uv version --no-sync {next_version}")
    print(f"Started development of {next_version}")


@task
def release(c: Context) -> None:
    """Preflight, commit, tag, and push the current development release."""
    branch = c.run("git branch --show-current", hide=True).stdout.strip()
    if branch != "main":
        print(f"Nothing to release from {branch!r}; switch to main first")
        return

    dev_version = c.run("uv version --short", hide=True).stdout.strip()
    match = VERSION_PATTERN.fullmatch(dev_version)
    if match is None or not dev_version.endswith(".dev0"):
        raise Exit(f"expected a three-part .dev0 version, found {dev_version!r}")
    major, minor, patch = map(int, match.groups())
    if patch == 0:
        raise Exit("automatic patch releases require a nonzero patch component")
    release_version = f"{major}.{minor}.{patch}"
    next_version = f"{major}.{minor}.{patch + 1}.dev0"
    tag = f"v{release_version}"

    c.run("nox")

    c.run(f"uv version --no-sync {release_version}")
    c.run("git add pyproject.toml uv.lock")
    c.run(f'git commit -m "Release version {release_version}"')
    c.run(f'git tag -a {tag} -m "Release {release_version}"')
    c.run(f"git push origin main {tag}")

    c.run(f"uv version --no-sync {next_version}")
    c.run("git add pyproject.toml uv.lock")
    c.run(f'git commit -m "Start development of {next_version}"')
    c.run("git push origin main")
    print(f"Pushed {tag} for release and advanced main to {next_version}")


@task
def info(c: Context) -> None:
    """Show the current project version and the latest version on PyPI."""
    version = c.run("uv version --short", hide=True).stdout.strip()
    pypi_version = latest_pypi_version()
    print(f"Current version: {version}")
    print(f"Latest on PyPI: {pypi_version}")



@task
def test(c: Context) -> None:
    """Run native Rust tests and pytest."""
    c.run("uv run pytest")


@task
def lint(c: Context) -> None:
    """Run linting checks."""
    c.run("uv run ty check")


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
