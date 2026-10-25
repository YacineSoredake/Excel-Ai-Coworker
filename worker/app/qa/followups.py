"""Suggested questions. Each carries a ready plan, so it can be answered with no AI."""
from .plan import SERIES_AGGS, SUMMABLE
from .schema import main_table


def _main_measure(t: dict):
    ms = [c for c in t["columns"] if c["role"] == "measure"]
    for sub in ("amount", "quantity"):
        hit = [c for c in ms if c["subtype"] == sub]
        if hit:
            return hit[0]
    return ms[0] if ms else None


def _best_dim(t: dict):
    ds = [c for c in t["columns"] if c["role"] == "dimension" and c["subtype"] in ("category", "product", "location", "status", "person")
          and 3 <= (c["distinct"] or 0) <= 30]
    return min(ds, key=lambda c: (c["subtype"] == "person", abs((c["distinct"] or 0) - 6)), default=None)


def initial_suggestions(schema: dict) -> list:
    t = main_table(schema)
    m, d = _main_measure(t), _best_dim(t)
    out = []
    if m:
        label = (m["name"] if m["name"].lower().startswith("total") else f"total {m['name']}") if m["subtype"] in SUMMABLE else f"average {m['name']}"
        out.append({"text": f"What is the {label}?",
                    "plan": {"op": "agg", "table": t["name"], "measure": m["name"]}})
    if m and d:
        out.append({"text": f"Which {d['name']} has the highest {m['name']}?",
                    "plan": {"op": "group", "table": t["name"], "measure": m["name"], "dim": d["name"], "limit": 5}})
    if m and t["time"]:
        out.append({"text": f"How does {m['name']} change over time?", "plan": {"op": "series", "table": t["name"], "measure": m["name"]}})
        out.append({"text": f"What changed in {m['name']} compared with the previous period?",
                    "plan": {"op": "compare", "table": t["name"], "measure": m["name"]}})
        if d and m["subtype"] in SUMMABLE:
            out.append({"text": f"Which {d['name']} contributed most to the latest change in {m['name']}?",
                        "plan": {"op": "contribution", "table": t["name"], "measure": m["name"], "dim": d["name"]}})
    if m:
        out.append({"text": f"Which rows have the largest {m['name']}?", "plan": {"op": "top_rows", "table": t["name"], "measure": m["name"], "limit": 10}})
    return out[:6]


def followups(plan: dict, res, schema: dict) -> list:
    t = next(x for x in schema["tables"] if x["name"] == plan["table"])
    m, d = plan["measure"], _best_dim(t)
    agg = plan["agg"] if plan["agg"] in SERIES_AGGS else "sum"
    out = []
    if res.kind == "group" and m and t["time"]:
        gs = [g for g in res.data["groups"] if not g.get("muted")]
        if gs:
            out.append({"text": f"How does {m} change over time for {gs[0]['label']}?",
                        "plan": {"op": "series", "table": t["name"], "measure": m, "agg": agg, "filters": [{"col": plan["dim"], "values": [gs[0]["label"]]}]}})
    if res.kind in ("series", "compare") and m and t["time"] and d and plan["agg"] == "sum":
        out.append({"text": f"Which {d['name']} contributed most to the latest change in {m}?",
                    "plan": {"op": "contribution", "table": t["name"], "measure": m, "dim": d["name"], "grain": plan.get("grain")}})
    if res.kind == "contribution" and m and t["time"]:
        gs = res.data["groups"]
        if gs:
            out.append({"text": f"How does {m} change over time for {gs[0]['label']}?",
                        "plan": {"op": "series", "table": t["name"], "measure": m, "agg": "sum", "filters": [{"col": plan["dim"], "values": [gs[0]["label"]]}]}})
    if res.kind in ("agg", "table") and m and d:
        out.append({"text": f"Which {d['name']} has the highest {m}?", "plan": {"op": "group", "table": t["name"], "measure": m, "dim": d["name"], "limit": 5}})
    if res.kind in ("agg", "group") and m and t["time"] and not any(f["col"] == t["time"] for f in plan["filters"]):
        out.append({"text": f"What changed in {m} compared with the previous period?", "plan": {"op": "compare", "table": t["name"], "measure": m, "agg": agg}})
    return out[:3]
