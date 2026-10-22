"""Trends, period-over-period change, largest swing, unusual periods, and breakdown over time."""
import numpy as np
import pandas as pd

from .facts_basic import labels
from .model import Fact
from .numfmt import fmt, num, pct
from .periods import GRAIN_NAME, build_series
from .plan import TableCtx, dim_suitability, importance, reliability

MIN_ROWS = 5  # a change between two periods needs at least this many rows behind each one


def kendall_tau(v: list[float]) -> float:
    n = len(v)
    if n < 2:
        return 0.0
    s = sum(np.sign(v[j] - v[i]) for i in range(n) for j in range(i + 1, n))
    return float(s / (n * (n - 1) / 2))


def direction(values: list[float]) -> tuple[str, float]:
    tau = kendall_tau(values)
    first, last = values[0], values[-1]
    rel = (last - first) / abs(first) if first else None
    if len(values) >= 4 and abs(tau) >= 0.4 and rel is not None and abs(rel) >= 0.1:
        return ("rising" if tau > 0 else "falling"), tau
    return "flat_or_mixed", tau


def _label(c, agg) -> str:
    return "the number of records" if c is None else (f"total {c.name}" if agg == "sum" else f"average {c.name}")


def time_facts(tc: TableCtx) -> list[Fact]:
    if tc.time is None or tc.grain is None:
        return []
    t, df, g = tc.t, tc.df, tc.grain
    gname, tcol = GRAIN_NAME[g], tc.time
    out: list[Fact] = []
    series_for = [(None, "count")] + [(c, "sum") for c, m in tc.measures if m == "sum"]
    for c, agg in series_for:
        items = build_series(df, tcol.name, g, c.name if c else None, agg, tc.min_d, tc.max_d)
        done = [i for i in items if i["complete"] and i["value"] is not None]
        if len(done) < 4:
            continue
        vals = [i["value"] for i in done]
        first, last = done[0], done[-1]
        label, cur, imp = _label(c, agg), (c.currency if c else None), importance(c)
        excluded = [i["period"] for i in items if not i["complete"]]
        empty = [i["period"] for i in items if i["empty"]]
        cols = [x for x in (tcol, c) if x is not None]
        used = sum(i["rows"] for i in done)
        thin = used / len(done) < MIN_ROWS
        rel, cav = reliability(tc, cols, used, agg, extra=(0.9 if empty else 1.0) * (0.85 if thin else 1.0))
        if thin:
            cav.append(f"Only {used / len(done):.1f} rows per {gname} on average, so single {gname}s are noisy.")
        if excluded:
            cav.append(f"Incomplete {gname}(s) left out of the comparisons: {', '.join(excluded)}.")
        if empty:
            cav.append(f"{len(empty)} {gname}(s) have no rows at all and count as zero: {', '.join(empty[:6])}.")
        spec = {"op": "series", "time": tcol.name, "grain": g, "measure": c.name if c else None, "agg": agg}
        src = {"table": t.name, "columns": [x.name for x in cols], "rows_used": used}
        common = dict(table_index=t.index, measure=c.name if c else None, time_column=tcol.name, agg=agg,
                      source=src, spec=spec, reliability=rel, caveats=cav)
        mname = c.name if c else "records"
        change = last["value"] - first["value"]
        change_pct = change / abs(first["value"]) if first["value"] else None
        dirn, tau = direction(vals)
        peak, low = max(done, key=lambda i: i["value"]), min(done, key=lambda i: i["value"])
        word = {"rising": "rising", "falling": "falling", "flat_or_mixed": "no clear direction"}[dirn]
        use = (0.85 if dirn != "flat_or_mixed" else 0.6) * imp * (0.8 if c is None else 1.0)
        out.append(Fact(
            kind="trend", key=f"trend:{t.index}:{mname}:{tcol.name}", title=f"How does {label} change by {gname}?",
            headline=(f"{label[0].upper() + label[1:]} by {gname}: {first['period']} {fmt(first['value'], cur)} → "
                      f"{last['period']} {fmt(last['value'], cur)} ({pct(change_pct, True)}); pattern: {word}"),
            definition=(f"{'Row count' if agg == 'count' else 'Sum of “' + c.name + '”'} per {gname} using “{tcol.name}”. "
                        f"Only complete {gname}s are compared; the direction needs at least 4 of them."),
            payload={"grain": g, "agg": agg, "periods": items, "complete_periods": len(done), "first": first,
                     "last": last, "change_abs": num(change), "change_pct": num(change_pct), "direction": dirn,
                     "tau": num(tau, 4), "peak": peak, "low": low, "excluded_partial": excluded,
                     "empty_periods": empty, "currency": cur},
            usefulness=round(use, 3), group=f"trend:{t.index}:{mname}", **common))

        if len(done) >= 2:
            p1, p2 = done[-2], done[-1]
            pos = {i["period"]: k for k, i in enumerate(items)}
            if pos[p2["period"]] - pos[p1["period"]] == 1 and min(p1["rows"], p2["rows"]) >= MIN_ROWS:
                d_abs = p2["value"] - p1["value"]
                d_pct = d_abs / abs(p1["value"]) if p1["value"] else None
                cav2 = list(cav)
                if not items[-1]["complete"]:
                    cav2.append(f"The latest {gname} ({items[-1]['period']}) is incomplete, so it is not compared.")
                out.append(Fact(
                    kind="period_change", key=f"period_change:{t.index}:{mname}:{tcol.name}",
                    title=f"What changed in {label} compared with the previous {gname}?",
                    headline=(f"{label[0].upper() + label[1:]} in {p2['period']} was {fmt(p2['value'], cur)} vs "
                              f"{fmt(p1['value'], cur)} in {p1['period']} ({pct(d_pct, True)})"),
                    definition=f"Latest complete {gname} compared with the {gname} before it.",
                    payload={"grain": g, "latest": p2, "previous": p1, "change_abs": num(d_abs),
                             "change_pct": num(d_pct), "currency": cur},
                    usefulness=round(0.8 * imp * (0.8 if c is None else 1.0), 3), group=f"period_change:{t.index}:{mname}",
                    **{**common, "caveats": cav2}))

        # biggest step between adjacent complete periods (ignore tiny bases)
        mean_v = float(np.mean(vals))
        best = None
        for a, b in zip(done, done[1:]):
            if (pos_ok(items, a, b) and min(a["rows"], b["rows"]) >= MIN_ROWS
                    and abs(a["value"]) >= 0.05 * abs(mean_v) and a["value"] != 0):
                p = (b["value"] - a["value"]) / abs(a["value"])
                if best is None or abs(p) > abs(best[2]):
                    best = (a, b, p)
        if best and abs(best[2]) >= 0.2:
            a, b, p = best
            out.append(Fact(
                kind="swing", key=f"swing:{t.index}:{mname}:{tcol.name}",
                title=f"Which {gname} saw the biggest change in {label}?",
                headline=(f"The largest {gname}-to-{gname} change in {label} was {a['period']} → {b['period']}: "
                          f"{fmt(a['value'], cur)} → {fmt(b['value'], cur)} ({pct(p, True)})"),
                definition=(f"Largest relative change between two consecutive complete {gname}s "
                            "(starting values below 5% of the average are ignored)."),
                payload={"grain": g, "from": a, "to": b, "change_pct": num(p), "currency": cur},
                usefulness=round(0.65 * imp * (0.8 if c is None else 1.0), 3), group=f"swing:{t.index}:{mname}", **common))

        solid = [i for i in done if i["rows"] >= MIN_ROWS]
        if len(solid) >= 8:
            svals = [i["value"] for i in solid]
            med = float(np.median(svals))
            mad = float(np.median([abs(v - med) for v in svals]))
            if mad > 0:
                flagged = [{**i, "robust_z": num(0.6745 * (i["value"] - med) / mad, 3)} for i in solid
                           if abs(0.6745 * (i["value"] - med) / mad) >= 3.5]
                if flagged:
                    out.append(Fact(
                        kind="anomaly_period", key=f"anomaly_period:{t.index}:{mname}:{tcol.name}",
                        title=f"Are there unusual {gname}s for {label}?",
                        headline=(f"{', '.join(f['period'] for f in flagged[:3])} stand out for {label} "
                                  f"(typical {gname}: {fmt(med, cur)})"),
                        definition=(f"{gname.capitalize()}s whose value is far from the median "
                                    "(robust z-score ≥ 3.5, using the median absolute deviation)."),
                        payload={"grain": g, "median": num(med), "mad": num(mad), "flagged": flagged, "currency": cur},
                        usefulness=round(0.7 * imp * (0.8 if c is None else 1.0), 3),
                        group=f"anomaly_period:{t.index}:{mname}", **common))

    out.extend(breakdown_facts(tc))
    return out


