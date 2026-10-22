"""Independent re-computation (report §6.1 'validates the facts', §14 phase H).

Everything here is written as plain Python loops over the cleaned rows, deliberately not reusing the
pandas code that produced the facts. A fact is kept only if this second computation agrees with it.
"""
import math
import re
import statistics

import pandas as pd

from .model import Fact


def isnull(x) -> bool:
    return x is None or x is pd.NA or x is pd.NaT or (isinstance(x, float) and math.isnan(x))


def close(a, b) -> bool:
    return a is not None and b is not None and math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-6)


class VCtx:
    def __init__(self, frames: dict):
        self.cols = {i: {c: df[c].tolist() for c in df.columns} for i, df in frames.items()}
        self._pk, self._ser = {}, {}

    def col(self, ti, name):
        return self.cols[ti][name]

    def pkeys(self, ti, time, grain):
        k = (ti, time, grain)
        if k not in self._pk:
            out = []
            for ts in self.col(ti, time):
                if isnull(ts):
                    out.append(None)
                elif grain == "M":
                    out.append(f"{ts.year:04d}-{ts.month:02d}")
                elif grain == "D":
                    out.append(f"{ts.year:04d}-{ts.month:02d}-{ts.day:02d}")
                else:
                    out.append(str(pd.Period(ts, freq=grain)))
            self._pk[k] = out
        return self._pk[k]

    def series(self, ti, time, grain, measure, agg):
        """{period: (value, rows)} for periods that have rows."""
        k = (ti, time, grain, measure, agg)
        if k in self._ser:
            return self._ser[k]
        keys = self.pkeys(ti, time, grain)
        vals = self.col(ti, measure) if measure else None
        acc: dict = {}
        for i, p in enumerate(keys):
            if p is None:
                continue
            a = acc.setdefault(p, [0, []])
            a[0] += 1
            if vals is not None and not isnull(vals[i]):
                a[1].append(float(vals[i]))
        res = {}
        for p, (n, xs) in acc.items():
            if agg == "count":
                res[p] = (float(n), n)
            elif not xs:
                res[p] = (None, n)
            else:
                res[p] = (math.fsum(xs) if agg == "sum" else math.fsum(xs) / len(xs), n)
        self._ser[k] = res
        return res

    def complete_flags(self, ti, time, grain, keys_sorted):
        times = [t for t in self.col(ti, time) if not isnull(t)]
        lo, hi = min(times).normalize(), max(times).normalize()
        first, last = keys_sorted[0], keys_sorted[-1]
        flags = {}
        for k in keys_sorted:
            p = pd.Period(k, freq=grain)
            start, end = p.start_time.normalize(), p.end_time.normalize()
            length = (end - start).days + 1
            ok = True
            if k == first and (lo - start).days > 0.2 * length:
                ok = False
            if k == last and (end - hi).days > 0.2 * length:
                ok = False
            flags[k] = ok
        return flags


def _kendall(v):
    n, s = len(v), 0
    for i in range(n):
        for j in range(i + 1, n):
            d = v[j] - v[i]
            s += (d > 0) - (d < 0)
    return s / (n * (n - 1) / 2) if n > 1 else 0.0


