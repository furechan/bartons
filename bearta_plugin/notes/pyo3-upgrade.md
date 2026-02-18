Based on the search results, yes, pyo3 and pyo3-polars should have compatible versions. Currently you have:

  - pyo3 = "0.23"
  - pyo3-polars = "0.20"

  This is problematic because:

  1. PyO3 0.23 has known issues - Earlier versions had stability problems and security vulnerabilities
  2. Version conflicts - Different PyO3 versions can't coexist due to conflicting native library links
  3. Ecosystem migration - The Polars ecosystem has moved to PyO3 0.24

  Recommendation: Update both to use PyO3 0.24:

  pyo3 = { version = "0.24", features = ["extension-module", "abi3-py38"] }
  pyo3-polars = { version = "0.21", features = ["derive", "dtype-struct", "dtype-decimal", "dtype-array"] }

  This will ensure compatibility and avoid the security/stability issues with PyO3 0.23.

  