def pos_ok(items, a, b) -> bool:
    names = [i["period"] for i in items]
    return names.index(b["period"]) - names.index(a["period"]) == 1


def breakdown_facts(tc: TableCtx) -> list[Fact]:
    """Category × time × measure: the data behind grouped or stacked charts (top 5 groups + other)."""
    t, df, g = tc.t, tc.df, tc.grain
    out = []
    cands = [d for d in tc.dims if 3 <= d.distinct_count <= 8]
    if not cands:
        return out
    d = max(cands, key=lambda x: (dim_suitability(x.distinct_count), x.distinct_count))
    tcol = tc.time
    for c, mode in tc.measures:
        if mode != "sum":
            continue
        base = build_series(df, tcol.name, g, c.name, "sum", tc.min_d, tc.max_d)
        periods = [i["period"] for i in base if i["complete"] and i["value"] is not None]
        if len(periods) < 4:
            continue
        lab = labels(df[d.name])
        sub = df.assign(_l=lab, _p=df[tcol.name].dt.to_period(g).astype(str)).dropna(subset=["_l", tcol.name, c.name])
        sub = sub[sub["_p"].isin(periods)]
        if sub.empty:
            continue
        piv = sub.pivot_table(index="_p", columns="_l", values=c.name, aggfunc="sum", fill_value=0.0).reindex(periods, fill_value=0.0)
        order = piv.sum().sort_values(ascending=False, kind="mergesort").index.tolist()
        top, rest = order[:5], order[5:]
        series = [{"label": str(k), "values": [num(v) for v in piv[k].tolist()], "total": num(piv[k].sum())} for k in top]
        if rest:
            series.append({"label": "Other", "values": [num(v) for v in piv[rest].sum(axis=1).tolist()],
                           "total": num(piv[rest].to_numpy().sum())})
        rel, cav = reliability(tc, [tcol, c, d], len(sub), "sum")
        out.append(Fact(
            kind="breakdown", key=f"breakdown:{tc.t.index}:{c.name}:{d.name}:{tcol.name}",
            title=f"How is {c.name} split by {d.name} over time?",
            headline=f"{c.name} by {d.name} and {GRAIN_NAME[g]}: {top[0]} is the largest group overall",
            definition=f"Sum of “{c.name}” per {GRAIN_NAME[g]} and “{d.name}”, complete {GRAIN_NAME[g]}s only; the five largest groups are shown, the rest as “Other”.",
            payload={"grain": g, "periods": periods, "series": series, "currency": c.currency},
            spec={"op": "breakdown", "time": tcol.name, "grain": g, "measure": c.name, "dim": d.name, "periods": periods},
            source={"table": tc.t.name, "columns": [tcol.name, c.name, d.name], "rows_used": int(len(sub))},
            table_index=tc.t.index, measure=c.name, dimension=d.name, time_column=tcol.name, agg="sum",
            caveats=cav, usefulness=round(0.6 * importance(c) * dim_suitability(d.distinct_count), 3), reliability=rel,
            group=f"breakdown:{tc.t.index}:{c.name}"))
    return out
