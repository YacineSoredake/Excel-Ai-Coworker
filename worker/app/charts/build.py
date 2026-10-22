"""Phase F for charts: map verified facts to candidate chart specs (report §5 table)."""
import numpy as np

from ..analytics.model import Fact
from ..analytics.numfmt import num
from ..analytics.periods import GRAIN_NAME
from ..engine.models import EngineOutput
from .model import ChartSpec

SCATTER_LIMIT = 500


def _enc(f: Fact, **extra) -> dict:
    return {"measure": f.measure, "dim": f.dimension, "time": f.time_column, **extra}


def _rd(kind: str, n: int = 0, extra: float = 1.0) -> float:
    """Readability of a chart type for this amount of data (§5: bars for rankings, no pies for many categories)."""
    if kind == "line":
        return 1.0 if 4 <= n <= 60 else 0.85
    if kind == "hbar":
        return 1.0 if n <= 10 else 0.9
    if kind == "donut":
        return 0.85 if 2 <= n <= 5 else 0.0
    if kind == "stacked_bar":
        return 0.9 if n <= 6 else 0.8
    if kind == "multi_line":
        return 0.85
    if kind == "scatter":
        return 0.9
    if kind == "histogram":
        return 0.85
    return 1.0


def _label(f: Fact) -> str:
    return "the number of records" if f.measure is None else (
        f"total {f.measure}" if f.agg == "sum" else f"average {f.measure}")


def _finish(c: ChartSpec, f: Fact, readability: float) -> ChartSpec:
    c.usefulness, c.reliability, c.readability = f.usefulness, f.reliability, round(readability, 3)
    c.score = round(c.usefulness * c.reliability * c.readability, 4)
    c.caveats = list(f.caveats)
    return c


