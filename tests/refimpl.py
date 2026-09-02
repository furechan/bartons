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


def ref_dema(xs, period):
    """DEMA composed independently from two EMA passes."""
    first = ref_ema(xs, period)
    second = ref_ema(first, period)
    return [
        None if a is None or b is None else 2.0 * a - b
        for a, b in zip(first, second)
    ]


def ref_tema(xs, period):
    """TEMA composed independently from three EMA passes."""
    first = ref_ema(xs, period)
    second = ref_ema(first, period)
    third = ref_ema(second, period)
    return [
        None if a is None or b is None or c is None else 3.0 * a - 3.0 * b + c
        for a, b, c in zip(first, second, third)
    ]


def ref_trix(xs, period):
    """TRIX from three independent EMA passes, scaled to percentage points."""
    first = ref_ema(xs, period)
    second = ref_ema(first, period)
    third = ref_ema(second, period)
    return [None if value is None else 100.0 * value for value in ref_roc(third, 1)]


def ref_zlema(xs, period):
    """ZLEMA from an independently materialized de-lagged source and EMA."""
    lag = (period - 1) // 2
    window = []
    adjusted = []
    for value in xs:
        if value is None:
            window = []
            adjusted.append(None)
            continue
        if lag == 0:
            adjusted.append(value)
            continue
        if len(window) < lag:
            window.append(value)
            adjusted.append(None)
            continue
        delayed = window.pop(0)
        window.append(value)
        adjusted.append(2.0 * value - delayed)
    return ref_ema(adjusted, period)


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


def ref_bbands(xs, period=20, nbdev=2.0):
    """Bollinger Bands using population standard deviation per full window."""
    upper = []
    middle = []
    lower = []
    window = []
    for value in xs:
        if value is None:
            window = []
        else:
            window.append(value)
            if len(window) > period:
                window.pop(0)

        if len(window) < period:
            upper.append(None)
            middle.append(None)
            lower.append(None)
            continue

        mean = sum(window) / period
        deviation = math.sqrt(
            sum((item - mean) ** 2 for item in window) / period
        )
        middle.append(mean)
        upper.append(mean + nbdev * deviation)
        lower.append(mean - nbdev * deviation)
    return upper, middle, lower


def ref_stoch(highs, lows, closes, period=14, fastn=3, slown=3):
    """Slow stochastic oscillator composed from direct rolling windows."""

    def rolling(values, window_size, aggregate):
        result = []
        window = []
        for value in values:
            if value is None:
                window = []
            else:
                window.append(value)
                if len(window) > window_size:
                    window.pop(0)
            result.append(
                aggregate(window) if len(window) == window_size else None
            )
        return result

    lowest = rolling(lows, period, min)
    highest = rolling(highs, period, max)
    fastk = [
        None
        if close is None or low is None or high is None
        else 100.0 * (close - low) / (high - low)
        if high != low
        else float("nan")
        for close, low, high in zip(closes, lowest, highest)
    ]
    slowk = rolling(fastk, fastn, lambda values: sum(values) / fastn)
    slowd = rolling(slowk, slown, lambda values: sum(values) / slown)
    return slowk, slowd


def ref_ultosc(highs, lows, closes, fast=7, medium=14, slow=28):
    """Ultimate Oscillator from independently materialized rolling sums."""
    pressure = []
    ranges = []
    for index, (high, low, close) in enumerate(zip(highs, lows, closes)):
        previous_close = closes[index - 1] if index else None
        if high is None or low is None or close is None or previous_close is None:
            pressure.append(None)
            ranges.append(None)
            continue
        pressure.append(close - min(low, previous_close))
        ranges.append(max(high, previous_close) - min(low, previous_close))

    def ratio(period):
        result = []
        for index in range(len(pressure)):
            window_pressure = pressure[index - period + 1 : index + 1]
            window_ranges = ranges[index - period + 1 : index + 1]
            if (
                len(window_pressure) < period
                or any(value is None for value in window_pressure)
                or any(value is None for value in window_ranges)
            ):
                result.append(None)
                continue
            denominator = sum(value for value in window_ranges if value is not None)
            numerator = sum(value for value in window_pressure if value is not None)
            result.append(
                numerator / denominator
                if denominator != 0.0
                else float("nan")
            )
        return result

    fast_values = ratio(fast)
    medium_values = ratio(medium)
    slow_values = ratio(slow)
    return [
        None
        if fast_value is None or medium_value is None or slow_value is None
        else 100.0 * (4.0 * fast_value + 2.0 * medium_value + slow_value) / 7.0
        for fast_value, medium_value, slow_value in zip(
            fast_values, medium_values, slow_values
        )
    ]


