"""Rule-based question planner: answers the common questions with no AI at all (and is the fallback when AI is off or fails)."""
import re

from ..engine import hints
from ..engine.textutil import norm_key
from ..engine.values import MONTHS
from .plan import SUMMABLE

OP_WORDS = {"agg", "group", "series", "compare", "contribution", "top_rows"}
GENERIC = {"total", "sum", "average", "mean", "count", "number", "top", "best", "worst", "most", "least", "highest", "lowest",
           "by", "per", "each", "the", "of", "in", "for", "what", "which", "how", "much", "many", "is", "are", "was", "were",
           "did", "do", "does", "show", "me", "our", "my", "all", "and", "to", "from", "with", "dzd", "da", "usd", "eur"}
CONTRIB = {"why", "drop", "dropped", "decrease", "decreased", "decline", "declined", "fell", "fall", "increase", "increased",
           "rise", "rose", "jump", "jumped", "driver", "drivers", "contributed", "contribute", "contribution", "contributors", "explain",
           "pourquoi", "baisse", "hausse", "chute"}
COMPARE = {"compare", "compared", "versus", "vs", "difference", "change", "changed", "previous", "comparer", "evolution", "variation"}
SERIES = {"trend", "trends", "monthly", "weekly", "daily", "yearly", "quarterly", "history", "evolve", "evolves", "evolved", "tendance"}
ROWS = {"rows", "transactions", "orders", "records", "lines", "entries", "lignes", "commandes"}
DESC = {"top", "best", "highest", "most", "biggest", "largest", "greatest", "meilleur", "plus"}
ASC = {"lowest", "least", "worst", "smallest", "bottom", "fewest", "moins", "pire"}
SUMW = {"total", "sum", "much", "somme", "totale"}
MEANW = {"average", "mean", "typical", "avg", "moyenne", "moyen"}
COUNTW = {"count", "many", "number", "combien", "nombre"}
PREDICT = {"forecast", "forecasts", "predict", "prediction", "predictions", "projection", "projections", "future", "estimate", "will",
           "prevision", "previsions", "prevoir", "prochain", "prochaine", "predire"}
NEXT_PERIOD = re.compile(r"\bnext (?:year|month|quarter|week|day)s?\b|\bgoing to\b|\bwhat if\b")
META = re.compile(
    r"\bhow (?:was|is|were|did|do|does) (?:this|that|it|you|these|those|the (?:answer|result|number))\s+(?:\w+\s+){0,2}?"
    r"(?:computed|calculated|calculate|compute|derived|work|works)\b|\bexplain (?:this|that|the) (?:answer|calculation|result)\b|"
    r"\bwhat does (?:this|that) mean\b|^\s*(?:help|aide)\s*\??\s*$", re.I)
SEGMENT_WORDS = {"segment", "segments", "breakdown", "split"}
GRAIN_WORDS = {"daily": "D", "day": "D", "weekly": "W", "week": "W", "monthly": "M", "month": "M", "quarterly": "Q", "quarter": "Q", "yearly": "Y", "year": "Y",
               "annual": "Y", "mois": "M", "semaine": "W", "jour": "D"}
SURE_MONTHS = {"janvier", "fevrier", "avril", "juin", "juillet", "aout", "septembre", "octobre", "novembre", "decembre", "january", "february",
               "march", "mars", "april", "june", "july", "august", "september", "october", "november", "december"}


def _toks(s: str) -> list:
    return norm_key(s).split()


def _name_score(col: dict, qt: set) -> float:
    ct = [t for t in hints.tokens(col["name"]) if t not in GENERIC]
    return (len(set(ct) & qt) / len(ct)) if ct else 0.0


def _pick_table(schema: dict, qt: set) -> dict:
    ts = schema["tables"]
    scored = sorted(ts, key=lambda t: (-sum(_name_score(c, qt) for c in t["columns"]) - (2 if set(hints.tokens(t["name"])) & qt else 0),
                                       not any(c["role"] == "measure" for c in t["columns"]), -t["rows"]))
    return scored[0]


