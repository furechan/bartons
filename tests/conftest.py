"""Skip the `#[pyfunction]` direct-call tests on polars engines that can't run them.

pyo3-polars marshals a Series into a raw `#[pyfunction]` via `PySeries._export`,
a polars *Python* API that only exists in newer releases. On older engines
(polars 1.0–1.4) those calls raise `AttributeError`. The registered-expression
path (`.bt.*`) does not use it and works across the full range, so we skip only
the direct-call tests when the capability is absent.
"""

import inspect
import re

import polars as pl
import pytest

try:
    HAS_PYFUNCTION = hasattr(pl.Series("x", [1.0])._s, "_export")
except Exception:
    HAS_PYFUNCTION = False

# Tests that invoke the raw pyfunction entry point, e.g. `plugin.sma(series, ...)`.
_PYFUNC_CALL = re.compile(r"\bplugin\.(ema|sma|rma|wma|trange)\(")


def pytest_collection_modifyitems(config, items):
    if HAS_PYFUNCTION:
        return
    skip = pytest.mark.skip(
        reason="pyo3-polars #[pyfunction] marshalling needs polars with PySeries._export"
    )
    for item in items:
        func = getattr(item, "function", None)
        if func is None:
            continue
        try:
            src = inspect.getsource(func)
        except (OSError, TypeError):
            continue
        if _PYFUNC_CALL.search(src):
            item.add_marker(skip)