def build_candidates(out: EngineOutput, facts: list[Fact]) -> list[ChartSpec]:
    cands: list[ChartSpec] = []
    by_kind: dict[str, list[Fact]] = {}
    for f in facts:
        by_kind.setdefault(f.kind, []).append(f)

    def find(kind, table, measure, time=None):
        return next((x for x in by_kind.get(kind, []) if x.table_index == table and x.measure == measure
                     and (time is None or x.time_column == time)), None)

    # ---- KPI cards
    for f in by_kind.get("kpi", []):
        if f.agg == "count":
            label, fmt = "Records", "number"
        elif f.agg == "sum":
            label, fmt = f"Total {f.measure}", "currency" if f.payload.get("currency") else "number"
        else:
            label, fmt = f"Average {f.measure}", "currency" if f.payload.get("currency") else "number"
        pc = find("period_change", f.table_index, f.measure) if f.agg in ("sum", "count") else None
        delta = None
        if pc:
            delta = {"pct": pc.payload["change_pct"], "abs": pc.payload["change_abs"],
                     "latest": pc.payload["latest"]["period"], "previous": pc.payload["previous"]["period"]}
        q = {"op": "agg", "agg": f.agg, "measure": f.measure}
        if pc:
            q["delta"] = {"time": pc.time_column, "grain": pc.payload["grain"]}
        cands.append(_finish(ChartSpec(
            key=f"chart:kpi:{f.key}", kind="kpi", role="kpi", table_index=f.table_index, title=f.title,
            why="A single number that summarizes the whole table.", fact_keys=[f.key], encoding=_enc(f),
            data={"label": label, "value": f.payload["value"], "format": fmt, "currency": f.payload.get("currency"),
                  "delta": delta, "median": f.payload.get("median")}, query=q), f, 1.0))
    for f in by_kind.get("target", []):
        cands.append(_finish(ChartSpec(
            key=f"chart:kpi:{f.key}", kind="kpi", role="kpi", table_index=f.table_index, title=f.title,
            why="Shows how far actual values are from the target.", fact_keys=[f.key],
            encoding=_enc(f, variant="target"),
            data={"label": f"Reached of {f.payload['target_column']}", "value": f.payload["attainment"], "format": "percent",
                  "currency": None, "delta": None,
                  "sub": f"{f.payload['matched_periods']} months compared"}, query=None), f, 1.0))

    # ---- trends (+ annotations from swing / unusual periods)
    for f in by_kind.get("trend", []):
        p = f.payload
        items = p["periods"]
        notes = []
        sw = find("swing", f.table_index, f.measure, f.time_column)
        if sw:
            notes.append({"period": sw.payload["to"]["period"], "label": f"Largest change {sw.payload['change_pct'] * 100:+.0f}%",
                          "kind": "swing"})
        an = find("anomaly_period", f.table_index, f.measure, f.time_column)
        for fl in (an.payload["flagged"] if an else []):
            notes.append({"period": fl["period"], "label": "Unusual", "kind": "unusual"})
        gname = GRAIN_NAME[p["grain"]]
        why = (f"A line shows how {_label(f)} moves from one {gname} to the next, so rises, falls and turning points are visible. "
               + (f"{len(p['excluded_partial'])} incomplete {gname}(s) are drawn dashed and not compared." if p["excluded_partial"] else ""))
        cands.append(_finish(ChartSpec(
            key=f"chart:line:{f.key}", kind="line", role="trend", table_index=f.table_index, title=f.title, why=why.strip(),
            fact_keys=[f.key] + [x.key for x in (sw, an) if x], encoding=_enc(f),
            data={"x": [i["period"] for i in items], "y": [i["value"] for i in items],
                  "rows": [i["rows"] for i in items], "complete": [i["complete"] for i in items]},
            query={"op": "series", "time": f.time_column, "grain": p["grain"], "measure": f.measure, "agg": f.agg},
            options={"currency": p.get("currency"), "grain": p["grain"], "direction": p["direction"],
                     "annotations": notes}), f, _rd("line", len(items))))

    # ---- rankings -> horizontal bars (and a donut when the whole is meaningful)
    for f in by_kind.get("ranking", []):
        p = f.payload
        groups = [{"label": g["label"], "value": g["value"], "share": g["share"], "rows": g["rows"]} for g in p["groups"]]
        if p["other"]:
            groups.append({"label": f"Other ({p['other']['n_groups']})", "value": p["other"]["value"],
                           "share": p["other"]["share"], "rows": None, "muted": True})
        q = {"op": "group", "dim": f.dimension, "measure": f.measure, "agg": p["agg"], "limit": 10,
             "min_group": f.spec.get("min_group", 0)}
        # bars by default (precise comparison); a donut is offered as a switch only when the whole is meaningful (§5)
        alt = ["donut"] if (p["composition_suitable"] and 2 <= p["n_groups"] <= 5) else []
        cands.append(_finish(ChartSpec(
            key=f"chart:hbar:{f.key}", kind="hbar", role="comparison", table_index=f.table_index, title=f.title,
            why="Bars on a common scale make the biggest and smallest groups easy to compare precisely.",
            fact_keys=[f.key], encoding=_enc(f), query=q,
            data={"groups": groups, "n_groups": p["n_groups"], "total": p["total"]},
            options={"currency": p.get("currency"), "agg": p["agg"], "additive": p["agg"] in ("sum", "count"),
                     "alt_kinds": alt}), f, _rd("hbar", p["n_groups"])))
    # ---- breakdown over time
    for f in by_kind.get("breakdown", []):
        p = f.payload
        stacked = len(p["periods"]) <= 12
        kind = "stacked_bar" if stacked else "multi_line"
        cands.append(_finish(ChartSpec(
            key=f"chart:{kind}:{f.key}", kind=kind, role="breakdown", table_index=f.table_index, title=f.title,
            why=("Stacked bars show both the total for each period and how much each group contributes."
                 if stacked else "One line per group shows how each group moves over time."),
            fact_keys=[f.key], encoding=_enc(f),
            data={"x": p["periods"], "series": [{"label": s["label"], "values": s["values"]} for s in p["series"]]},
            query={"op": "breakdown", "time": f.time_column, "grain": p["grain"], "measure": f.measure,
                   "dim": f.dimension, "top": 5},
            options={"currency": p.get("currency"), "grain": p["grain"]}), f, _rd(kind, len(p["series"]))))

    # ---- target
    for f in by_kind.get("target", []):
        p = f.payload
        cands.append(_finish(ChartSpec(
            key=f"chart:target:{f.key}", kind="target", role="target", table_index=f.table_index, title=f.title,
            why="Bars for actual values against a line for the target show where each month fell short or went over.",
            fact_keys=[f.key], encoding=_enc(f),
            data={"x": [r["period"] for r in p["periods"]], "actual": [r["actual"] for r in p["periods"]],
                  "target": [r["target"] for r in p["periods"]], "attainment": p["attainment"]},
            query=None, options={"currency": p.get("currency"), "target_column": p["target_column"]}), f, 0.95))

    # ---- relationships between measures -> scatter
    tables = {t.index: t for t in out.tables}
    for f in by_kind.get("correlation", []):
        t = tables[f.table_index]
        a, b = f.spec["a"], f.spec["b"]
        d = out.frames[t.id][[a, b, "row_number"]].dropna()
        idx = np.linspace(0, len(d) - 1, min(len(d), SCATTER_LIMIT)).astype(int)
        s = d.iloc[idx]
        cands.append(_finish(ChartSpec(
            key=f"chart:scatter:{f.key}", kind="scatter", role="relationship", table_index=f.table_index, title=f.title,
            why="Each dot is one row. A scatter plot shows whether two numbers rise together, and where the exceptions are.",
            fact_keys=[f.key], encoding={"measure": a, "dim": None, "time": None, "x": a, "y": b},
            data={"points": [[num(x), num(y), int(r)] for x, y, r in zip(s[a], s[b], s["row_number"])],
                  "n": int(len(d)), "rho": f.payload["rho"], "sampled": len(s) < len(d)},
            query={"op": "scatter", "x": a, "y": b, "limit": SCATTER_LIMIT},
            options={"x": a, "y": b}), f, _rd("scatter")))

    # ---- distribution of the most important summed measure
    for t in out.tables:
        kp = [f for f in by_kind.get("kpi", []) if f.table_index == t.index and f.agg == "sum"]
        if not kp:
            continue
        f = max(kp, key=lambda x: x.usefulness)
        col = next((c for c in t.columns if c.name == f.measure), None)
        h = col.stats.get("histogram") if col else None
        if h and len(col.values) >= 30:
            cands.append(_finish(ChartSpec(
                key=f"chart:histogram:{f.key}", kind="histogram", role="distribution", table_index=t.index,
                title=f"How are {f.measure} values spread?",
                why="Shows how often small and large values occur; a long tail means a few very large values.",
                fact_keys=[f.key], encoding=_enc(f), data={"edges": h["edges"], "counts": h["counts"]},
                query={"op": "histogram", "measure": f.measure, "bins": 10},
                options={"currency": f.payload.get("currency")}), f, _rd("histogram")))
            cands[-1].usefulness = round(cands[-1].usefulness * 0.45, 3)  # secondary: explore only
            cands[-1].score = round(cands[-1].usefulness * cands[-1].reliability * cands[-1].readability, 4)
    return cands
