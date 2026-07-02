"""Independent reference oracles for the indicator tests.

Each `ref_*` re-derives an indicator by hand in pure Python — deliberately NOT
calling the Rust kernel — so a test comparing kernel output against the oracle is
checking the kernel against a second, independent implementation. They live here,
in one importable module (not inline in each test file), so nothing is duplicated
and the composite indicators reuse the primitives: `ref_atr` is `ref_rma` of
`ref_trange`, and `ref_rsi` smooths its gains/losses with `ref_rma`.

By convention a `None` input breaks the current run (gap reset) and the output is
`None` during warmup.
"""

from __future__ import annotations


def ref_ema(xs, period):
    """EMA: seed on the first valid value, then alpha = 2/(period+1) smoothing;
    null during warmup (count < period), reset the run on a null."""
    alpha = 2.0 / (period + 1.0)
    ema = None
    count = 0
    out = []
    for x in xs:
        if x is None:
            ema = None
            count = 0
            out.append(None)
            continue
        if count == 0:
            ema = x
        else:
            ema += alpha * (x - ema)
        count += 1
        out.append(ema if count >= period else None)
    return out


def ref_sma(xs, period):
    """SMA: rolling mean of the last `period` values; null during warmup (fewer
    than `period` seen), reset on a null."""
    out = []
    window = []
    for x in xs:
        if x is None:
            window = []
            out.append(None)
            continue
        window.append(x)
        if len(window) > period:
            window.pop(0)
        out.append(sum(window) / period if len(window) == period else None)
    return out


def ref_rma(xs, period):
    """Wilder's RMA: simple-average seed for the first `period` values, then
    smoothing with alpha = 1/period; null during warmup, reset on a null."""
    alpha = 1.0 / period
    rma = None
    total = 0.0
    count = 0
    out = []
    for x in xs:
        if x is None:
            rma = None
            total = 0.0
            count = 0
            out.append(None)
            continue
        count += 1
        if count <= period:
            total += x
            rma = total / count
        else:
            rma += alpha * (x - rma)
        out.append(rma if count >= period else None)
    return out


def ref_wma(xs, period):
    """WMA: weighted mean of the last `period` values (oldest weight 1 .. newest
    weight `period`); null during warmup, reset on a null. Computed directly (not
    incrementally) to catch kernel bugs."""
    wdiv = period * (period + 1) / 2
    out = []
    window = []
    for x in xs:
        if x is None:
            window = []
            out.append(None)
            continue
        window.append(x)
        if len(window) > period:
            window.pop(0)
        if len(window) == period:
            wsum = sum((i + 1) * window[i] for i in range(period))
            out.append(wsum / wdiv)
        else:
            out.append(None)
    return out


def ref_trange(highs, lows, closes):
    """True Range: max(h-l, |h-prev_close|, |l-prev_close|), first bar = h-l,
    null when high or low is missing."""
    out = []
    prev_close = None
    for h, l, c in zip(highs, lows, closes):
        if h is None or l is None:
            out.append(None)
        else:
            tr = h - l
            if prev_close is not None:
                tr = max(tr, abs(h - prev_close), abs(l - prev_close))
            out.append(tr)
        prev_close = c
    return out


def ref_rsi(xs, period):
    """Wilder's RSI: bar-to-bar gains and losses each smoothed with `ref_rma`
    (alpha = 1/period), RSI = 100 * avg_gain / (avg_gain + avg_loss); a flat run
    yields 0. Output is null until the first delta plus the averages' warmup; a
    null resets the run.

    Gains/losses carry a `None` at every null bar and at the first bar of each run
    (no delta yet); feeding those to `ref_rma` resets/holds its warmup exactly as
    the kernel does, so the two Wilder averages need no bespoke state here.
    """
    gains = []
    losses = []
    prev = None
    for x in xs:
        if x is None:
            prev = None
            gains.append(None)
            losses.append(None)
            continue
        if prev is None:
            prev = x
            gains.append(None)
            losses.append(None)
            continue
        delta = x - prev
        prev = x
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = ref_rma(gains, period)
    avg_loss = ref_rma(losses, period)
    out = []
    for ag, al in zip(avg_gain, avg_loss):
        if ag is None or al is None:
            out.append(None)
        else:
            denom = ag + al
            out.append(0.0 if denom == 0.0 else 100.0 * ag / denom)
    return out


def ref_atr(highs, lows, closes, period):
    """ATR is Wilder's RMA of the True Range — `ref_rma` of `ref_trange`."""
    return ref_rma(ref_trange(highs, lows, closes), period)
