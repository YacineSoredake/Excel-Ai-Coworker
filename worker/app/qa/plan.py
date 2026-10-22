"""Plan validation. A plan is the only thing the LLM can produce, and it must pass every check here."""
import difflib
import re
from datetime import date

import pandas as pd

from ..engine.textutil import norm_key

OPS = {"agg", "group", "series", "compare", "contribution", "top_rows"}
AGGS = {"sum", "mean", "count", "median", "min", "max"}
SERIES_AGGS = {"sum", "mean", "count"}
GRAINS = {"D", "W", "M", "Q", "Y"}
SUMMABLE = {"amount", "quantity"}
NUMERIC = {"integer", "decimal", "currency", "percentage"}
PERIOD_RE = {"M": r"\d{4}-\d{2}", "D": r"\d{4}-\d{2}-\d{2}", "Q": r"\d{4}Q[1-4]", "Y": r"\d{4}", "W": r"\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}"}
MAX_FILTERS = 5


class PlanError(Exception):
    def __init__(self, code: str, message: str, suggestions: list | None = None):
        super().__init__(message)
        self.code, self.message, self.suggestions = code, message, suggestions or []


def _close(name: str, options: list[str]) -> list[str]:
    keyed = {norm_key(o): o for o in options}
    return [keyed[k] for k in difflib.get_close_matches(norm_key(name), list(keyed), n=3, cutoff=0.5)]


def _table(schema: dict, name) -> dict:
    ts = schema["tables"]
    if name in (None, ""):
        return max(ts, key=lambda t: (any(c["role"] == "measure" for c in t["columns"]), t["rows"]))
    for t in ts:
        if norm_key(t["name"]) == norm_key(name):
            return t
    raise PlanError("unknown_table", f"There is no table called “{name}”.", [t["name"] for t in ts])


def _col(t: dict, name, *, types=None, roles=None, what="column"):
    for c in t["columns"]:
        if norm_key(c["name"]) == norm_key(str(name)):
            if types and c["type"] not in types and c["role"] != "identifier":
                raise PlanError("wrong_type", f"“{c['name']}” is not a numeric column, so it can't be used as a {what}.")
            if roles and c["role"] not in roles:
                raise PlanError("wrong_role", f"“{c['name']}” can't be used as a {what} here.",
                                [x["name"] for x in t["columns"] if x["role"] in roles][:6])
            return c
    raise PlanError("unknown_column", f"There is no column called “{name}”.", _close(str(name), [c["name"] for c in t["columns"]]))


def _is_date(s) -> bool:
    try:
        date.fromisoformat(str(s))
        return True
    except ValueError:
        return False


