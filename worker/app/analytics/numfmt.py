import math


def num(x, digits: int = 10):
    """JSON-safe float (None for NaN/inf)."""
    if x is None:
        return None
    x = float(x)
    return None if (math.isnan(x) or math.isinf(x)) else round(x, digits)


def fmt(v, cur: str | None = None) -> str:
    if v is None:
        return "–"
    a = abs(v)
    s = f"{v:,.0f}" if (a >= 1000 or float(v).is_integer()) else f"{v:,.2f}"
    return f"{s} {cur}" if cur else s


def pct(x, signed: bool = False) -> str:
    if x is None:
        return "–"
    s = f"{x * 100:+.0f}%" if signed else f"{x * 100:.0f}%"
    return "0%" if s in ("+0%", "-0%") else s
