"""Guide Me (report §7): the workbook's highest-value opportunities as an ordered path that a user can follow or skip.

Built only from verified facts, charts, findings and insights: no AI, no new calculation. Every button carries a plan that
the Ask engine validates and verifies, so a step can never send the user somewhere that cannot be answered.
Wording describes patterns and never claims causes (§6.3).
"""
from ..analytics.numfmt import pct
from ..analytics.periods import period_range
from ..engine.models import EngineOutput
from ..qa.followups import _best_dim, _main_measure
from ..qa.schema import main_table

GUIDE_VERSION = 1
MIN_UNUSUAL_SCORE = 0.3
SEVERITY_RANK = {"high": 0, "medium": 1}
CAUTION = " These are patterns to check, not conclusions."


def _notes(*facts) -> list:
    out = []
    for f in facts:
        for c in (f.caveats if f else []):
            if c not in out:
                out.append(c)
    return out[:3]


def _act(label: str, text: str | None, plan: dict | None, kind: str = "ask") -> dict:
    return {"label": label, "kind": kind, "text": text, "plan": plan}


def _chart(charts, ti: int, fact_key: str, kinds: set):
    return next((c.key for c in charts if c.table_index == ti and c.fact_keys[:1] == [fact_key] and c.kind in kinds), None)


def _other_dim(t: dict, not_this: str | None):
    ds = [c for c in t["columns"] if c["role"] == "dimension" and c["subtype"] in ("category", "product", "location", "status")
          and 3 <= (c["distinct"] or 0) <= 30 and c["name"] != not_this]
    return min(ds, key=lambda c: abs((c["distinct"] or 0) - 6), default=None)


