"""Executes a validated plan with pandas. The result is later re-computed independently (verify.py)."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..analytics.numfmt import num
from ..analytics.periods import GRAIN_NAME, build_series
from .plan import PlanError, describe

MIN_ROWS, MIN_GROUP = 5, 5


@dataclass
class Result:
    kind: str  # agg | group | series | compare | contribution | table
    data: dict
    rows_used: int
    rows_after_filters: int
    sample_rows: list = field(default_factory=list)
    definition: str = ""
    caveats: list = field(default_factory=list)
    chart: dict | None = None


def apply_filters(df: pd.DataFrame, plan: dict) -> pd.DataFrame:
    d = df
    for f in plan["filters"]:
        if "values" in f:
            d = d[d[f["col"]].astype("string").str.strip().isin(f["values"])]
        else:
            if f["from"]:
                d = d[d[f["col"]] >= pd.Timestamp(f["from"])]
            if f["to"]:
                d = d[d[f["col"]] < pd.Timestamp(f["to"]) + pd.Timedelta(1, unit="D")]
    return d


def coverage(df: pd.DataFrame, plan: dict, time: str):
    t = df[time].dropna()
    lo, hi = t.min().normalize(), t.max().normalize()
    for f in plan["filters"]:
        if f["col"] == time:
            if f.get("from"):
                lo = max(lo, pd.Timestamp(f["from"]))
            if f.get("to"):
                hi = min(hi, pd.Timestamp(f["to"]))
    return lo, hi


def _labels(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip()


def _currency(schema_table: dict, name):
    return next((c.get("currency") for c in schema_table["columns"] if c["name"] == name), None)


def _pick_periods(items: list, plan: dict):
    if plan["periods"]:
        by = {i["period"]: i for i in items}
        for k in "ab":
            if plan["periods"][k] not in by:
                raise PlanError("no_data", f"There is no data for {plan['periods'][k]}.")
        return by[plan["periods"]["a"]], by[plan["periods"]["b"]]
    done = [i for i in items if i["complete"] and i["value"] is not None]
    names = [i["period"] for i in items]
    if len(done) < 2 or names.index(done[-1]["period"]) - names.index(done[-2]["period"]) != 1:
        raise PlanError("not_enough_periods", "There are not enough complete periods to compare.")
    return done[-2], done[-1]


def _top_rows(df: pd.DataFrame, m: str | None, k: int = 10) -> list:
    if m is None:
        return [int(r) for r in df["row_number"].head(k)]
    x = df.dropna(subset=[m]).sort_values([m, "row_number"], ascending=[False, True], kind="mergesort")
    return [int(r) for r in x["row_number"].head(k)]


def execute(plan: dict, df: pd.DataFrame, table: dict) -> Result:
    d = apply_filters(df, plan)
    m, agg, op = plan["measure"], plan["agg"], plan["op"]
    cur = _currency(table, m)
    caveats = []
    if m and d[m].isna().any():
        caveats.append(f"{int(d[m].isna().sum())} row(s) have no value in “{m}” and are left out.")
    base = dict(rows_after_filters=int(len(d)), definition=describe(plan))

    if op == "agg":
        if m is None:
            value, used = len(d), len(d)
        else:
            x = d[m].dropna()
            used = len(x)
            value = None if x.empty else float({"sum": x.sum, "mean": x.mean, "median": x.median, "min": x.min, "max": x.max}[agg]())
        label = ("Rows" if m is None else {"sum": "Total", "mean": "Average", "median": "Median", "min": "Smallest", "max": "Largest",
                                           "count": "Count of"}[agg] + f" {m}")
        data = {"agg": agg, "measure": m, "value": num(value) if value is not None else None, "count": int(used), "currency": cur}
        chart = {"kind": "kpi", "why": "The single number the question asks for.",
                 "data": {"label": label, "value": data["value"], "format": "currency" if cur else "number", "currency": cur, "delta": None}, "options": {}}
        return Result("agg", data, int(used), sample_rows=_top_rows(d, m, 5), caveats=caveats, chart=chart, **base)

    if op == "group":
        lab = _labels(d[plan["dim"]])
        if m is None:
            mask = lab.notna()
            g = d[mask].groupby(lab[mask]).size().astype(float)
            sizes = g
        else:
            mask = lab.notna() & d[m].notna()
            grp = pd.DataFrame({"l": lab[mask], "v": d.loc[mask, m]}).groupby("l")["v"]
            g = grp.agg({"sum": "sum", "mean": "mean", "median": "median", "min": "min", "max": "max", "count": "count"}[agg])
            sizes = grp.size()
            if agg in ("mean", "median"):
                keep = sizes >= MIN_GROUP
                if (~keep).any():
                    caveats.append(f"{int((~keep).sum())} group(s) with fewer than {MIN_GROUP} rows were left out.")
                g, sizes = g[keep], sizes[keep]
        if g.empty:
            return Result("group", {"groups": [], "n_groups": 0, "total": None, "agg": agg, "currency": cur}, 0, caveats=caveats, **base)
        g = g.rename("v").reset_index()
        g.columns = ["l", "v"]
        g = g.sort_values(["v", "l"], ascending=[plan["order"] == "asc", True], kind="mergesort").reset_index(drop=True)
        additive = agg in ("sum", "count")
        total = float(g["v"].sum())
        shares = additive and total > 0 and bool((g["v"] >= 0).all())
        sz = sizes.to_dict()
        top = g.head(plan["limit"])
        groups = [{"label": r.l, "value": num(r.v), "share": num(r.v / total) if shares else None, "rows": int(sz[r.l])} for r in top.itertuples()]
        rest = g.iloc[plan["limit"]:]
        if len(rest) and additive and plan["order"] == "desc":
            v = float(rest["v"].sum())
            groups.append({"label": f"Other ({len(rest)})", "value": num(v), "share": num(v / total) if shares else None, "rows": None, "muted": True})
        data = {"agg": agg, "n_groups": int(len(g)), "total": num(total) if additive else None, "groups": groups,
                "order": plan["order"], "currency": cur}
        chart = {"kind": "hbar", "why": "Bars on a common scale make the groups easy to compare.", "data": {"groups": groups, "n_groups": data["n_groups"], "total": data["total"]},
                 "options": {"currency": cur, "agg": agg, "additive": additive, "alt_kinds": []}}
        sub = d[mask & (lab == top.iloc[0]["l"])] if len(top) else d
        return Result("group", data, int(sizes.sum()), sample_rows=_top_rows(sub, m, 10), caveats=caveats, chart=chart, **base)

    # time-based operations
    tcol, grain = plan["time"], plan["grain"]
    lo, hi = coverage(df, plan, tcol)
    gname = GRAIN_NAME[grain]
    items = build_series(d, tcol, grain, m, agg if op != "contribution" else "sum", lo, hi)
    if not items:
        return Result("series", {"x": [], "y": [], "rows": [], "complete": []}, 0, caveats=caveats, **base)

    if op == "series":
        done = [i for i in items if i["complete"] and i["value"] is not None]
        if any(not i["complete"] for i in items):
            caveats.append(f"Incomplete {gname}(s) are drawn dashed and not used for the highest/lowest: "
                           f"{', '.join(i['period'] for i in items if not i['complete'])}.")
        data = {"grain": grain, "agg": agg, "measure": m, "periods": items, "currency": cur,
                "peak": max(done, key=lambda i: i["value"]) if done else None, "low": min(done, key=lambda i: i["value"]) if done else None,
                "first": done[0] if done else None, "last": done[-1] if done else None}
        chart = {"kind": "line", "why": f"A line shows how the value moves from one {gname} to the next.",
                 "data": {"x": [i["period"] for i in items], "y": [i["value"] for i in items], "rows": [i["rows"] for i in items],
                          "complete": [i["complete"] for i in items]}, "options": {"currency": cur, "grain": grain, "annotations": []}}
        return Result("series", data, sum(i["rows"] for i in items), sample_rows=_top_rows(d, m, 10), caveats=caveats, chart=chart, **base)

    a, b = _pick_periods(items, plan)
    for p in (a, b):
        if not p["complete"]:
            caveats.append(f"{p['period']} is an incomplete {gname}, so the comparison is not like for like.")
        elif p["rows"] < MIN_ROWS:
            caveats.append(f"Only {p['rows']} row(s) in {p['period']}.")
    if a["value"] is None or b["value"] is None:
        raise PlanError("no_data", "There is no value to compare for one of the periods.")

    if op == "compare":
        ch = b["value"] - a["value"]
        pc = ch / abs(a["value"]) if a["value"] else None
        data = {"grain": grain, "agg": agg, "measure": m, "a": a, "b": b, "change_abs": num(ch), "change_pct": num(pc), "currency": cur}
        chart = {"kind": "kpi", "why": "The latest value, with its change from the earlier period.",
                 "data": {"label": f"{m or 'Rows'} in {b['period']}", "value": b["value"], "format": "currency" if cur else "number", "currency": cur,
                          "delta": {"pct": num(pc), "abs": num(ch), "latest": b["period"], "previous": a["period"]}}, "options": {}}
        return Result("compare", data, a["rows"] + b["rows"], sample_rows=_top_rows(d, m, 10), caveats=caveats, chart=chart, **base)

    # contribution: where did the change between two periods come from?
    lab = _labels(d[plan["dim"]])
    sub = d.assign(_l=lab, _p=d[tcol].dt.to_period(grain).astype(str)).dropna(subset=["_l", tcol, m])
    sub = sub[sub["_p"].isin([a["period"], b["period"]])]
    if len(sub) < len(d[d[tcol].dt.to_period(grain).astype(str).isin([a["period"], b["period"]])]):
        caveats.append("Rows without a value in the breakdown column are not included in the contributions.")
    ap, bp = a["period"], b["period"]
    piv = sub.pivot_table(index="_l", columns="_p", values=m, aggfunc="sum", fill_value=0.0).reindex(columns=[ap, bp], fill_value=0.0)
    entries = [(str(l), float(piv.at[l, ap]), float(piv.at[l, bp])) for l in piv.index]
    entries = sorted(((l, va, vb, vb - va) for l, va, vb in entries), key=lambda e: (-abs(e[3]), e[0]))
    ta, tb = sum(e[1] for e in entries), sum(e[2] for e in entries)
    change = tb - ta
    groups = [{"label": l, "a": num(va), "b": num(vb), "delta": num(dl), "share_of_change": num(dl / change) if change else None}
              for l, va, vb, dl in entries[: plan["limit"]]]
    rest = entries[plan["limit"]:]
    other = {"n_groups": len(rest), "delta": num(sum(e[3] for e in rest))} if rest else None
    data = {"grain": grain, "measure": m, "a": {"period": a["period"], "total": num(ta)}, "b": {"period": b["period"], "total": num(tb)},
            "change": num(change), "change_pct": num(change / ta) if ta else None, "groups": groups, "other": other,
            "dim": plan["dim"], "currency": cur}
    bars = [{"label": x["label"], "value": x["delta"], "share": None, "rows": None} for x in groups]
    if other:
        bars.append({"label": f"Other ({other['n_groups']})", "value": other["delta"], "share": None, "rows": None, "muted": True})
    chart = {"kind": "hbar", "why": f"Each bar is how much a {plan['dim']} value added to or took away from the change between the two {gname}s.",
             "data": {"groups": bars, "n_groups": len(entries), "total": None}, "options": {"currency": cur, "agg": "sum", "additive": False, "alt_kinds": []}}
    top_label = groups[0]["label"] if groups else None
    srows = _top_rows(sub[(sub["_l"] == top_label) & sub["_p"].isin([a["period"], b["period"]])], m, 10) if top_label else []
    return Result("contribution", data, int(len(sub)), sample_rows=srows, caveats=caveats, chart=chart, **base)


def execute_top_rows(plan: dict, df: pd.DataFrame, table: dict) -> Result:
    d = apply_filters(df, plan)
    m = plan["measure"]
    x = d.dropna(subset=[m]).sort_values([m, "row_number"], ascending=[plan["order"] == "asc", True], kind="mergesort")
    dims = [c["name"] for c in table["columns"] if c["role"] == "dimension"][:3]
    time = [c["name"] for c in table["columns"] if c["role"] == "time"][:1]
    cols = ["row_number", *time, *dims, m]
    head = x.head(plan["limit"])

    def cell(v):
        if isinstance(v, pd.Timestamp):
            return v.date().isoformat()
        if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA:
            return None
        return num(v) if isinstance(v, (float, np.floating)) else (int(v) if isinstance(v, (int, np.integer)) else str(v))
    rows = [[cell(v) for v in r] for r in head[cols].itertuples(index=False)]
    data = {"columns": ["Excel row" if c == "row_number" else c for c in cols], "rows": rows, "total_rows": int(len(x)), "measure": m,
            "order": plan["order"], "currency": _currency(table, m)}
    return Result("table", data, int(len(x)), rows_after_filters=int(len(d)), sample_rows=[int(r) for r in head["row_number"]],
                  definition=describe(plan), chart={"kind": "table", "why": "The rows themselves, with their Excel row numbers.", "data": data, "options": {}})


def run_plan(plan: dict, df: pd.DataFrame, table: dict) -> Result:
    return execute_top_rows(plan, df, table) if plan["op"] == "top_rows" else execute(plan, df, table)
