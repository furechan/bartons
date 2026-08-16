"""Raise the polars-py ceiling to the newest release — but only if it passes.

The ceiling in `pyproject.toml` is a record of what the nox `compat` matrix has
verified, not a prediction, so it goes stale every time polars releases. Left
alone it eventually blocks users from upgrading polars at all. This does the
whole loop in one command:

  1. look up the newest polars-py on PyPI;
  2. add it to `COMPAT_VERSIONS` in `noxfile.py` if not already there;
  3. run `nox -s "compat(plv=<new>)"` against it;
  4. **only if that passes**, move the ceiling to the next minor.

On failure nothing is left changed — the noxfile edit is rolled back — so a
polars release that genuinely breaks the plugin leaves the declared range honest
rather than silently widened. Nothing is committed either way.

Run via `just raise-ceiling`.
"""

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
NOXFILE = ROOT / "noxfile.py"

RANGE_RE = re.compile(r'"polars>=(?P<floor>[\d.]+),<(?P<ceiling>[\d.]+)"')
CONFIRMED_RE = re.compile(r'^LATEST_CONFIRMED = "(?P<version>[\d.]+)"$', re.M)


def parse(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("."))


def latest_polars_py() -> str:
    with urllib.request.urlopen("https://pypi.org/pypi/polars/json", timeout=30) as r:
        return json.load(r)["info"]["version"]


def next_minor(v: str) -> str:
    major, minor = parse(v)[:2]
    return f"{major}.{minor + 1}"


def main() -> int:
    pyproject = PYPROJECT.read_text()
    m = RANGE_RE.search(pyproject)
    if not m:
        sys.exit("raise-ceiling: could not find the polars range in pyproject.toml")
    floor, ceiling = m.group("floor"), m.group("ceiling")

    noxfile = NOXFILE.read_text()
    cm = CONFIRMED_RE.search(noxfile)
    if not cm:
        sys.exit("raise-ceiling: could not find LATEST_CONFIRMED in noxfile.py")
    confirmed = cm.group("version")

    latest = latest_polars_py()
    print(f"floor {floor} | ceiling <{ceiling} | last confirmed {confirmed} | latest {latest}")

    if parse(latest) < parse(ceiling):
        print(f"nothing to do — {latest} is already inside the declared range.")
        return 0

    # 1. probe it first — nothing is edited until this passes. The `probe` session
    #    takes the version off the command line, so the matrix stays untouched and
    #    there is no edit to roll back if it fails.
    print(f"probing polars-py {latest} ...")
    proc = subprocess.run(["uv", "run", "nox", "-s", "probe", "--", latest], cwd=ROOT)
    if proc.returncode != 0:
        sys.exit(
            f"\nraise-ceiling: polars-py {latest} FAILED — nothing changed, ceiling "
            f"still <{ceiling}>.\nInvestigate before widening the range."
        )

    # 2. passed — it *replaces* the previous confirmation rather than joining the
    #    matrix: it is the ceiling representative, not new engine coverage.
    #    COMPAT_VERSIONS is left alone; engine gaps are revisited when the cargo
    #    pins change, which is when the compiled artifact actually differs.
    NOXFILE.write_text(noxfile.replace(cm.group(0), f'LATEST_CONFIRMED = "{latest}"'))
    print(f"LATEST_CONFIRMED {confirmed} -> {latest}")

    # 3. and move the ceiling
    new_ceiling = next_minor(latest)
    PYPROJECT.write_text(pyproject.replace(m.group(0), f'"polars>={floor},<{new_ceiling}"'))
    print(f"\npassed — ceiling raised <{ceiling} -> <{new_ceiling}>")

    # 4. bring the dev env along. Without this the newly-admitted version is
    #    tested once in a throwaway nox venv and never again: `just test` would
    #    keep running the older engine. Targeted (-P polars) so nothing else in
    #    the lockfile churns.
    #    `uv sync -P polars` re-locks and installs in one step: -P allows that one
    #    package past its pin, and sync updates uv.lock unless --frozen.
    print(f"\nupgrading the dev env to polars-py {latest} ...")
    if subprocess.run(["uv", "sync", "-P", "polars"], cwd=ROOT).returncode != 0:
        sys.exit(
            f"raise-ceiling: `uv sync -P polars` failed. The ceiling is already raised to "
            f"<{new_ceiling}>; re-run that command by hand or revert pyproject.toml."
        )

    # 5. re-run the suite against what is now actually installed
    print("\nre-running the suite against the upgraded dev env ...")
    if subprocess.run(["uv", "run", "pytest", "-q"], cwd=ROOT).returncode != 0:
        sys.exit(
            "raise-ceiling: the suite FAILED against the upgraded dev env, even though the "
            "isolated compat session passed. Investigate before committing — the ceiling and "
            "lockfile are already changed."
        )

    print(f"\ndone. ceiling <{new_ceiling}>, dev env on polars-py {latest}, suite green.")
    print("Review the diff, update the CHANGELOG, and commit. Nothing was committed.")
    print("Note: docs quoting the old range may need updating — grep for it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
