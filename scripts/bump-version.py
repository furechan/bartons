"""Bump the patch version in pyproject.toml.

The in-repo version names the *next* release. So this runs immediately after a
publish — the version just shipped is now taken, and the repo should name what
comes after it. Mirrors `bump_version` in mintalib's tasks.py.

Run from the project root. Used by `just bump`; also fine standalone.
"""

import re
import sys
from pathlib import Path

PATTERN = r"^version \s* = \s* \"(.+)\" \s*"


def main() -> int:
    pyproject = Path("pyproject.toml").resolve(strict=True)
    buffer = pyproject.read_text()

    match = re.search(PATTERN, buffer, flags=re.VERBOSE | re.MULTILINE)
    if not match:
        print("error: could not find version setting in pyproject.toml", file=sys.stderr)
        return 1

    current = match.group(1)
    try:
        parts = tuple(int(i) for i in current.split("."))
    except ValueError:
        # A suffixed version (0.1.0rc1, 0.1.0.dev0) has no obvious patch to
        # increment, and guessing would silently ship the wrong number.
        print(f"error: cannot bump non-numeric version {current!r}", file=sys.stderr)
        return 1

    bumped = ".".join(str(v) for v in parts[:-1] + (parts[-1] + 1,))
    pyproject.write_text(
        re.sub(PATTERN, f'version = "{bumped}"\n', buffer, flags=re.VERBOSE | re.MULTILINE)
    )
    print(f"{current} -> {bumped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