def ref_stochrsi(xs, period=14, fastn=3, slown=3):
    """Stochastic RSI composed from the independent RSI and rolling oracles."""

    def rolling(values, window_size, aggregate):
        result = []
        window = []
        for value in values:
            if value is None:
                window = []
            else:
                window.append(value)
                if len(window) > window_size:
                    window.pop(0)
            result.append(aggregate(window) if len(window) == window_size else None)
        return result

    rsi = ref_rsi(xs, period)
    lowest = rolling(rsi, period, min)
    highest = rolling(rsi, period, max)
    raw = [
        None
        if value is None or low is None or high is None
        else 100.0 * (value - low) / (high - low)
        if high != low
        else float("nan")
        for value, low, high in zip(rsi, lowest, highest)
    ]
    fastk = rolling(raw, fastn, lambda values: sum(values) / fastn)
    fastd = rolling(fastk, slown, lambda values: sum(values) / slown)
    return fastk, fastd


def ref_roc(xs, period=1):
    """Percentage change from the value exactly ``period`` rows earlier."""
    result = []
    for index, value in enumerate(xs):
        previous = xs[index - period] if index >= period else None
        if value is None or previous is None:
            result.append(None)
        elif previous == 0:
            result.append(float("nan") if value == 0 else math.copysign(float("inf"), value))
        else:
            result.append(value / previous - 1.0)
    return result


def ref_cmo(xs, period=14):
    """Original CMO from direct rolling sums of gains and losses."""
    changes = [
        None if index == 0 or value is None or xs[index - 1] is None
        else value - xs[index - 1]
        for index, value in enumerate(xs)
    ]
    result = []
    for index in range(len(changes)):
        window = changes[index - period + 1 : index + 1]
        if len(window) < period or any(value is None for value in window):
            result.append(None)
            continue
        gains = sum(max(value, 0.0) for value in window if value is not None)
        losses = sum(max(-value, 0.0) for value in window if value is not None)
        total = gains + losses
        result.append(0.0 if total == 0.0 else 100.0 * (gains - losses) / total)
    return result


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


def ref_supertrend(highs, lows, closes, period=10, multiplier=3.0):
    """Supertrend from independently materialized ATR and finalized bands."""
    atrs = ref_atr(highs, lows, closes, period)
    lines = []
    directions = []
    upper = None
    lower = None
    direction = None
    previous_close = None

    for high, low, close, atr in zip(highs, lows, closes, atrs):
        if high is None or low is None or close is None or atr is None:
            lines.append(None)
            directions.append(None)
            previous_close = close
            continue

        midpoint = (high + low) / 2.0
        basic_upper = midpoint + multiplier * atr
        basic_lower = midpoint - multiplier * atr
        if upper is None or previous_close is None or basic_upper < upper or previous_close > upper:
            upper = basic_upper
        if lower is None or previous_close is None or basic_lower > lower or previous_close < lower:
            lower = basic_lower

        if direction is None:
            direction = -1
        elif direction == -1 and close > upper:
            direction = 1
        elif direction == 1 and close < lower:
            direction = -1

        lines.append(lower if direction == 1 else upper)
        directions.append(direction)
        previous_close = close

    return lines, directions


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


def ref_alma(xs, period=9, offset=0.85, sigma=6.0):
    """ALMA recomputed directly from one pre-normalized Gaussian window."""
    center = offset * (period - 1)
    width = period / sigma
    weights = [
        math.exp(-((index - center) ** 2) / (2.0 * width * width))
        for index in range(period)
    ]
    total = sum(weights)
    weights = [weight / total for weight in weights]

    out = []
    window = []
    for value in xs:
        if value is None:
            window = []
            out.append(None)
            continue
        window.append(value)
        if len(window) > period:
            window.pop(0)
        out.append(
            sum(value * weight for value, weight in zip(window, weights))
            if len(window) == period
            else None
        )
    return out


