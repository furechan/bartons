# `polars-talib` linking workaround

## Symptom

The Linux AArch64 wheel for `polars-talib==0.1.6` can fail during import with
an unresolved TA-Lib symbol, for example:

```text
ImportError: .../_polars_talib.abi3.so:
undefined symbol: TA_CDL3BLACKCROWS_Lookback
```

This was reproduced with the
`polars_talib-0.1.6-cp37-abi3-manylinux_2_34_aarch64.whl` wheel. A similar
unresolved-symbol problem has also been reported upstream on macOS Intel, but
the workaround below is the one verified in this repository on Linux AArch64.

## Cause

The extension contains unresolved `TA_*` references but does not declare the
TA-Lib shared library as a normal dynamic dependency. The Python `ta-lib`
package supplies that library under `ta_lib.libs`, but its symbols are not
automatically placed in the process-global namespace where `_polars_talib`
expects to find them.

Useful diagnostics are:

```sh
readelf -d path/to/_polars_talib.abi3.so
nm -D path/to/_polars_talib.abi3.so | grep TA_CDL3BLACKCROWS_Lookback
nm -D path/to/ta_lib.libs/libta-lib.so | grep TA_CDL3BLACKCROWS_Lookback
```

The first command shows that there is no `DT_NEEDED` entry for TA-Lib. The
other two show that the extension needs the symbol and that the bundled TA-Lib
library exports it.

## Temporary workaround

Preload the shared library with `RTLD_GLOBAL` before importing
`polars_talib`:

```python
import ctypes
import glob
import os
import sysconfig

site_packages = sysconfig.get_paths()["purelib"]
matches = glob.glob(
    os.path.join(site_packages, "ta_lib.libs", "libta-lib*.so*")
)
if not matches:
    raise RuntimeError("the TA-Lib shared library was not found")

ctypes.CDLL(matches[0], mode=ctypes.RTLD_GLOBAL | os.RTLD_NOW)

import polars_talib
```

This is application-side wheel-layout discovery, so it should remain a
workaround rather than a public library API. The benchmark implements a
try-normal-import-first version in
[`benchmarks/benchmark-vs-talib.py`](../benchmarks/benchmark-vs-talib.py).

## Proper upstream fix

The wheel should make the dependency load normally. Possible packaging fixes
include linking the extension to a bundled TA-Lib shared library with an
`$ORIGIN`-relative runtime path, repairing the wheel with `auditwheel`, or
statically linking TA-Lib into the extension.

Upstream references:

- [Linux AArch64 issue #36](https://github.com/Yvictor/polars_ta_extension/issues/36)
- [macOS Intel issue #24](https://github.com/Yvictor/polars_ta_extension/issues/24)