def _measures(t: dict, qt: set):
    """(candidates, named_directly). Candidates found only through a synonym ("revenue" -> any amount column) may be ambiguous."""
    ms = [c for c in t["columns"] if c["role"] == "measure"]
    direct = [c for c in ms if _name_score(c, qt) > 0]
    if direct:
        return sorted(direct, key=lambda c: -_name_score(c, qt)), True
    groups = [(hints.QUANTITY, "quantity"), (hints.PRICE, "price"), (hints.AMOUNT, "amount"), (hints.RATE, "rate")]
    for vocab, sub in groups:
        if qt & vocab:
            hit = [c for c in ms if c["subtype"] == sub]
            if hit:
                return hit, False
    return [], False


def _dims(t: dict, qt: set) -> list:
    ds = [c for c in t["columns"] if c["role"] == "dimension"]
    direct = [c for c in ds if _name_score(c, qt) > 0]
    if direct:
        return sorted(direct, key=lambda c: -_name_score(c, qt))
    for vocab, sub in ((hints.LOCATION, "location"), (hints.PERSON, "person"), (hints.PRODUCT, "product"), (hints.STATUS, "status")):
        if qt & vocab:
            hit = [c for c in ds if c["subtype"] == sub]
            if hit:
                return hit
    return []


def _best_dim(t: dict) -> dict | None:
    ds = [c for c in t["columns"] if c["role"] == "dimension" and c["subtype"] in ("category", "product", "location", "status", "person")
          and 3 <= (c["distinct"] or 0) <= 30]
    return min(ds, key=lambda c: (c["subtype"] == "person", abs((c["distinct"] or 0) - 6)), default=None)


def _month(q: str, qt: list):
    """Month number and optional year mentioned in the question (only when unambiguous)."""
    year = next((int(x) for x in qt if re.fullmatch(r"(?:19|20)\d{2}", x)), None)
    for i, tok in enumerate(qt):
        m = MONTHS.get(tok)
        if not m:
            continue
        prep = i > 0 and qt[i - 1] in {"in", "of", "for", "during", "en", "de", "pour", "mois"}
        if tok in SURE_MONTHS or prep:
            return m, year
    return None, year


def _year_for(schema_t: dict, month: int, year: int | None):
    if year:
        return year
    tcol = next((c for c in schema_t["columns"] if c["role"] == "time" and c.get("min")), None)
    if not tcol:
        return None
    y0, y1 = int(tcol["min"][:4]), int(tcol["max"][:4])
    for y in range(y1, y0 - 1, -1):  # latest year that has this month
        lo, hi = f"{y}-{month:02d}", None
        if tcol["min"][:7] <= lo <= tcol["max"][:7]:
            return y
    return None


def is_meta(question: str) -> bool:
    """A question about the app or the last answer ("how was this computed?"), not about the data."""
    return bool(META.search(question or ""))


