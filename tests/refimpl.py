"""Independent reference oracles for the indicator tests.

Each `ref_*` re-derives an indicator by hand in pure Python — deliberately NOT
calling the Rust kernel — so a test comparing kernel output against the oracle is
checking the kernel against a second, independent implementation. They live here,
in one importable module (not inline in each test file), so nothing is duplicated
and the composite indicators reuse the primitives: `ref_atr` is `ref_rma` of
`ref_trange`, and `ref_rsi` smooths its gains/losses with `ref_rma`.

The output is `None` during warmup. A `None` input is skipped by the recursive
oracles (EMA, RMA — and thus RSI, ATR): they emit `None` but carry their running
state across the gap, matching mintalib/polars. The windowed oracles (SMA, WMA)
reset their window on a `None`.
"""

from __future__ import annotations


def ref_ema(xs, period):
    """EMA: seed on the first valid value, then alpha = 2/(period+1) smoothing;
    null during warmup (count < period). A null is skipped: emit null but carry
    the running EMA across the gap."""
    alpha = 2.0 / (period + 1.0)
    ema = None
    count = 0
    out = []
    for x in xs:
        if x is None:
            out.append(None)
            continue
        if count == 0:
            ema = x
        else:
            ema += alpha * (x - ema)
        count += 1
        out.append(ema if count >= period else None)
    return out


def ref_macd(xs, fast=12, slow=26, signal=9):
    """MACD composed from the independent EMA oracle."""
    fast_values = ref_ema(xs, fast)
    slow_values = ref_ema(xs, slow)
    line = [
        None if fast_value is None or slow_value is None else fast_value - slow_value
        for fast_value, slow_value in zip(fast_values, slow_values)
    ]
    signal_line = ref_ema(line, signal)
    histogram = [
        None if value is None or signal_value is None else value - signal_value
        for value, signal_value in zip(line, signal_line)
    ]
    return line, signal_line, histogram


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


def ref_mad(xs, period):
    """Rolling mean absolute deviation, recomputed directly per window."""
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
            mean = sum(window) / period
            out.append(sum(abs(value - mean) for value in window) / period)
        else:
            out.append(None)
    return out


def ref_cci(highs, lows, closes, period):
    """CCI composed independently from typical price, SMA and MAD."""
    typical = [
        None if high is None or low is None or close is None else (high + low + close) / 3
        for high, low, close in zip(highs, lows, closes)
    ]
    average = ref_sma(typical, period)
    deviation = ref_mad(typical, period)
    return [
        None
        if value is None or mean is None or mad is None
        else (value - mean) / (0.015 * mad)
        if mad != 0
        else float("nan")
        for value, mean, mad in zip(typical, average, deviation)
    ]


def ref_rma(xs, period):
    """Wilder's RMA: simple-average seed for the first `period` values, then
    smoothing with alpha = 1/period; null during warmup. A null is skipped: emit
    null but carry the running average across the gap."""
    alpha = 1.0 / period
    rma = None
    total = 0.0
    count = 0
    out = []
    for x in xs:
        if x is None:
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
    yields 0. Output is null until the first delta plus the averages' warmup.

    A null is skipped entirely: gains/losses carry a `None` at every null bar
    (which `ref_rma` skips) while `prev` is kept, so the next valid bar measures
    the real change across the gap. The `None` at the first bar of the series (no
    delta yet) holds the averages in warmup.
    """
    gains = []
    losses = []
    prev = None
    for x in xs:
        if x is None:
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
