"""Refuse to publish a version that should not be published.

The in-repo version names the next release, plain (no `.devN`), so it stays
publishable at all times and the one real hazard is forgetting to bump: `just
publish` would then try to re-upload a version already on PyPI. PyPI never allows
a version or filename to be reused, even after deletion, so a re-upload cannot fix
a bad release — only a new version can. Failing here beats a 400 halfway through
an upload that has already placed some files, and beats `--skip-existing`, which
would quietly do nothing and let you believe you had published.

A `.devN` or local (`+…`) version is rejected too. Neither should ever appear
under the current convention; if one does, something edited the version by hand.

Run from the project root. Used by `just publish`; also fine standalone.
"""

import json
import sys
import tomllib
import urllib.error
import urllib.request

PYPI_JSON = "https://pypi.org/pypi/{name}/json"
TIMEOUT = 10


def project() -> tuple[str, str]:
    with open("pyproject.toml", "rb") as fh:
        meta = tomllib.load(fh)["project"]
    return meta["name"], meta["version"]


def published_versions(name: str) -> set[str] | None:
    """Versions already on PyPI, or None if that could not be determined."""
    try:
        with urllib.request.urlopen(PYPI_JSON.format(name=name), timeout=TIMEOUT) as resp:
            return set(json.load(resp)["releases"])
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return set()  # project does not exist yet — nothing can collide
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def main() -> int:
    name, version = project()

    if ".dev" in version or "+" in version:
        print(
            f"refusing to publish {name} {version}: not a plain release version.\n"
            f"The in-repo version should name the next release with no suffix.",
            file=sys.stderr,
        )
        return 1

    existing = published_versions(name)
    if existing is None:
        # Not fatal: the upload itself will reject a duplicate. Say so rather than
        # implying the check passed.
        print(f"warning: could not reach PyPI to check existing {name} versions", file=sys.stderr)
    elif version in existing:
        print(
            f"refusing to publish {name} {version}: already on PyPI.\n"
            f"PyPI never permits reusing a version or filename, even after deletion — "
            f"bump the version instead.",
            file=sys.stderr,
        )
        return 1

    print(f"ok: {name} {version} is a release version and not yet on PyPI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