def build_guide(out: EngineOutput, facts: list, charts: list, schema: dict, context: dict | None) -> dict:
    t = main_table(schema)
    ti = next(i for i, x in enumerate(out.tables) if x.name == t["name"])
    F = [f for f in facts if f.table_index == ti]
    m = _main_measure(t)
    mn = m["name"] if m else None
    dim = _best_dim(t)
    tname = t["name"]
    steps = []

    # 1. the big picture
    tm = (context or {}).get("time")
    total = next((f for f in F if f.kind == "kpi" and f.measure == mn and f.agg == "sum"), None)
    text = f"This table has {len(out.tables[ti].rows):,} records" + (f", from {tm['from']} to {tm['to']}" if tm and tm.get("from") else "") + "."
    if total:
        text += f" {total.headline}."
    steps.append({"id": "overview", "kind": "overview", "title": "Let's understand the big picture", "narrative": text,
                  "chart_keys": [c.key for c in charts if c.table_index == ti and c.placement == "kpi"],
                  "fact_keys": [total.key] if total else [], "notes": _notes(total), "actions": [], "value": 1.0})

    # 2. where it comes from
    ranks = ([f for f in F if f.kind == "ranking" and f.measure == mn and f.agg == "sum"]
             or [f for f in F if f.kind == "ranking" and f.agg in ("sum", "count")])
    if ranks:
        r = max(ranks, key=lambda f: f.score)
        p = r.payload
        top = p["groups"][0]["label"]
        text = r.headline + "."
        if p["top3_share"] is not None and p["n_groups"] > 3:
            text += f" The top 3 account for {pct(p['top3_share'])} of the total."
        if (p["top1_share"] or 0) >= 0.5:
            text += " One group holds most of it."
        acts = []
        if t["time"] and r.measure:
            acts.append(_act(f"Explore {top}", f"How does {r.measure} change over time for {top}?",
                             {"op": "series", "table": tname, "measure": r.measure, "agg": "sum", "filters": [{"col": r.dimension, "values": [top]}]}))
        other = _other_dim(t, r.dimension)
        if other:
            acts.append(_act(f"Compare by {other['name']}", f"Which {other['name']} has the highest {r.measure or 'number of rows'}?",
                             {"op": "group", "table": tname, "measure": r.measure, "agg": "sum" if r.measure else "count", "dim": other["name"], "limit": 5}))
        steps.append({"id": "sources", "kind": "sources", "title": "Now let's see where it comes from", "narrative": text,
                      "chart_keys": [k for k in [_chart(charts, ti, r.key, {"hbar"})] if k], "fact_keys": [r.key], "notes": _notes(r), "actions": acts, "value": r.score})

    # 3. how it changed
    tr = next((f for f in F if f.kind == "trend" and f.measure == mn and mn), None)
    if tr:
        pc = next((f for f in F if f.kind == "period_change" and f.measure == mn and f.time_column == tr.time_column), None)
        text = tr.headline + "." + (f" {pc.headline}." if pc else "")
        acts = []
        if dim:
            acts.append(_act("What contributed to the latest change?", f"Which {dim['name']} contributed most to the latest change in {mn}?",
                             {"op": "contribution", "table": tname, "measure": mn, "dim": dim["name"]}))
        acts.append(_act("Compare the latest two periods", f"What changed in {mn} compared with the previous period?",
                         {"op": "compare", "table": tname, "measure": mn, "agg": "sum"}))
        steps.append({"id": "change", "kind": "change", "title": "How has it changed over time?", "narrative": text,
                      "chart_keys": [k for k in [_chart(charts, ti, tr.key, {"line"})] if k],
                      "fact_keys": [tr.key] + ([pc.key] if pc else []), "notes": _notes(tr, pc), "actions": acts, "value": tr.score})

    # 4. something unusual
    cands = [f for f in F if (f.kind in ("swing", "anomaly_period", "anomaly_values") or (f.kind == "derivation" and f.payload["mismatch_count"]))
             and f.measure in (mn, None)]
    best = max(cands, key=lambda f: f.score, default=None)
    if best is not None and best.score >= MIN_UNUSUAL_SCORE and mn:
        acts, chart_keys = [], []

        def inspect(period=None, grain=None, label="Inspect the largest rows"):
            plan = {"op": "top_rows", "table": tname, "measure": mn, "limit": 10}
            rng = period_range(period, grain) if period and best.time_column else None
            if rng:
                plan["filters"] = [{"col": best.time_column, "from": rng[0], "to": rng[1]}]
                return _act(f"Inspect transactions in {period}", f"Which rows have the largest {mn} in {period}?", plan)
            return _act(label, f"Which rows have the largest {mn}?", plan)

        if best.kind in ("swing", "anomaly_period"):
            trend = next((f for f in F if f.kind == "trend" and f.measure == best.measure and f.time_column == best.time_column), None)
            chart_keys = [k for k in [trend and _chart(charts, ti, trend.key, {"line"})] if k]
            g = best.payload["grain"]
            if best.kind == "swing":
                a, b = best.payload["from"]["period"], best.payload["to"]["period"]
                if dim and best.agg == "sum":
                    acts.append(_act(f"What contributed to {a} → {b}?", f"Which {dim['name']} contributed most to the change in {mn} between {a} and {b}?",
                                     {"op": "contribution", "table": tname, "measure": mn, "dim": dim["name"], "grain": g, "periods": {"a": a, "b": b}}))
                acts.append(inspect(b, g))
            else:
                acts.append(inspect(best.payload["flagged"][0]["period"], g))
        else:
            acts.append(inspect())
        steps.append({"id": "unusual", "kind": "unusual", "title": "There's something unusual", "narrative": best.headline + "." + CAUTION,
                      "chart_keys": chart_keys, "fact_keys": [best.key], "notes": _notes(best), "actions": acts, "value": best.score})

    # 5. against target
    tg = next((f for f in F if f.kind == "target"), None)
    if tg:
        steps.append({"id": "target", "kind": "target", "title": "Are you on track?", "narrative": tg.headline + ".",
                      "chart_keys": [k for k in [_chart(charts, ti, tg.key, {"target"})] if k], "fact_keys": [tg.key], "notes": _notes(tg), "actions": [], "value": tg.score})

    # 6. data quality
    fnd = sorted((f for f in out.findings if f.severity in SEVERITY_RANK and f.table_index in (ti, None) and f.code != "header_uncertain"),
                 key=lambda f: (SEVERITY_RANK[f.severity], -(f.affected or 0)))[:3]
    if fnd:
        listed = "; ".join(f.title.replace("Potential issue: ", "") for f in fnd)
        steps.append({"id": "quality", "kind": "quality", "title": "Check the data before relying on it",
                      "narrative": f"Before relying on the totals, check: {listed}.", "chart_keys": [], "fact_keys": [], "notes": [],
                      "actions": [_act("Review the issues", None, None, kind="details")], "value": 0.6})

    # 7. where to go next
    used = {a["text"] for s in steps for a in s["actions"]}
    nxt = [q for q in (context or {}).get("suggested_questions", []) if q["text"] not in used][:3]
    acts = [_act(q["text"], q["text"], q["plan"]) for q in nxt] + [_act("Ask your own question", None, None, kind="ask_tab")]
    steps.append({"id": "next", "kind": "next", "title": "Where to go next", "narrative": "That's the tour. These questions are good places to continue.",
                  "chart_keys": [], "fact_keys": [], "notes": [], "actions": acts, "value": 0.5})
    return {"version": GUIDE_VERSION, "table": tname, "table_index": ti, "steps": steps}
