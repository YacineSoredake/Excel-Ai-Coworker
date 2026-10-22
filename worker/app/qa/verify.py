"""Independent re-computation of a query result in plain Python (no pandas), as the analytics layer does for facts.

An answer is shown only if this second computation agrees with the first.
"""
import math
import statistics

import pandas as pd

from ..analytics.verify import close, isnull
from .execute import MIN_GROUP

AGG = {"sum": math.fsum, "mean": lambda x: math.fsum(x) / len(x), "median": statistics.median, "min": min, "max": max,
       "count": len}


def _mask(plan: dict, cols: dict, n: int) -> list:
    keep = []
    for i in range(n):
        ok = True
        for f in plan["filters"]:
            v = cols[f["col"]][i]
            if "values" in f:
                ok = not isnull(v) and str(v).strip() in f["values"]
            else:
                ok = not isnull(v)
                if ok and f["from"]:
                    ok = v >= pd.Timestamp(f["from"])
                if ok and f["to"]:
                    ok = v < pd.Timestamp(f["to"]) + pd.Timedelta(1, unit="D")
            if not ok:
                break
        keep.append(ok)
    return keep


def _pkey(ts, grain: str) -> str:
    if grain == "M":
        return f"{ts.year:04d}-{ts.month:02d}"
    if grain == "D":
        return f"{ts.year:04d}-{ts.month:02d}-{ts.day:02d}"
    return str(pd.Period(ts, freq=grain))


def _flags(keys: list, lo, hi, grain: str) -> dict:
    out = {}
    for k in keys:
        p = pd.Period(k, freq=grain)
        s, e = p.start_time.normalize(), p.end_time.normalize()
        length = (e - s).days + 1
        ok = True
        if k == keys[0] and (lo - s).days > 0.2 * length:
            ok = False
        if k == keys[-1] and (e - hi).days > 0.2 * length:
            ok = False
        out[k] = ok
    return out


def _series(plan: dict, cols: dict, keep: list, agg: str) -> dict:
    tcol, m, grain = plan["time"], plan["measure"], plan["grain"]
    ts_all = [t for t in cols[tcol] if not isnull(t)]
    lo, hi = min(ts_all).normalize(), max(ts_all).normalize()
    for f in plan["filters"]:
        if f["col"] == tcol:
            if f.get("from"):
                lo = max(lo, pd.Timestamp(f["from"]))
            if f.get("to"):
                hi = min(hi, pd.Timestamp(f["to"]))
    acc: dict = {}
    for i, ok in enumerate(keep):
        t = cols[tcol][i]
        if not ok or isnull(t):
            continue
        a = acc.setdefault(_pkey(t, grain), [0, []])
        a[0] += 1
        if m is not None and not isnull(cols[m][i]):
            a[1].append(float(cols[m][i]))
    ks = sorted(acc)
    # fill gaps between first and last period
    full = [str(p) for p in pd.period_range(ks[0], ks[-1], freq=grain)] if ks else []
    flags = _flags(full, lo, hi, grain) if full else {}
    out = {}
    for k in full:
        n, xs = acc.get(k, [0, []])
        if agg == "count":
            v = float(n)
        elif n == 0:
            v = 0.0 if agg == "sum" else None
        elif not xs:
            v = None
        else:
            v = math.fsum(xs) if agg == "sum" else math.fsum(xs) / len(xs)
        out[k] = {"value": v, "rows": n, "complete": flags[k]}
    return out


def verify(plan: dict, res, cols: dict) -> bool:
    try:
        return _verify(plan, res, cols)
    except Exception:
        return False


