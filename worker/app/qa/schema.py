"""What the planner (and the LLM) may know about a workbook: names, types, roles, and category labels. Never rows."""
import pandas as pd

from ..analytics.periods import choose_grain

MAX_VALUES = 30


def make_schema(tables: list[dict]) -> dict:
    """tables: [{name, id, rows, columns: [{name, data_type, role, role_subtype, currency, distinct_count, stats}], frame}]."""
    out = []
    for t in tables:
        df = t["frame"]
        cols, time_col = [], None
        for c in t["columns"]:
            e = {"name": c["name"], "type": c["data_type"], "role": c["role"], "subtype": c.get("role_subtype"),
                 "currency": c.get("currency"), "distinct": c.get("distinct_count"), "values": None, "private": False}
            if c["role"] == "dimension" and c["name"] in df.columns and (c.get("distinct_count") or 0) <= MAX_VALUES:
                if c.get("role_subtype") == "person":
                    e["private"] = True  # people's names are never sent to an AI provider
                else:
                    vc = df[c["name"]].astype("string").str.strip().value_counts()
                    e["values"] = [str(v) for v in vc.index[:MAX_VALUES]]
            if c["role"] == "time" and c["name"] in df.columns:
                d = df[c["name"]].dropna()
                if len(d):
                    e["min"], e["max"] = d.min().date().isoformat(), d.max().date().isoformat()
                    if time_col is None:
                        time_col = (c["name"], choose_grain(d.min(), d.max()))
            cols.append(e)
        out.append({"id": t.get("id"), "name": t["name"], "rows": t["rows"], "columns": cols,
                    "time": time_col[0] if time_col else None, "grain": time_col[1] if time_col else None})
    return {"tables": out}


def schema_for_llm(schema: dict) -> dict:
    """The only workbook information that can leave the server: names, types, roles, non-personal category labels."""
    def col(c):
        d = {"name": c["name"], "type": c["type"], "role": c["role"], "subtype": c["subtype"]}
        if c.get("currency"):
            d["currency"] = c["currency"]
        if c.get("values"):
            d["values"] = c["values"]
        if c.get("min"):
            d["range"] = [c["min"], c["max"]]
        return d
    return {"tables": [{"name": t["name"], "rows": t["rows"], "time_column": t["time"], "default_grain": t["grain"],
                        "columns": [col(c) for c in t["columns"] if c["role"] != "ignore"]} for t in schema["tables"]]}


def main_table(schema: dict) -> dict:
    return max(schema["tables"], key=lambda t: (any(c["role"] == "measure" for c in t["columns"]), t["rows"]))


def schema_from_output(out) -> dict:
    """Schema straight from the engine output (used right after analysis; at question time it is rebuilt from the database)."""
    return make_schema([{"id": t.id, "name": t.name, "rows": len(t.rows), "frame": out.frames[t.id], "columns": [
        {"name": c.name, "data_type": c.data_type, "role": c.role, "role_subtype": c.role_subtype, "currency": c.currency,
         "distinct_count": c.distinct_count, "stats": c.stats} for c in t.columns]} for t in out.tables])
