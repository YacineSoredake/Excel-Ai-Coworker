"""Time bucketing with an honest notion of 'complete period' (an unfinished month is not a decline)."""
import pandas as pd


def choose_grain(min_d: pd.Timestamp, max_d: pd.Timestamp) -> str | None:
    """Pick the bucket that gives a readable series (roughly 4-40 periods)."""
    span = (max_d - min_d).days
    if span < 7:
        return None
    if span < 21:
        return "D"
    if span < 120:
        return "W"
    months = span / 30.44
    if months <= 36:
        return "M"
    if months <= 120:
        return "Q"
    return "Y"


GRAIN_NAME = {"D": "day", "W": "week", "M": "month", "Q": "quarter", "Y": "year"}


def _is_complete(p: pd.Period, first: pd.Period, last: pd.Period, min_d, max_d) -> bool:
    """A period at the edge of the data is partial when the data stops/starts well inside it (20% tolerance)."""
    start, end = p.start_time.normalize(), p.end_time.normalize()
    length = (end - start).days + 1
    if p == first and (min_d.normalize() - start).days > 0.2 * length:
        return False
    if p == last and (end - max_d.normalize()).days > 0.2 * length:
        return False
    return True


def build_series(df: pd.DataFrame, time: str, grain: str, value: str | None, agg: str, min_d, max_d) -> list[dict]:
    """agg: sum | mean | count. Missing periods inside the range become explicit empty items."""
    d = df.dropna(subset=[time])
    per = d[time].dt.to_period(grain)
    first, last = per.min(), per.max()
    rows = per.groupby(per).size()
    if agg == "count":
        vals = rows
    else:
        dv = d.assign(_p=per).dropna(subset=[value]).groupby("_p")[value]
        vals = dv.sum() if agg == "sum" else dv.mean()
    items = []
    for p in pd.period_range(first, last, freq=grain):
        n = int(rows.get(p, 0))
        v = vals.get(p)
        if v is None or pd.isna(v):
            v = 0.0 if (n == 0 and agg in ("sum", "count")) else None
        items.append({"period": str(p), "value": None if v is None else float(v), "rows": n,
                      "complete": _is_complete(p, first, last, min_d, max_d), "empty": n == 0})
    return items
