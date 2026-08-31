"""Version-portable test helpers.

`polars.testing.assert_series_equal` gained the `rel_tol`/`abs_tol` keywords only
in polars 1.32.3, so calling it with those kwargs raises `TypeError` on the older
engines the `compat` matrix still covers (polars 1.28–1.32.2). This drop-in
replacement reproduces the subset of its behaviour the suite uses, using only
stable Series API (`len`, `name`, `dtype`, `to_list`) so it works across the whole
supported polars range. See notes/maintenance/test-compat-helpers.md.
"""

from __future__ import annotations


def assert_series_equal(
    got,
    expected,
    *,
    check_names: bool = True,
    check_dtype: bool = True,
    check_exact: bool = True,
    rel_tol: float = 0.0,
    abs_tol: float = 0.0,
    **_ignored,
) -> None:
    assert len(got) == len(expected), f"length {len(got)} != {len(expected)}"
    if check_names:
        assert got.name == expected.name, f"name {got.name!r} != {expected.name!r}"
    if check_dtype:
        assert got.dtype == expected.dtype, f"dtype {got.dtype} != {expected.dtype}"
    g, e = got.to_list(), expected.to_list()
    for i, (a, b) in enumerate(zip(g, e)):
        if a is None or b is None:
            assert a is None and b is None, f"null mismatch at {i}: {a!r} vs {b!r}"
        elif check_exact:
            assert a == b, f"mismatch at {i}: {a!r} != {b!r}"
        else:
            assert abs(a - b) <= abs_tol + rel_tol * abs(b), (
                f"mismatch at {i}: {a!r} vs {b!r} (rel_tol={rel_tol}, abs_tol={abs_tol})"
            )