def _verify(plan: dict, res, cols: dict) -> bool:
    n = len(cols["row_number"])
    keep = _mask(plan, cols, n)
    if sum(keep) != res.rows_after_filters:
        return False
    op, m, agg, d = plan["op"], plan["measure"], plan["agg"], res.data

    if op == "agg":
        xs = [float(cols[m][i]) for i in range(n) if keep[i] and not isnull(cols[m][i])] if m else None
        if m is None:
            return d["value"] == sum(keep) and res.rows_used == sum(keep)
        if not xs:
            return d["value"] is None and d["count"] == 0
        return d["count"] == len(xs) and close(AGG[agg](xs), d["value"])

    if op == "group":
        acc: dict = {}
        for i in range(n):
            l = cols[plan["dim"]][i]
            if not keep[i] or isnull(l):
                continue
            if m is not None and isnull(cols[m][i]):
                continue
            acc.setdefault(str(l).strip(), []).append(float(cols[m][i]) if m else 1.0)
        vals = {}
        for l, xs in acc.items():
            if agg in ("mean", "median") and len(xs) < MIN_GROUP:
                continue
            vals[l] = (AGG[agg](xs) if m else float(len(xs)), len(xs))
        if len(vals) != d["n_groups"]:
            return False
        ranked = sorted(vals.items(), key=lambda kv: ((kv[1][0] if plan["order"] == "asc" else -kv[1][0]), kv[0]))
        shown = [g for g in d["groups"] if not g.get("muted")]
        for g, (l, (v, k)) in zip(shown, ranked):
            if g["label"] != l or not close(v, g["value"]) or g["rows"] != k:
                return False
        if len(shown) != min(plan["limit"], len(ranked)):
            return False
        if agg in ("sum", "count"):
            return close(math.fsum(v for v, _ in vals.values()), d["total"])
        return True

    if op == "top_rows":
        rows = [(float(cols[m][i]), int(cols["row_number"][i])) for i in range(n) if keep[i] and not isnull(cols[m][i])]
        rows.sort(key=lambda r: ((r[0] if plan["order"] == "asc" else -r[0]), r[1]))
        top = rows[: plan["limit"]]
        got = [r[0] for r in d["rows"]]
        return d["total_rows"] == len(rows) and got == [r[1] for r in top] and all(close(r[-1], t[0]) for r, t in zip(d["rows"], top))

    series_agg = "sum" if op == "contribution" else agg
    ser = _series(plan, cols, keep, series_agg)
    if op == "series":
        for it in d["periods"]:
            s = ser.get(it["period"])
            if not s or s["rows"] != it["rows"] or s["complete"] != it["complete"]:
                return False
            if (s["value"] is None) != (it["value"] is None) or (s["value"] is not None and not close(s["value"], it["value"])):
                return False
        return len(ser) == len(d["periods"])

    a, b = (d["a"], d["b"])
    ap, bp = (a["period"], b["period"]) if op == "contribution" else (a["period"], b["period"])
    if op == "compare":
        if not (close(ser[ap]["value"], a["value"]) and close(ser[bp]["value"], b["value"])):
            return False
        return close(ser[bp]["value"] - ser[ap]["value"], d["change_abs"])

    # contribution: per-label sums for the two periods
    acc2: dict = {}
    for i in range(n):
        l, t, v = cols[plan["dim"]][i], cols[plan["time"]][i], cols[m][i]
        if not keep[i] or isnull(l) or isnull(t) or isnull(v):
            continue
        k = _pkey(t, plan["grain"])
        if k in (ap, bp):
            acc2.setdefault(str(l).strip(), {ap: [], bp: []})[k].append(float(v))
    entries = sorted(((l, math.fsum(x[ap]), math.fsum(x[bp])) for l, x in acc2.items()), key=lambda e: (-abs(e[2] - e[1]), e[0]))
    ta, tb = math.fsum(e[1] for e in entries), math.fsum(e[2] for e in entries)
    if not (close(ta, a["total"]) and close(tb, b["total"]) and close(tb - ta, d["change"])):
        return False
    for g, (l, va, vb) in zip(d["groups"], entries):
        if g["label"] != l or not close(va, g["a"]) or not close(vb, g["b"]) or not close(vb - va, g["delta"]):
            return False
    return len(d["groups"]) == min(plan["limit"], len(entries))
