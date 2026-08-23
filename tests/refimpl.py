"""Independent reference oracles for the indicator tests.

Each `ref_*` re-derives an indicator by hand in pure Python — deliberately NOT
calling the Rust kernel — so a test comparing kernel output against the oracle is
checking the kernel against a second, independent implementation. They live here,
in one importable module (not inline in each test file), so nothing is duplicated
and the composite indicators reuse the primitives: `ref_atr` is `ref_rma` of
`ref_trange`, and `ref_rsi` smooths its gains/losses with `ref_rma`.

The output is `None` during warmup. A `None` input is skipped by the recursive
oracles (EMA, RMA — and thus RSI, ATR): they emit `None` but carry their running
state across the gap, matching mintalib/polars. The windowed oracles (SMA, WMA,
KER) reset their window on a `None`. `ref_kama` is the hybrid: its window resets
while its running average carries.
"""

from __future__ import annotations

import math


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


def ref_ker(xs, period):
    """Kaufman Efficiency Ratio: the magnitude of the net move over a window of
    `period` changes divided by the total distance travelled within it, in
    0..=1; a window that never moved counts as perfectly efficient (1.0).

    `period` changes span `period + 1` values, so warmup ends one row later than
    a plain rolling window. A null resets both the window and the previous
    value, so no change ever spans a gap. Recomputed directly per window (not
    incrementally) to catch kernel bugs."""
    out = []
    window = []
    for x in xs:
        if x is None:
            window = []
            out.append(None)
            continue
        window.append(x)
        if len(window) > period + 1:
            window.pop(0)
        if len(window) == period + 1:
            direction = abs(window[-1] - window[0])
            volatility = sum(abs(b - a) for a, b in zip(window, window[1:]))
            out.append(1.0 if volatility == 0.0 else direction / volatility)
        else:
            out.append(None)
    return out


def ref_kama(xs, period=10, fastn=2, slown=30):
    """Kaufman Adaptive Moving Average composed from the independent KER oracle:
    an EMA whose alpha is `(slow + KER * (fast - slow)) ** 2`, seeded on the
    first row the ratio is available for. The ratio's window resets on a null
    while the running average carries across the gap."""
    fast = 2.0 / (fastn + 1.0)
    slow = 2.0 / (slown + 1.0)
    ratios = ref_ker(xs, period)
    kama = None
    out = []
    for x, ratio in zip(xs, ratios):
        if x is None or ratio is None:
            out.append(None)
            continue
        alpha = (slow + ratio * (fast - slow)) ** 2.0
        kama = x if kama is None else kama + alpha * (x - kama)
        out.append(kama)
    return out


def ref_linreg(xs, period=20, output="forecast", offset=0):
    """Rolling least-squares regression on the integer grid 1..period.

    Nulls reset the window. ``forecast`` evaluates the fitted line at
    ``period + offset``; the diagnostics describe the fitted window itself.
    """
    window = []
    out = []
    xbar = (period + 1.0) / 2.0
    vxx = sum((x - xbar) ** 2 for x in range(1, period + 1)) / period

    for value in xs:
        if value is None:
            window = []
            out.append(None)
            continue
        window.append(float(value))
        if len(window) > period:
            window.pop(0)
        if len(window) < period:
            out.append(None)
            continue

        ybar = sum(window) / period
        vxy = sum((x - xbar) * (y - ybar) for x, y in enumerate(window, 1)) / period
        vyy = sum((y - ybar) ** 2 for y in window) / period
        slope = vxy / vxx

        if output == "forecast":
            intercept = ybar - slope * xbar
            result = intercept + slope * (period + offset)
        elif output == "slope":
            result = slope
        elif output == "rvalue":
            result = vxy / math.sqrt(vxx * vyy) if vyy > 0 else math.nan
        elif output == "rmse":
            if vyy > 0:
                corr = vxy / math.sqrt(vxx * vyy)
                result = math.sqrt(max(0.0, vyy * (1.0 - corr * corr)))
            else:
                result = math.nan
        else:
            raise ValueError(output)
        out.append(result)

    return out


def ref_sar(highs, lows, afs=0.02, maxaf=0.2):
    """Parabolic SAR, independently spelling the shared mintalib/bearta state
    machine. Invalid bars emit null and leave all state untouched."""
    out = []
    ep = sar = af = None
    previous = None
    trend = 0

    for high, low in zip(highs, lows):
        if high is None or low is None or high < low:
            out.append(None)
            continue

        if previous is None:
            previous = (high, low)
            out.append(None)
            continue

        previous_high, previous_low = previous
        previous = (high, low)
        high2 = max(previous_high, high)
        low2 = min(previous_low, low)

        if trend > 0 and low < sar:
            ep, sar, af, trend = low, ep, afs, -1
        elif trend < 0 and high > sar:
            ep, sar, af, trend = high, ep, afs, 1

        out.append(sar)

        if trend == 0:
            if high > previous_high:
                ep, sar, af, trend = high2, low2, afs, 1
            else:
                ep, sar, af, trend = low2, high2, afs, -1
        else:
            assert ep is not None and sar is not None and af is not None
            sar += af * (ep - sar)
            if trend > 0:
                sar = min(sar, low2)
                if high > ep:
                    ep = high
                    af += afs
            else:
                sar = max(sar, high2)
                if low < ep:
                    ep = low
                    af += afs

        if maxaf and af > maxaf:
            af = maxaf

    return out


def ref_streak(values):
    """Count consecutive true values; false and null both reset to zero."""
    out = []
    count = 0
    for value in values:
        count = count + 1 if value is True else 0
        out.append(count)
    return out
