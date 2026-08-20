"""Preflight a release and verify the uploaded artifacts.

The in-repo version names the next release, plain (no `.devN`), so it stays
publishable at all times and the one real hazard is forgetting to bump: `just
publish` would then try to re-upload a version already on PyPI. PyPI never allows
a version or filename to be reused, even after deletion, so a re-upload cannot fix
a bad release — only a new version can. Failing here beats a 400 halfway through
an upload that has already placed some files, and beats `--skip-existing`, which
would quietly do nothing and let you believe you had published.

A non-numeric or non-three-part version is rejected too. Neither should ever
appear under the current convention; if one does, something edited the version
by hand.

Preflight also requires a clean tree exactly synchronized with its upstream and
fails closed if PyPI cannot be checked. After upload, ``--verify dist/*`` checks
that PyPI has exactly the local filenames and SHA-256 hashes.

Run from the project root. Used by `just publish`; also fine standalone.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

PYPI_JSON = "https://pypi.org/pypi/{name}/json"
TIMEOUT = 10


def project() -> tuple[str, str]:
    with open("pyproject.toml", "rb") as fh:
        meta = tomllib.load(fh)["project"]
    return meta["name"], meta["version"]


def pypi_project(name: str) -> dict:
    """Return the PyPI project response, failing closed on lookup errors."""
    try:
        with urllib.request.urlopen(PYPI_JSON.format(name=name), timeout=TIMEOUT) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"releases": {}}  # project does not exist yet — nothing can collide
        raise RuntimeError(f"PyPI lookup failed: HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"PyPI lookup failed: {exc}") from exc


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()


def preflight() -> int:
    name, version = project()

    if not version.replace(".", "").isdigit() or len(version.split(".")) != 3:
        print(
            f"refusing to publish {name} {version}: expected a plain X.Y.Z release version",
            file=sys.stderr,
        )
        return 1

    if git("status", "--porcelain"):
        print("refusing to publish: the working tree is not clean", file=sys.stderr)
        return 1

    try:
        upstream = git("rev-parse", "--abbrev-ref", "@{upstream}")
        counts = git("rev-list", "--left-right", "--count", "@{upstream}...HEAD")
        behind, ahead = map(int, counts.split())
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"refusing to publish: cannot resolve the upstream branch: {exc}", file=sys.stderr)
        return 1

    if behind or ahead:
        print(
            f"refusing to publish: HEAD is {ahead} ahead and {behind} behind {upstream}",
            file=sys.stderr,
        )
        return 1

    try:
        existing = set(pypi_project(name)["releases"])
    except RuntimeError as exc:
        print(f"refusing to publish: {exc}", file=sys.stderr)
        return 1

    if version in existing:
        print(
            f"refusing to publish {name} {version}: already on PyPI.\n"
            "PyPI never permits reusing a version or filename, even after deletion — "
            "bump the version instead.",
            file=sys.stderr,
        )
        return 1

    branch = git("branch", "--show-current")
    revision = git("rev-parse", "--short", "HEAD")
    print(f"ok: clean, synchronized {branch} at {revision}")
    print(f"ok: {name} {version} is a stable release version not yet on PyPI")
    return 0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(paths: list[Path]) -> int:
    name, version = project()
    local = {path.name: sha256(path) for path in paths}
    remote: dict[str, str] = {}
    error = ""
    for attempt in range(1, 7):
        try:
            release = pypi_project(name)["releases"][version]
            remote = {file["filename"]: file["digests"]["sha256"] for file in release}
            error = "PyPI files do not match dist/"
        except RuntimeError as exc:
            error = str(exc)
        except KeyError:
            error = f"{name} {version} is absent from PyPI"
        if remote == local:
            break
        if attempt < 6:
            print(f"verification attempt {attempt}/6: {error}; retrying in 5 seconds")
            time.sleep(5)
    else:
        print(f"release verification failed: {error}", file=sys.stderr)
        print(f"local:  {local}", file=sys.stderr)
        print(f"remote: {remote}", file=sys.stderr)
        return 1

    print(
        f"ok: PyPI has all {len(local)} artifacts for {name} {version}, "
        "with matching SHA-256 hashes"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", nargs="+", type=Path, metavar="ARTIFACT")
    args = parser.parse_args()
    return verify(args.verify) if args.verify else preflight()


if __name__ == "__main__":
    raise SystemExit(main())
