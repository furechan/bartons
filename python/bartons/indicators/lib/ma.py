"""Generic moving-average expression dispatcher."""

import polars as pl

from ...prelude import wrap_src_indicator
from ...typing import IntoExprColumn, MAType
from .dema import DEMA
from .ema import EMA
from .kama import KAMA
from .sma import SMA
from .tema import TEMA
from .wma import WMA

__all__ = ("MA",)

_MA_FACTORIES = {
    "sma": SMA,
    "ema": EMA,
    "wma": WMA,
    "dema": DEMA,
    "tema": TEMA,
    "kama": KAMA,
}


@wrap_src_indicator
def MA(
    period: int = 30,
    *,
    matype: MAType = "sma",
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Moving average selected by ``matype``.

    The dispatcher constructs the corresponding concrete indicator expression;
    it does not introduce another numerical kernel.

    Args:
        period: moving-average period.
        matype: one of ``sma``, ``ema``, ``wma``, ``dema``, ``tema``, or
            ``kama``.
        src: input column expression or name.

    Raises:
        ValueError: if ``matype`` is unsupported.
    """
    try:
        factory = _MA_FACTORIES[matype]
    except KeyError:
        raise ValueError(f"unsupported matype: {matype!r}") from None
    return factory(period, src=src)