def ref_hma(xs, period):
    """HMA composed independently from its three WMA passes."""
    half = ref_wma(xs, period // 2)
    full = ref_wma(xs, period)
    combined = [
        None if a is None or b is None else 2.0 * a - b
        for a, b in zip(half, full)
    ]
    return ref_wma(combined, math.isqrt(period))


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


def ref_dmi(highs, lows, closes, period):
    """DMI composed independently from directional movement, ATR, and RMA."""
    plus_dm = []
    minus_dm = []
    previous = None
    for high, low in zip(highs, lows):
        current = None if high is None or low is None else (high, low)
        if current is None or previous is None:
            plus_dm.append(None)
            minus_dm.append(None)
        else:
            up = current[0] - previous[0]
            down = previous[1] - current[1]
            plus_dm.append(up if up > down and up > 0.0 else 0.0)
            minus_dm.append(down if down > up and down > 0.0 else 0.0)
        previous = current

    atr = ref_atr(highs, lows, closes, period)
    plus_dm = ref_rma(plus_dm, period)
    minus_dm = ref_rma(minus_dm, period)
    pdi = []
    mdi = []
    for tr, positive, negative in zip(atr, plus_dm, minus_dm):
        if tr is None or positive is None or negative is None:
            pdi.append(None)
            mdi.append(None)
        elif tr == 0.0:
            pdi.append(0.0)
            mdi.append(0.0)
        else:
            pdi.append(100.0 * positive / tr)
            mdi.append(100.0 * negative / tr)

    dx = []
    for positive, negative in zip(pdi, mdi):
        if positive is None or negative is None:
            dx.append(None)
        else:
            total = positive + negative
            dx.append(0.0 if total == 0.0 else 100.0 * abs(positive - negative) / total)
    return ref_rma(dx, period), pdi, mdi


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


def ref_quadreg(xs, period=20, output="forecast", offset=0):
    """Rolling quadratic regression recomputed directly on a centered grid.

    Nulls reset the window. ``curve`` is the quadratic coefficient, ``slope``
    is the derivative at the projected endpoint, and ``rvalue`` is the partial
    correlation of the quadratic term after removing the linear term.
    """
    window = []
    out = []
    half = (period - 1.0) / 2.0
    us = [x - half for x in range(period)]
    su2 = sum(u * u for u in us)
    su4 = sum(u**4 for u in us)
    vxx = su2 / period
    vuu = su4 / period - (su2 / period) ** 2

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

        sz = sum(window)
        szz = sum(z * z for z in window)
        suz = sum(u * z for u, z in zip(us, window))
        su2z = sum(u * u * z for u, z in zip(us, window))
        slope = suz / period / vxx
        szz_r = szz - 2.0 * slope * suz + slope * slope * su2
        vuz = su2z / period - su2 * sz / period / period
        vzz = szz_r / period - sz * sz / period / period
        curve = vuz / vuu
        rvalue = vuz / math.sqrt(vuu * vzz) if vuu * vzz > 0 else math.nan

        if output == "forecast":
            alpha = sz / period - curve * su2 / period
            x_end = half + offset
            result = alpha + slope * x_end + curve * x_end * x_end
        elif output == "curve":
            result = curve
        elif output == "slope":
            result = slope + 2.0 * curve * (half + offset)
        elif output == "rvalue":
            result = rvalue
        elif output == "rmse":
            result = math.sqrt(vzz * max(0.0, 1.0 - rvalue * rvalue))
        else:
            raise ValueError(output)
        out.append(result)

    return out


def ref_mfi(srcs, volumes, period=14):
    """Money Flow Index from directly maintained signed-flow windows."""
    out = []
    window = []
    previous = None

    for src, volume in zip(srcs, volumes):
        if src is None:
            window = []
            previous = None
            out.append(None)
            continue

        prior, previous = previous, src
        if volume is None:
            window = []
            out.append(None)
            continue
        if prior is None:
            out.append(None)
            continue

        raw_flow = src * volume
        flow = raw_flow if src > prior else -raw_flow if src < prior else 0.0
        window.append(flow)
        if len(window) > period:
            window.pop(0)
        if len(window) < period:
            out.append(None)
            continue

        positive = sum(value for value in window if value > 0.0)
        negative = -sum(value for value in window if value < 0.0)
        total = positive + negative
        out.append(100.0 * positive / total if total > 0.0 else math.nan)

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


def ref_step(values, threshold=1.0):
    """Limit each change from the prior output; null and NaN skip state."""
    out = []
    previous = None

    for value in values:
        if value is None:
            out.append(None)
            continue
        if math.isnan(value):
            out.append(math.nan)
            continue

        if previous is None:
            previous = value
            out.append(None)
            continue

        change = value - previous
        if change > threshold:
            previous += threshold
        elif change < -threshold:
            previous -= threshold
        else:
            previous = value
        out.append(previous)

    return out


def ref_clag(values, period=1):
    """Confirm a discrete state after its first value plus ``period`` repeats."""
    out = []
    candidate = confirmed = None
    repeats = 0

    for value in values:
        if value is None:
            out.append(None)
            continue
        if math.isnan(value):
            out.append(math.nan)
            continue

        if value == candidate:
            repeats += 1
        else:
            candidate = value
            repeats = 0

        if repeats >= period:
            confirmed = value
        out.append(confirmed)

    return out