def rule_plan(question: str, schema: dict, frames: dict):
    """Returns a raw plan, {"clarify":..., "options":[...]}, or None when the question isn't understood."""
    ql = _toks(question)
    qt = set(ql)
    if not qt:
        return None
    if qt & PREDICT or NEXT_PERIOD.search(norm_key(question)):
        return {"unsupported": "I can describe what happened in your data, but I can't predict or forecast the future."}
    t = _pick_table(schema, qt)
    df = frames[t["name"]]
    (ms, named), ds = _measures(t, qt), _dims(t, qt)
    month, year = _month(question, ql)
    asc = bool(qt & ASC)
    want_group = bool(ds) or bool(qt & (hints.CATEGORY | SEGMENT_WORDS))  # "which segment...": a breakdown, by a sensible default column
    has_time = bool(t["time"])
    n = next((int(x) for i, x in enumerate(ql) if x.isdigit() and i > 0 and ql[i - 1] in ("top", "bottom", "first", "last") and 1 <= int(x) <= 20), None)

    if qt & CONTRIB:
        op = "contribution"
    elif want_group and qt & {"which", "what", "by", "per", "each"} and qt & (DESC | ASC) and not qt & {"show", "list", "display"}:
        op = "group"  # "which status has the most orders": a category ranking, not a list of rows
    elif qt & ROWS and (qt & (DESC | ASC) or "show" in qt or "list" in qt):
        op = "top_rows"
    elif qt & SERIES or ("over" in qt and "time" in qt) or ({"by", "per", "each"} & qt and qt & set(GRAIN_WORDS)):
        op = "series"
    elif qt & COMPARE or "last" in qt and "month" in qt or {"than", "from"} <= qt and month:
        op = "compare"
    elif want_group and (qt & (DESC | ASC) or {"by", "per", "each", "which", "what"} & qt):
        op = "group"
    elif ms or qt & (SUMW | MEANW | COUNTW):
        op = "agg"
    else:
        return None

    counting = bool(qt & COUNTW) or (op == "group" and bool(qt & ROWS) and not ms)  # "most orders" counts rows
    if len(ms) > 1 and not named:
        return {"clarify": "Which number do you mean?", "options": [c["name"] for c in ms]}
    measure = ms[0] if ms else None
    if measure is None and op in ("agg", "group", "series", "compare", "contribution", "top_rows") and not (op in ("agg", "group", "series") and counting):
        cands = [c for c in t["columns"] if c["role"] == "measure" and c["subtype"] in SUMMABLE]
        money = [c for c in cands if c["subtype"] == "amount"]
        if len(money) == 1:  # "largest", "total", "top" most naturally mean money
            cands = money
        if len(cands) == 1:
            measure = cands[0]
        elif len(cands) > 1:
            return {"clarify": "Which number do you mean?", "options": [c["name"] for c in cands]}
        else:
            return None
    plan = {"op": op, "table": t["name"], "measure": measure["name"] if measure else None, "order": "asc" if asc else "desc",
            "limit": n, "filters": []}
    if counting and not qt & (SUMW | MEANW):
        plan["agg"], plan["measure"] = "count", None
    elif qt & MEANW:
        plan["agg"] = "mean"
    elif qt & SUMW:
        plan["agg"] = "sum"

    if op in ("group", "contribution"):
        dim = ds[0] if ds else _best_dim(t)
        if dim is None:
            return {"clarify": "What should I break it down by?", "options": [c["name"] for c in t["columns"] if c["role"] == "dimension"][:6]}
        plan["dim"] = dim["name"]
        if not ds:  # no column was named: use the most sensible one and say so, instead of asking
            others = [c["name"] for c in t["columns"] if c["role"] == "dimension" and c["name"] != dim["name"] and (c["distinct"] or 0) <= 30][:4]
            plan["_assumption"] = f"You didn't name a category, so I broke it down by “{dim['name']}”." + (
                f" You can also ask by {', '.join(others)}." if others else "")
    if op in ("series", "compare", "contribution"):
        if not has_time:
            return None
        g = next((GRAIN_WORDS[w] for w in ql if w in GRAIN_WORDS), None)
        plan["grain"] = g or t["grain"] or "M"
        if month and plan["grain"] == "M" and op in ("compare", "contribution"):
            y = _year_for(t, month, year)
            if y is None:
                return None
            prev_y, prev_m = (y, month - 1) if month > 1 else (y - 1, 12)
            plan["periods"] = {"a": f"{prev_y:04d}-{prev_m:02d}", "b": f"{y:04d}-{month:02d}"}
    elif month and has_time:  # agg / group / top_rows: restrict to that month
        y = _year_for(t, month, year)
        if y:
            import calendar
            plan["filters"].append({"col": t["time"], "from": f"{y:04d}-{month:02d}-01",
                                    "to": f"{y:04d}-{month:02d}-{calendar.monthrange(y, month)[1]:02d}"})
    elif year and has_time and re.search(r"\b(?:in|during|for|en)\s+" + str(year) + r"\b", norm_key(question)):
        plan["filters"].append({"col": t["time"], "from": f"{year}-01-01", "to": f"{year}-12-31"})

    nq = " " + norm_key(question) + " "
    for c in t["columns"]:
        if c["role"] != "dimension" or c["name"] not in df.columns or c["name"] == plan.get("dim"):
            continue
        for v in df[c["name"]].astype("string").str.strip().dropna().unique()[:300]:
            k = norm_key(v)
            if len(k) >= 3 and f" {k} " in nq:
                plan["filters"].append({"col": c["name"], "values": [str(v)]})
                break
    return plan
