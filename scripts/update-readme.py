"""Regenerate the indicator catalog in README.md."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
INDICATORS_INIT = ROOT / "python" / "bartons" / "indicators" / "__init__.py"
START = "<!-- indicators:start -->"
END = "<!-- indicators:end -->"

INDICATORS = {
    "EMA": ("EMA(period)", "Exponential moving average"),
    "SMA": ("SMA(period)", "Simple moving average"),
    "RMA": ("RMA(period)", "Wilder's running moving average"),
    "WMA": ("WMA(period)", "Weighted moving average"),
    "RSI": ("RSI(period)", "Wilder's relative strength index"),
    "TRANGE": ("TRANGE()", "True range"),
    "ATR": ("ATR(period)", "Average true range"),
    "MACD": (
        "MACD(fast=12, slow=26, signal=9)",
        "MACD, signal and histogram expressions",
    ),
    "MAD": ("MAD(period=20)", "Rolling mean absolute deviation"),
    "AVGPRICE": (
        "AVGPRICE()",
        "Average price, `(open + high + low + close) / 4`",
    ),
    "MEDPRICE": ("MEDPRICE()", "Median price, `(high + low) / 2`"),
    "TYPPRICE": ("TYPPRICE()", "Typical price, `(high + low + close) / 3`"),
    "WCLPRICE": (
        "WCLPRICE()",
        "Weighted close price, `(high + low + 2 * close) / 4`",
    ),
    "CCI": ("CCI(period=20)", "Commodity Channel Index"),
    "KER": ("KER(period=10)", "Kaufman efficiency ratio"),
    "KAMA": (
        "KAMA(period=10, fastn=2, slown=30)",
        "Kaufman adaptive moving average",
    ),
    "SAR": ("SAR(afs=0.02, maxaf=0.2)", "Parabolic Stop and Reverse"),
    "STREAK": ("STREAK(src)", "Consecutive true count"),
}


def exported_indicators() -> list[str]:
    module = ast.parse(INDICATORS_INIT.read_text())
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, list) or not all(
                isinstance(name, str) for name in value
            ):
                break
            return value
    raise RuntimeError(f"could not read __all__ from {INDICATORS_INIT}")


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