def _ranks(xs):
    n = len(xs)
    order = sorted(range(n), key=lambda i: xs[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def _pearson(a, b):
    n = len(a)
    ma, mb = math.fsum(a) / n, math.fsum(b) / n
    sab = math.fsum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa, sbb = math.fsum((x - ma) ** 2 for x in a), math.fsum((y - mb) ** 2 for y in b)
    return sab / math.sqrt(saa * sbb)


# ------------------------------------------------------------------ per kind

def _kpi(f: Fact, v: VCtx) -> bool:
    s, ti, p = f.spec, f.table_index, f.payload
    if s["measure"] is None:
        return p["value"] == len(v.col(ti, "row_number"))
    xs = [float(x) for x in v.col(ti, s["measure"]) if not isnull(x)]
    if not xs or p["count"] != len(xs):
        return False
    if s["agg"] == "sum":
        return close(math.fsum(xs), p["value"])
    return (close(math.fsum(xs) / len(xs), p["value"]) and close(statistics.median(xs), p["median"])
            and close(min(xs), p["min"]) and close(max(xs), p["max"]))


def _group(f: Fact, v: VCtx) -> bool:
    s, ti, p = f.spec, f.table_index, f.payload
    labs = v.col(ti, s["dim"])
    vals = v.col(ti, s["measure"]) if s["measure"] else None
    acc: dict = {}
    for i, l in enumerate(labs):
        if isnull(l):
            continue
        l = str(l).strip()
        if vals is not None:
            if isnull(vals[i]):
                continue
            acc.setdefault(l, []).append(float(vals[i]))
        else:
            acc.setdefault(l, []).append(1.0)
    agg = s["agg"]
    res = {}
    for l, xs in acc.items():
        if agg == "mean":
            if len(xs) < s["min_group"]:
                continue
            res[l] = (math.fsum(xs) / len(xs), len(xs))
        else:
            res[l] = (math.fsum(xs), len(xs))
    if len(res) != p["n_groups"]:
        return False
    ranked = sorted(res.items(), key=lambda kv: (-kv[1][0], kv[0]))
    for g, (l, (val, n)) in zip(p["groups"], ranked):
        if g["label"] != l or not close(val, g["value"]) or g["rows"] != n:
            return False
    if agg in ("sum", "count"):
        total = math.fsum(x for x, _ in res.values())
        if not close(total, p["total"]):
            return False
        if p["groups"][0]["share"] is not None and not close(ranked[0][1][0] / total, p["groups"][0]["share"]):
            return False
        if p["top1_share"] is not None and p["top3_share"] is not None:
            if not close(math.fsum(x for _, (x, _) in ranked[:3]) / total, p["top3_share"]):
                return False
    return True


def _check_series(p_items, ser, flags) -> bool:
    for it in p_items:
        val, n = ser.get(it["period"], (None, 0))
        if n != it["rows"] or it["complete"] != flags[it["period"]]:
            return False
        if n == 0:
            if it["value"] not in (0.0, None):
                return False
        elif not close(val, it["value"]) if val is not None else it["value"] is not None:
            return False
    return True


def _series_ctx(f: Fact, v: VCtx):
    s, ti = f.spec, f.table_index
    ser = v.series(ti, s["time"], s["grain"], s["measure"], s["agg"])
    keys = [i["period"] for i in f.payload["periods"]] if "periods" in f.payload else None
    return s, ti, ser, keys


def _trend(f: Fact, v: VCtx) -> bool:
    s, ti, ser, keys = _series_ctx(f, v)
    p = f.payload
    flags = v.complete_flags(ti, s["time"], s["grain"], keys)
    if not _check_series(p["periods"], ser, flags):
        return False
    def value_of(k):  # a period with no rows is 0 for sums and counts, unknown for averages
        if k in ser:
            return ser[k][0]
        return 0.0 if s["agg"] in ("sum", "count") else None

    done = [(k, value_of(k)) for k in keys if flags[k] and value_of(k) is not None]
    vals = [x for _, x in done]
    if len(done) != p["complete_periods"] or not close(vals[0], p["first"]["value"]) or not close(vals[-1], p["last"]["value"]):
        return False
    if not close(vals[-1] - vals[0], p["change_abs"]):
        return False
    if p["change_pct"] is not None and not close((vals[-1] - vals[0]) / abs(vals[0]), p["change_pct"]):
        return False
    tau = _kendall(vals)
    rel = (vals[-1] - vals[0]) / abs(vals[0]) if vals[0] else None
    dirn = ("rising" if tau > 0 else "falling") if (len(vals) >= 4 and abs(tau) >= 0.4 and rel is not None and abs(rel) >= 0.1) else "flat_or_mixed"
    return dirn == p["direction"] and p["peak"]["period"] == max(done, key=lambda t: t[1])[0] and p["low"]["period"] == min(done, key=lambda t: t[1])[0]


def _period_change(f: Fact, v: VCtx) -> bool:
    s, ti = f.spec, f.table_index
    ser = v.series(ti, s["time"], s["grain"], s["measure"], s["agg"])
    p = f.payload
    a, b = p["previous"], p["latest"]
    if not (close(ser[a["period"]][0], a["value"]) and close(ser[b["period"]][0], b["value"])):
        return False
    if not close(b["value"] - a["value"], p["change_abs"]):
        return False
    return p["change_pct"] is None or close((b["value"] - a["value"]) / abs(a["value"]), p["change_pct"])


def _swing(f: Fact, v: VCtx) -> bool:
    s, ti = f.spec, f.table_index
    ser = v.series(ti, s["time"], s["grain"], s["measure"], s["agg"])
    p = f.payload
    a, b = p["from"], p["to"]
    if not (close(ser[a["period"]][0], a["value"]) and close(ser[b["period"]][0], b["value"])):
        return False
    return close((b["value"] - a["value"]) / abs(a["value"]), p["change_pct"])


def _anomaly_period(f: Fact, v: VCtx) -> bool:
    s, ti = f.spec, f.table_index
    ser = v.series(ti, s["time"], s["grain"], s["measure"], s["agg"])
    p = f.payload
    for it in p["flagged"]:
        if not close(ser[it["period"]][0], it["value"]):
            return False
    keys = sorted(ser)
    flags = v.complete_flags(ti, s["time"], s["grain"], keys)
    vals = {k: ser[k][0] for k in keys if flags[k] and ser[k][0] is not None and ser[k][1] >= 5}
    med = statistics.median(vals.values())
    mad = statistics.median([abs(x - med) for x in vals.values()])
    if mad == 0 or not close(med, p["median"]):
        return False
    flagged = {k for k, x in vals.items() if abs(0.6745 * (x - med) / mad) >= 3.5}
    return flagged == {it["period"] for it in p["flagged"]}


def _breakdown(f: Fact, v: VCtx) -> bool:
    s, ti, p = f.spec, f.table_index, f.payload
    labs, vals = v.col(ti, s["dim"]), v.col(ti, s["measure"])
    keys = v.pkeys(ti, s["time"], s["grain"])
    want = set(s["periods"])
    acc: dict = {}
    for i, k in enumerate(keys):
        if k in want and not isnull(labs[i]) and not isnull(vals[i]):
            acc.setdefault(str(labs[i]).strip(), {}).setdefault(k, []).append(float(vals[i]))
    named = {x["label"] for x in p["series"] if x["label"] != "Other"}
    for ser in p["series"]:
        if ser["label"] == "Other":
            rest = [math.fsum(acc[l].get(k, [0.0]) and acc[l].get(k, [0.0]) for l in acc if l not in named
                              for _ in [0]) for k in s["periods"]] if False else None
            totals = [math.fsum(math.fsum(acc[l].get(k, [])) for l in acc if l not in named) for k in s["periods"]]
            if not all(close(a, b) for a, b in zip(totals, ser["values"])):
                return False
        else:
            got = [math.fsum(acc.get(ser["label"], {}).get(k, [])) for k in s["periods"]]
            if not all(close(a, b) for a, b in zip(got, ser["values"])):
                return False
    return True


def _corr(f: Fact, v: VCtx) -> bool:
    s, ti = f.spec, f.table_index
    a, b = v.col(ti, s["a"]), v.col(ti, s["b"])
    pairs = [(float(x), float(y)) for x, y in zip(a, b) if not isnull(x) and not isnull(y)]
    if len(pairs) != f.payload["n"]:
        return False
    rho = _pearson(_ranks([x for x, _ in pairs]), _ranks([y for _, y in pairs]))
    return close(rho, f.payload["rho"])


def _derivation(f: Fact, v: VCtx) -> bool:
    s, ti, p = f.spec, f.table_index, f.payload
    z, x, y = (v.col(ti, s[k]) for k in ("z", "x", "y"))
    n = bad = 0
    for a, b, c in zip(z, x, y):
        if isnull(a) or isnull(b) or isnull(c):
            continue
        n += 1
        e = float(b) * float(c)
        if abs(float(a) - e) > 1e-6 + 1e-6 * abs(e):
            bad += 1
    return n == p["checked_rows"] and bad == p["mismatch_count"] and close((n - bad) / n, p["match_share"])


def _target(f: Fact, v: VCtx) -> bool:
    s, ti, p = f.spec, f.table_index, f.payload
    ser = v.series(ti, s["time"], "M", s["measure"], "sum")
    flags = v.complete_flags(ti, s["time"], "M", sorted(ser))
    ri, kcol = s["ref_table_index"], s["key_column"]
    keys = []
    for x in v.col(ri, kcol):
        if isnull(x):
            keys.append(None)
        elif hasattr(x, "year"):
            keys.append(f"{x.year:04d}-{x.month:02d}")
        else:
            m = re.fullmatch(r"(\d{4})[-/](\d{1,2})", str(x).strip())
            keys.append(f"{m.group(1)}-{int(m.group(2)):02d}" if m else None)
    tg: dict = {}
    for k, val in zip(keys, v.col(ri, s["ref_column"])):
        if k is not None and not isnull(val):
            tg[k] = tg.get(k, 0.0) + float(val)
    ta = tt = 0.0
    for r in p["periods"]:
        pk = r["period"]
        if not flags.get(pk) or ser[pk][0] is None or pk not in tg:
            return False
        if not (close(ser[pk][0], r["actual"]) and close(tg[pk], r["target"])):
            return False
        ta, tt = ta + ser[pk][0], tt + tg[pk]
    return close(ta / tt, p["attainment"])


def _outliers(f: Fact, v: VCtx) -> bool:
    lo, hi = f.spec["fences"]
    xs = [float(x) for x in v.col(f.table_index, f.spec["measure"]) if not isnull(x)]
    return sum(1 for x in xs if x < lo or x > hi) == f.payload["count"]


CHECKS = {"kpi": _kpi, "ranking": _group, "trend": _trend, "period_change": _period_change, "swing": _swing,
          "anomaly_period": _anomaly_period, "breakdown": _breakdown, "correlation": _corr,
          "derivation": _derivation, "target": _target, "anomaly_values": _outliers}


def verify(f: Fact, v: VCtx) -> bool:
    try:
        return bool(CHECKS[f.kind](f, v))
    except Exception:
        return False
