"""Phase D — profile: distributions, cardinality, outliers (report §4.2)."""
import math
from collections import Counter

import numpy as np
import pandas as pd

from .columns import ColumnResult


def _f(x):
    if x is None:
        return None
    x = float(x)
    return None if (math.isnan(x) or math.isinf(x)) else round(x, 6)


def basic_counts(col: ColumnResult) -> None:
    valid = [v for v in col.values if v is not None]
    col.distinct_count = len(set(valid))
    col.uniqueness = round(col.distinct_count / len(valid), 4) if valid else 0.0
    if col.base_type in ("text", "identifier") and valid:
        col.avg_len = float(np.mean([len(str(v)) for v in valid]))


def granularity(dates) -> str | None:
    days = sorted({d.date() for d in dates})
    if len(days) < 3:
        return None
    gaps = np.diff([d.toordinal() for d in days])
    med = float(np.median(gaps))
    if med <= 1.5:
        return "daily"
    if med <= 8:
        return "weekly"
    if med <= 35:
        return "monthly"
    if med <= 100:
        return "quarterly"
    return "yearly"


def detailed_stats(col: ColumnResult) -> None:
    valid = [v for v in col.values if v is not None]
    s: dict = {"valid_count": len(valid)}
    t = col.base_type
    if not valid:
        col.stats = s
        return
    if t in ("integer", "decimal", "currency", "percentage"):
        a = np.array(valid, dtype=float)
        q = np.percentile(a, [5, 25, 50, 75, 95])
        s.update(min=_f(a.min()), max=_f(a.max()), mean=_f(a.mean()), median=_f(q[2]),
                 std=_f(a.std(ddof=1)) if len(a) > 1 else None, sum=_f(a.sum()),
                 p05=_f(q[0]), p25=_f(q[1]), p75=_f(q[3]), p95=_f(q[4]),
                 zeros=int((a == 0).sum()), negatives=int((a < 0).sum()))
        if col.distinct_count > 1:
            counts, edges = np.histogram(a, bins=min(10, col.distinct_count))
            s["histogram"] = {"edges": [_f(e) for e in edges], "counts": [int(c) for c in counts]}
        if col.distinct_count <= 12:
            s["top_values"] = [{"value": _f(k), "count": c} for k, c in Counter(valid).most_common(12)]
        col.outliers = outlier_info(a, [r for r, v in zip(col.rows, col.values) if v is not None])
    elif t in ("date", "datetime"):
        s.update(min=min(valid).isoformat(), max=max(valid).isoformat(),
                 span_days=(max(valid) - min(valid)).days, distinct_days=len({d.date() for d in valid}),
                 granularity=granularity(valid), has_time=t == "datetime")
    elif t == "boolean":
        s.update(true_count=sum(1 for v in valid if v), false_count=sum(1 for v in valid if not v))
    else:
        lens = [len(str(v)) for v in valid]
        s.update(avg_len=round(float(np.mean(lens)), 1), max_len=max(lens),
                 top_values=[{"value": str(k)[:60], "count": c} for k, c in Counter(map(str, valid)).most_common(10)])
        low = Counter(str(v).strip().casefold() for v in valid)
        s["distinct_normalized"] = len(low)
    col.stats = s


def outlier_info(a: np.ndarray, rows: list) -> dict | None:
    """Flag extreme values (3×IQR fences). Heavy right tails (money) are judged on a log scale."""
    if len(a) < 20 or len(set(a.tolist())) < 10:
        return None
    method, x = "iqr", a
    if (a > 0).all() and abs(float(pd.Series(a).skew())) > 1:
        method, x = "iqr_log10", np.log10(a)
    q1, q3 = np.percentile(x, [25, 75])
    iqr = q3 - q1
    if iqr <= 0:
        return None
    lo3, hi3, lo15, hi15 = q1 - 3 * iqr, q3 + 3 * iqr, q1 - 1.5 * iqr, q3 + 1.5 * iqr
    ext = (x < lo3) | (x > hi3)
    mild = ((x < lo15) | (x > hi15)) & ~ext
    back = (lambda v: float(10 ** v)) if method == "iqr_log10" else float
    dev = np.abs(x - np.median(x))
    idx = [i for i in np.argsort(-dev) if ext[i]][:5]
    return {
        "method": method, "count_extreme": int(ext.sum()), "count_mild": int(mild.sum()),
        "fences_extreme": [_f(back(lo3)), _f(back(hi3))],
        "sample": [{"row": int(rows[i]), "value": _f(a[i])} for i in idx],
        "extreme_rows": [int(rows[i]) for i in np.flatnonzero(ext)[:200]],
    }
