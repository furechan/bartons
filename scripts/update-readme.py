"""Regenerate the indicator catalog in README.md."""

from indicator_exports import ROOT, indicator_exports


README = ROOT / "README.md"
START = "<!-- indicators:start -->"
END = "<!-- indicators:end -->"

INDICATORS = {
    "ADL": ("ADL()", "Accumulation/Distribution Line"),
    "ADOSC": ("ADOSC(fast=3, slow=10)", "Chaikin A/D Oscillator"),
    "AROON": ("AROON(period=14)", "Aroon Down and Up"),
    "AROONOSC": ("AROONOSC(period=14)", "Aroon Oscillator"),
    "EMA": ("EMA(period)", "Exponential moving average"),
    "DEMA": ("DEMA(period)", "Double exponential moving average"),
    "TEMA": ("TEMA(period=20)", "Triple exponential moving average"),
    "HMA": ("HMA(period)", "Hull moving average"),
    "ZLEMA": ("ZLEMA(period)", "Zero-lag exponential moving average"),
    "ALMA": (
        "ALMA(period=9, offset=0.85, sigma=6.0)",
        "Arnaud Legoux moving average",
    ),
    "APO": ("APO(fast=12, slow=26, matype=\"ema\")", "Absolute Price Oscillator"),
    "SMA": ("SMA(period)", "Simple moving average"),
    "MA": ("MA(period=30, matype=\"sma\")", "Generic moving-average dispatcher"),
    "RMA": ("RMA(period)", "Wilder's running moving average"),
    "ROC": ("ROC(period=1)", "Rate of Change (%)"),
    "ROCP": ("ROCP(period=1)", "Rate of Change as an unscaled fraction"),
    "LROC": ("LROC(period=1)", "Logarithmic Rate of Change"),
    "WMA": ("WMA(period)", "Weighted moving average"),
    "VWMA": ("VWMA(period=20)", "Volume-weighted moving average"),
    "WILLR": ("WILLR(period=14)", "Williams %R"),
    "RSI": ("RSI(period)", "Wilder's relative strength index"),
    "TRANGE": ("TRANGE()", "True range"),
    "TRIX": ("TRIX(period=30)", "Triple-smoothed EMA rate of change (%)"),
    "ULTOSC": (
        "ULTOSC(fast=7, medium=14, slow=28)",
        "Ultimate Oscillator",
    ),
    "ATR": ("ATR(period)", "Average true range"),
    "NATR": ("NATR(period=14)", "Normalized Average True Range (%)"),
    "BBANDS": (
        "BBANDS(period=20, nbdev=2.0)",
        "Bollinger upper, middle and lower bands",
    ),
    "BBP": ("BBP(period=20, nbdev=2.0)", "Bollinger Percent B ratio"),
    "BBW": ("BBW(period=20, nbdev=2.0)", "Bollinger BandWidth ratio"),
    "BOP": ("BOP()", "Unsmoothed Balance of Power"),
    "MACD": (
        "MACD(fast=12, slow=26, signal=9)",
        "MACD, signal and histogram expressions",
    ),
    "MAD": ("MAD(period=20)", "Rolling mean absolute deviation"),
    "MOM": ("MOM(period=1)", "Momentum"),
    "AVGPRICE": (
        "AVGPRICE()",
        "Average price, `(open + high + low + close) / 4`",
    ),
    "MEDPRICE": ("MEDPRICE()", "Median price, `(high + low) / 2`"),
    "MIDPRICE": (
        "MIDPRICE(period=14)",
        "Midpoint of the rolling highest high and lowest low",
    ),
    "TYPPRICE": ("TYPPRICE()", "Typical price, `(high + low + close) / 3`"),
    "WCLPRICE": (
        "WCLPRICE()",
        "Weighted close price, `(high + low + 2 * close) / 4`",
    ),
    "CCI": ("CCI(period=20)", "Commodity Channel Index"),
    "CLAG": ("CLAG(period=1)", "Confirmation lag for discrete states"),
    "CMF": ("CMF(period=20)", "Chaikin Money Flow"),
    "CMO": ("CMO(period=14)", "Rolling-window Chande Momentum Oscillator"),
    "KER": ("KER(period=10)", "Kaufman efficiency ratio"),
    "KAMA": (
        "KAMA(period=10, fastn=2, slown=30)",
        "Kaufman adaptive moving average",
    ),
    "KELTNER": (
        "KELTNER(period=20, nbatr=2.0)",
        "Keltner upper, middle and lower channels",
    ),
    "SAR": ("SAR(afs=0.02, maxaf=0.2)", "Parabolic Stop and Reverse"),
    "STOCH": (
        "STOCH(period=14, fastn=3, slown=3)",
        "Slow stochastic oscillator, `%K` and `%D`",
    ),
    "STOCHRSI": (
        "STOCHRSI(period=14, fastn=3, slown=3)",
        "Stochastic RSI, fast K and fast D",
    ),
    "STREAK": ("STREAK(src)", "Consecutive true count"),
    "STEP": ("STEP(threshold=1.0)", "Threshold-limited step function"),
    "SUPERTREND": (
        "SUPERTREND(period=10, multiplier=3.0)",
        "Supertrend line and bullish/bearish direction",
    ),
    "LINREG": ("LINREG(period=20, offset=0)", "Rolling linear-regression forecast"),
    "LINREG_SLOPE": ("LINREG_SLOPE(period=20)", "Rolling linear-regression slope"),
    "LINREG_RVALUE": ("LINREG_RVALUE(period=20)", "Rolling linear-regression r-value"),
    "LINREG_RMSE": ("LINREG_RMSE(period=20)", "Rolling linear-regression RMSE"),
    "QUADREG": ("QUADREG(period=20, offset=0)", "Rolling quadratic-regression forecast"),
    "QUADREG_CURVE": ("QUADREG_CURVE(period=20)", "Rolling quadratic coefficient"),
    "QUADREG_SLOPE": ("QUADREG_SLOPE(period=20, offset=0)", "Rolling quadratic-regression slope"),
    "QUADREG_RVALUE": ("QUADREG_RVALUE(period=20)", "Rolling quadratic partial r-value"),
    "QUADREG_RMSE": ("QUADREG_RMSE(period=20)", "Rolling quadratic-regression RMSE"),
    "MFI": ("MFI(period=14)", "Money Flow Index"),
    "OBV": ("OBV()", "On-Balance Volume"),
    "PPO": ("PPO(fast=12, slow=26, matype=\"ema\")", "Price Percentage Oscillator (%)"),
    "DMI": ("DMI(period=14)", "ADX, plus DI and minus DI expressions"),
    "ADX": ("ADX(period=14)", "Average Directional Index"),
    "PDI": ("PDI(period=14)", "Positive Directional Indicator"),
    "MDI": ("MDI(period=14)", "Negative Directional Indicator"),
    "DONCHIAN": (
        "DONCHIAN(period=20)",
        "Donchian upper, middle and lower channels",
    ),
}


def exported_indicators() -> list[str]:
    return sorted(name for _, names in indicator_exports() for name in names)


def render(names: list[str]) -> str:
    missing = set(names) - INDICATORS.keys()
    stale = INDICATORS.keys() - set(names)
    if missing or stale:
        raise RuntimeError(
            f"indicator metadata mismatch: missing={sorted(missing)}, stale={sorted(stale)}"
        )

    rows = ["| | |", "|---|---|"]
    rows.extend(f"| `{INDICATORS[name][0]}` | {INDICATORS[name][1]} |" for name in names)
    return "\n".join(rows)


def main() -> None:
    contents = README.read_text()
    if contents.count(START) != 1 or contents.count(END) != 1:
        raise RuntimeError("README indicator markers must each occur exactly once")

    before, remainder = contents.split(START)
    _, after = remainder.split(END)
    updated = f"{before}{START}\n{render(exported_indicators())}\n{END}{after}"
    README.write_text(updated)


if __name__ == "__main__":
    main()
