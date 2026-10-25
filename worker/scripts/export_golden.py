"""Exports cleaned tables (Parquet) and expected results computed with pandas.

The browser data engine (web/src/lib/dataEngine.ts) must reproduce these numbers exactly.
Run from worker/:  python scripts/export_golden.py
"""
import io
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.analytics.periods import build_series  # noqa: E402
from app.analytics.run import compute_analytics  # noqa: E402
from app.charts.run import build_charts  # noqa: E402
from app.context.infer import build_context  # noqa: E402
from app.engine.analyze import analyze_workbook  # noqa: E402
from app.guide.build import build_guide  # noqa: E402
from app.qa.highlights import highlights_answer  # noqa: E402
from app.insights.build import build_insights  # noqa: E402
from app.qa.run import QAContext, answer_question  # noqa: E402
from app.qa.schema import schema_from_output  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "web", "tests", "golden")
MIN_ROWS = 5


def parquet(df, name):
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, compression="snappy", coerce_timestamps="ms", allow_truncated_timestamps=True)
    open(os.path.join(OUT, name), "wb").write(buf.getvalue())


def jsonable(x):
    if isinstance(x, dict):
        return {k: jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if (np.isnan(x) or np.isinf(x)) else float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def apply_filters(df, f, time):
    d = df
    if f.get("from"):
        d = d[d[time] >= pd.Timestamp(f["from"])]
    if f.get("to"):
        d = d[d[time] < pd.Timestamp(f["to"]) + pd.Timedelta(1, unit="D")]
    for c, vals in f.get("dims", {}).items():
        d = d[d[c].astype("string").str.strip().isin(vals)]
    return d


def py_group(df, q):
    lab = df[q["dim"]].astype("string").str.strip()
    if q["measure"] is None:
        m = lab.notna()
        g = df[m].groupby(lab[m]).size().astype(float)
        sizes = g
    else:
        m = lab.notna() & df[q["measure"]].notna()
        grp = pd.DataFrame({"l": lab[m], "v": df.loc[m, q["measure"]]}).groupby("l")["v"]
        g, sizes = (grp.sum() if q["agg"] == "sum" else grp.mean()), grp.size()
        if q["agg"] == "mean":
            keep = sizes >= q["min_group"]
            g, sizes = g[keep], sizes[keep]
    g = g.rename("v").reset_index()
    g.columns = ["l", "v"]
    g = g.sort_values(["v", "l"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    additive = q["agg"] != "mean"
    total = float(g["v"].sum())
    ok = additive and total > 0 and (g["v"] >= 0).all()
    sizes = sizes.to_dict()
    lim = q["limit"]
    groups = [{"label": r.l, "value": float(r.v), "share": float(r.v / total) if ok else None, "rows": int(sizes[r.l])}
              for r in g.head(lim).itertuples()]
    rest = g.iloc[lim:]
    if len(rest) and additive:
        v = float(rest["v"].sum())
        groups.append({"label": f"Other ({len(rest)})", "value": v, "share": v / total if ok else None, "rows": None, "muted": True})
    return {"groups": groups, "n_groups": int(len(g)), "total": total if additive else None}


def py_breakdown(df, q, lo, hi):
    base = build_series(df, q["time"], q["grain"], q["measure"], "sum", lo, hi)
    periods = [i["period"] for i in base if i["complete"] and i["value"] is not None]
    lab = df[q["dim"]].astype("string").str.strip()
    sub = df.assign(_l=lab, _p=df[q["time"]].dt.to_period(q["grain"]).astype(str)).dropna(subset=["_l", q["time"], q["measure"]])
    sub = sub[sub["_p"].isin(periods)]
    piv = sub.pivot_table(index="_p", columns="_l", values=q["measure"], aggfunc="sum", fill_value=0.0).reindex(periods, fill_value=0.0)
    order = piv.sum().sort_values(ascending=False, kind="mergesort").index.tolist()
    top, rest = order[: q["top"]], order[q["top"]:]
    s = [{"label": str(k), "values": piv[k].tolist()} for k in top]
    if rest:
        s.append({"label": "Other", "values": piv[rest].sum(axis=1).tolist()})
    return {"x": periods, "series": s}


def py_delta(items):
    done = [i for i in items if i["complete"] and i["value"] is not None]
    if len(done) < 2:
        return None
    a, b = done[-2], done[-1]
    names = [i["period"] for i in items]
    if names.index(b["period"]) - names.index(a["period"]) != 1 or min(a["rows"], b["rows"]) < MIN_ROWS:
        return None
    ab = b["value"] - a["value"]
    return {"pct": ab / abs(a["value"]) if a["value"] else None, "abs": ab, "latest": b["period"], "previous": a["period"]}


def py_hist(df, q):
    xs = df[q["measure"]].dropna().to_numpy()
    nb = min(q["bins"], len(set(xs.tolist())))
    if nb < 2:
        return {"edges": [], "counts": []}
    counts, edges = np.histogram(xs, bins=nb)
    return {"edges": edges.tolist(), "counts": counts.tolist()}


def expected(df_all, f, time, queries):
    df = apply_filters(df_all, f, time)
    t = df_all[time].dropna()
    lo, hi = t.min().normalize(), t.max().normalize()
    if f.get("from"):
        lo = max(lo, pd.Timestamp(f["from"]))
    if f.get("to"):
        hi = min(hi, pd.Timestamp(f["to"]))
    res = []
    for q in queries:
        op = q["op"]
        if op == "agg":
            if q["measure"] is None:
                r = {"value": int(len(df)), "count": int(len(df))}
            else:
                x = df[q["measure"]].dropna()
                r = {"value": float(x.sum() if q["agg"] == "sum" else x.mean()) if len(x) else None, "count": int(len(x))}
            if q.get("delta"):
                r["delta"] = py_delta(build_series(df, q["delta"]["time"], q["delta"]["grain"], q["measure"], q["agg"], lo, hi))
        elif op == "series":
            r = build_series(df, q["time"], q["grain"], q["measure"], q["agg"], lo, hi)
        elif op == "group":
            r = py_group(df, q)
        elif op == "breakdown":
            r = py_breakdown(df, q, lo, hi)
        elif op == "histogram":
            r = py_hist(df, q)
        res.append({"query": q, "expect": jsonable(r)})
    return {"filters": f, "rows": int(len(df)), "results": res}


def out_summary_findings(o):
    from collections import Counter
    c = Counter(f.severity for f in o.findings)
    return {k: c.get(k, 0) for k in ("high", "medium", "low", "info")}


def main():
    os.makedirs(OUT, exist_ok=True)
    gold = {}

    out = analyze_workbook(open(os.path.join(FIX, "01_sales_clean.xlsx"), "rb").read())
    sales = out.frames[out.tables[0].id]
    parquet(sales, "sales.parquet")
    qs = [
        {"op": "agg", "agg": "sum", "measure": "total_dzd", "delta": {"time": "date", "grain": "M"}},
        {"op": "agg", "agg": "count", "measure": None, "delta": {"time": "date", "grain": "M"}},
        {"op": "agg", "agg": "mean", "measure": "unit_price_dzd"},
        {"op": "series", "time": "date", "grain": "M", "measure": "total_dzd", "agg": "sum"},
        {"op": "series", "time": "date", "grain": "M", "measure": None, "agg": "count"},
        {"op": "series", "time": "date", "grain": "M", "measure": "unit_price_dzd", "agg": "mean"},
        {"op": "series", "time": "date", "grain": "W", "measure": "total_dzd", "agg": "sum"},
        {"op": "group", "dim": "category", "measure": "total_dzd", "agg": "sum", "limit": 10, "min_group": 0},
        {"op": "group", "dim": "wilaya", "measure": None, "agg": "count", "limit": 4, "min_group": 0},
        {"op": "group", "dim": "wilaya", "measure": "total_dzd", "agg": "sum", "limit": 3, "min_group": 0},
        {"op": "group", "dim": "category", "measure": "unit_price_dzd", "agg": "mean", "limit": 10, "min_group": 5},
        {"op": "breakdown", "time": "date", "grain": "M", "measure": "total_dzd", "dim": "category", "top": 3},
        {"op": "breakdown", "time": "date", "grain": "M", "measure": "quantity", "dim": "channel", "top": 5},
        {"op": "histogram", "measure": "total_dzd", "bins": 10},
    ]
    cases = [
        {"name": "no filters", "f": {}},
        {"name": "one category", "f": {"dims": {"category": ["Electronics"]}}},
        {"name": "date range cutting months", "f": {"from": "2026-03-10", "to": "2026-06-20"}},
        {"name": "range + two channels", "f": {"from": "2026-02-01", "to": "2026-08-31", "dims": {"channel": ["Online", "Phone"]}}},
        {"name": "rare combination", "f": {"dims": {"category": ["Grocery"], "wilaya": ["Tizi Ouzou", "Batna"]}}},
    ]
    gold["sales"] = {"parquet": "sales.parquet", "timeCol": "date", "cases": [
        {"name": c["name"], **expected(sales, c["f"], "date", qs)} for c in cases]}

    # drill-down: which rows sit behind a bar / a month
    el = sales[sales["category"] == "Electronics"]
    may = sales[sales["date"].dt.to_period("M").astype(str) == "2026-05"]
    gold["sales"]["drill"] = {
        "group_category_Electronics": sorted(el["row_number"].tolist()),
        "period_2026-05": sorted(may["row_number"].tolist()),
        "breakdown_Online_2026-05": sorted(may[may["channel"] == "Online"]["row_number"].tolist()),
    }

    out2 = analyze_workbook(open(os.path.join(FIX, "02_messy_ventes_fr.xlsx"), "rb").read())
    messy = out2.frames[out2.tables[0].id]
    parquet(messy, "messy.parquet")
    qm = [
        {"op": "series", "time": "Date", "grain": "W", "measure": "Montant (DA)", "agg": "sum"},
        {"op": "series", "time": "Date", "grain": "W", "measure": None, "agg": "count"},
        {"op": "group", "dim": "Wilaya", "measure": None, "agg": "count", "limit": 10, "min_group": 0},
        {"op": "agg", "agg": "mean", "measure": "Prix unitaire (DA)"},
    ]
    gold["messy"] = {"parquet": "messy.parquet", "timeCol": "Date", "cases": [
        {"name": "no filters", **expected(messy, {}, "Date", qm)},
        {"name": "paid only", **expected(messy, {"dims": {"Statut": ["Payé"]}}, "Date", qm)}]}

    # every period grain, over several years
    rnd = np.random.default_rng(7)
    dates = pd.to_datetime("2019-03-17") + pd.to_timedelta(rnd.integers(0, 365 * 7 + 120, 1500), unit="D")
    multi = pd.DataFrame({"row_number": np.arange(2, 1502), "date": dates, "amount": rnd.uniform(5, 500, 1500).round(2)})
    multi.loc[rnd.choice(1500, 40, replace=False), "amount"] = np.nan
    parquet(multi, "multiyear.parquet")
    qy = [{"op": "series", "time": "date", "grain": g, "measure": "amount", "agg": a}
          for g in ("W", "M", "Q", "Y") for a in ("sum", "mean", "count")]
    qd = [{"op": "series", "time": "date", "grain": "D", "measure": "amount", "agg": a} for a in ("sum", "mean", "count")]
    gold["multiyear"] = {"parquet": "multiyear.parquet", "timeCol": "date", "cases": [
        {"name": "all years", **expected(multi, {}, "date", qy)},
        {"name": "mid-quarter range", **expected(multi, {"from": "2021-02-11", "to": "2024-08-19"}, "date", qy)},
        {"name": "two weeks, daily", **expected(multi, {"from": "2022-05-02", "to": "2022-05-15"}, "date", qd)},
        {"name": "one quarter, daily", **expected(multi, {"from": "2023-01-01", "to": "2023-03-31"}, "date", qd)}]}

    # scatter sampling
    n = 900
    x = rnd.uniform(1, 50, n).round(3)
    sc = pd.DataFrame({"row_number": np.arange(2, n + 2), "x": x, "y": (x * 10 + rnd.uniform(0, 120, n)).round(3)})
    sc.loc[[5, 80, 300], "y"] = np.nan
    parquet(sc, "scatter.parquet")
    d = sc[["x", "y", "row_number"]].dropna()
    idx = np.linspace(0, len(d) - 1, 500).astype(int)
    gold["scatter"] = {"parquet": "scatter.parquet", "n": int(len(d)),
                       "points": [[float(a), float(b), int(r)] for a, b, r in zip(d["x"].iloc[idx], d["y"].iloc[idx], d["row_number"].iloc[idx])]}

    # real chart specs, to check that every kind the worker can produce has a renderer
    specs = {}
    for key, o in (("clean", out), ("messy", out2)):
        cs, _ = build_charts(o, compute_analytics(o))
        specs[key] = [{"key": c.key, "kind": c.kind, "placement": c.placement, "data": c.data, "options": c.options,
                       "query": c.query, "encoding": c.encoding} for c in cs]
    json.dump(jsonable(specs), open(os.path.join(OUT, "charts.json"), "w"), separators=(",", ":"))

    # everything the dashboard component needs, for the clean sales workbook
    from dataclasses import asdict
    res = compute_analytics(out)
    cs, _ = build_charts(out, res)
    t0 = out.tables[0]
    dash = {
        "table": {"id": "t1", "name": t0.name, "row_count": len(t0.rows), "artifact_path": "x", "position": 0},
        "columns": [{"id": c.name, "table_id": "t1", "position": c.position, "name": c.name, "data_type": c.data_type,
                     "role": c.role, "role_subtype": c.role_subtype, "distinct_count": c.distinct_count, "stats": c.stats}
                    for c in t0.columns],
        "charts": [{**asdict(c), "id": c.key, "table_id": "t1"} for c in cs if c.table_index == 0],
        "facts": [{"id": f.key, "table_id": "t1", "kind": f.kind, "headline": f.headline, "score": f.score, "payload": f.payload}
                  for f in res.facts if f.table_index == 0],
        "findings": out_summary_findings(out),
    }
    json.dump(jsonable(dash), open(os.path.join(OUT, "dashboard.json"), "w"), separators=(",", ":"))

    # Phase 5: real context, insights and answers produced by the worker, for the component tests
    schema = schema_from_output(out)
    frames = {t.name: out.frames[t.id] for t in out.tables}
    ctx = build_context(out, schema)
    ins, _ = build_insights(out, res.facts, None, False, schema)
    qa = QAContext(schema, frames)
    questions = ["What is the total sales?", "Which wilaya has the highest sales for Electronics?", "How does sales change over time?",
                 "Why did sales increase in September?", "show the largest orders", "what is the weather like?", "Which month saw the biggest drop?"]
    answers = [{"id": f"q{i}", "workbook_id": "w1", "text": q, "status": "answered", "created_at": "2026-10-10T10:00:00Z",
                "answer": answer_question(q, qa)} for i, q in enumerate(questions)]
    rows = [{"category": i.category, "priority": i.priority, "statement": i.statement, "next_check": i.next_check, "next_plan": i.next_plan} for i in ins]
    for k, q in enumerate(["What should I pay attention to?", "Find suspicious data"]):
        answers.append({"id": f"qh{k}", "workbook_id": "w1", "text": q, "status": "answered", "created_at": "2026-10-10T10:00:00Z",
                        "answer": highlights_answer(q, rows)})
    cs2, _ = build_charts(out, res)
    guide = build_guide(out, res.facts, cs2, schema, ctx)
    answers.append({"id": "qc", "workbook_id": "w1", "text": "What is the total", "status": "answered", "created_at": "2026-10-10T10:00:00Z",
                    "answer": {"status": "clarify", "text": "Which number do you mean?", "options": ["total_dzd", "quantity"], "plan": None, "result": None,
                               "chart": None, "caveats": [], "notes": [], "sample_rows": [], "followups": [], "source": {"plan": "rules", "text": "template"}}})
    json.dump(jsonable({"context": ctx, "guide": guide, "insights": [{"id": i.key, "table_id": None, "key": i.key, "category": i.category, "priority": i.priority,
                                                      "statement": i.statement, "interpretation": i.interpretation, "next_check": i.next_check,
                                                      "next_plan": i.next_plan, "caveats": i.caveats, "fact_keys": i.fact_keys, "source": i.source} for i in ins],
                        "answers": answers}), open(os.path.join(OUT, "ai.json"), "w"), separators=(",", ":"))

    json.dump(jsonable(gold), open(os.path.join(OUT, "golden.json"), "w"), separators=(",", ":"))
    print("golden written:", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