def validate_plan(raw: dict, schema: dict, frames: dict) -> tuple[dict, list]:
    """Returns (clean plan, notes shown to the user) or raises PlanError."""
    if not isinstance(raw, dict):
        raise PlanError("bad_plan", "The question could not be understood.")
    notes: list[str] = []
    op = raw.get("op")
    if op not in OPS:
        raise PlanError("unsupported_op", "That kind of question isn't supported yet.")
    t = _table(schema, raw.get("table"))
    df = frames[t["name"]]
    plan = {"op": op, "table": t["name"], "measure": None, "agg": None, "dim": None, "time": None, "grain": None,
            "order": "asc" if raw.get("order") == "asc" else "desc", "limit": None, "filters": [], "periods": None}

    agg = raw.get("agg")
    if agg is not None and agg not in AGGS:
        raise PlanError("unsupported_agg", f"“{agg}” isn't a supported calculation. Use total, average, count, median, min or max.")
    m = raw.get("measure")
    mcol = None
    if m not in (None, ""):
        mcol = _col(t, m, types=NUMERIC, roles={"measure"}, what="measure")
        plan["measure"] = mcol["name"]
    needs_measure = op in ("contribution", "top_rows") or (op in ("agg", "group", "series", "compare") and agg not in (None, "count"))
    if needs_measure and mcol is None:
        raise PlanError("missing_measure", "Which number should I use?", [c["name"] for c in t["columns"] if c["role"] == "measure"][:6])
    if mcol is None and agg in (None, "count"):
        agg = "count"
    if mcol is not None and agg is None:
        agg = "sum" if mcol["subtype"] in SUMMABLE else "mean"
    if agg == "sum" and mcol is not None and mcol["subtype"] in ("price", "rate"):
        agg = "mean"
        notes.append(f"“{mcol['name']}” is a {'price' if mcol['subtype'] == 'price' else 'rate'}, so I averaged it instead of adding it up.")
    if op in ("series", "compare") and agg not in SERIES_AGGS:
        raise PlanError("unsupported_agg", "Over time I can show totals, averages or counts.")
    plan["agg"] = agg
    if op == "contribution":
        if mcol["subtype"] not in SUMMABLE and mcol["subtype"] != "generic":
            raise PlanError("wrong_type", "Contribution analysis needs an amount or a quantity, not a price or a rate.")
        plan["agg"] = "sum"

    if op in ("group", "contribution"):
        d = raw.get("dim")
        if d in (None, ""):
            raise PlanError("missing_dim", "Which category should I break it down by?",
                            [c["name"] for c in t["columns"] if c["role"] == "dimension"][:6])
        plan["dim"] = _col(t, d, roles={"dimension"}, what="category")["name"]
    if op in ("series", "compare", "contribution"):
        tc = raw.get("time") or t["time"]
        if not tc:
            raise PlanError("no_time", "This table has no date column, so I can't show changes over time.")
        plan["time"] = _col(t, tc, roles={"time"}, what="date column")["name"]
        g = raw.get("grain") or t["grain"] or "M"
        if g not in GRAINS:
            raise PlanError("bad_grain", "Use day, week, month, quarter or year.")
        plan["grain"] = g
        p = raw.get("periods")
        if p is not None:
            if not (isinstance(p, dict) and all(isinstance(p.get(k), str) and re.fullmatch(PERIOD_RE[g], p[k]) for k in "ab")):
                raise PlanError("bad_period", "I couldn't read the periods to compare.")
            plan["periods"] = {"a": p["a"], "b": p["b"]}
    lim = raw.get("limit")
    default = 10 if op == "top_rows" else 5
    plan["limit"] = max(1, min(20, int(lim))) if isinstance(lim, (int, float)) and not isinstance(lim, bool) else default

    filters = raw.get("filters") or []
    if not isinstance(filters, list) or len(filters) > MAX_FILTERS:
        raise PlanError("bad_filters", "Too many or malformed filters.")
    for f in filters:
        if not isinstance(f, dict):
            raise PlanError("bad_filters", "Malformed filter.")
        if "from" in f or "to" in f:
            c = _col(t, f.get("col") or plan["time"] or t["time"], roles={"time"}, what="date filter")
            fr, to = f.get("from"), f.get("to")
            for v in (fr, to):
                if v is not None and not _is_date(v):
                    raise PlanError("bad_date", f"“{v}” is not a valid date (use YYYY-MM-DD).")
            plan["filters"].append({"col": c["name"], "from": fr, "to": to})
        else:
            c = _col(t, f.get("col"), roles={"dimension"}, what="filter")
            vals = f.get("values")
            if not isinstance(vals, list) or not vals or len(vals) > 10:
                raise PlanError("bad_filters", f"Which values of “{c['name']}” should I keep?")
            have = {norm_key(v): v for v in df[c["name"]].astype("string").str.strip().dropna().unique()}
            clean = []
            for v in vals:
                k = norm_key(v)
                if k not in have:
                    raise PlanError("unknown_value", f"“{c['name']}” has no value “{v}”.", _close(str(v), list(have.values())))
                clean.append(have[k])
            plan["filters"].append({"col": c["name"], "values": clean})
    return plan, notes


def describe(plan: dict) -> str:
    """The plan in plain words, shown with every answer so the user can see what was actually computed."""
    agg = {"sum": "Total", "mean": "Average", "count": "Number of rows", "median": "Median", "min": "Smallest", "max": "Largest"}[plan["agg"] or "count"]
    what = f"{agg} of {plan['measure']}" if plan["measure"] else "Number of rows"
    op = plan["op"]
    if op == "group":
        s = f"{what} by {plan['dim']}, {'highest' if plan['order'] == 'desc' else 'lowest'} {plan['limit']}"
    elif op == "series":
        s = f"{what} by {plan['grain']}"
    elif op == "compare":
        s = f"{what}: {plan['periods']['b']} vs {plan['periods']['a']}" if plan["periods"] else f"{what}: latest two complete periods"
    elif op == "contribution":
        s = f"Change in {plan['measure']} between two periods, split by {plan['dim']}"
    elif op == "top_rows":
        s = f"{'Largest' if plan['order'] == 'desc' else 'Smallest'} {plan['limit']} rows by {plan['measure']}"
    else:
        s = what
    for f in plan["filters"]:
        s += f"; {f['col']} = {', '.join(f['values'])}" if "values" in f else f"; {f['col']} from {f['from'] or '…'} to {f['to'] or '…'}"
    return s
