"""Write the engine output to Postgres (profile tables) and Storage (cleaned Parquet)."""
import io
import json
import uuid

from supabase import Client

from .engine.models import EngineOutput

ARTIFACTS = "artifacts"
CHUNK = 400


def _native(x):
    """JSON round-trip guarantees plain python types (no numpy, no datetimes)."""
    return json.loads(json.dumps(x, default=str, allow_nan=False)) if x is not None else None


def _insert(client: Client, table: str, rows: list) -> None:
    for i in range(0, len(rows), CHUNK):
        client.table(table).insert(rows[i:i + CHUNK]).execute()


def _remove_folder(client: Client, bucket: str, prefix: str) -> None:
    store = client.storage.from_(bucket)
    try:
        items = store.list(prefix, {"limit": 1000})
    except Exception:
        return
    paths = [f"{prefix}/{i['name']}" for i in items if i.get("id")]
    if paths:
        store.remove(paths)


def save_profile(client: Client, user_id: str, workbook_id: str, out: EngineOutput) -> None:
    # idempotent: wipe any previous profile first (children cascade from sheets / data_tables)
    client.table("sheets").delete().eq("workbook_id", workbook_id).execute()
    client.table("findings").delete().eq("workbook_id", workbook_id).execute()
    client.table("workbook_profiles").delete().eq("workbook_id", workbook_id).execute()
    prefix = f"{user_id}/{workbook_id}/tables"
    _remove_folder(client, ARTIFACTS, prefix)

    base = {"workbook_id": workbook_id, "user_id": user_id}
    sheet_ids = {s["name"]: str(uuid.uuid4()) for s in out.sheets}
    _insert(client, "sheets", [
        {**base, "id": sheet_ids[s["name"]], "position": s["position"], "name": s["name"], "hidden": s["hidden"],
         "row_count": s["row_count"], "column_count": s["column_count"], "cell_count": s["cell_count"],
         "formula_count": s["formula_count"], "error_count": s["error_count"], "merged_count": s["merged_count"],
         "hyperlink_count": s["hyperlink_count"], "is_empty": s["is_empty"], "notes": _native(s["notes"])}
        for s in out.sheets])

    # cleaned tables -> Parquet (compact, typed) in the artifacts bucket
    store = client.storage.from_(ARTIFACTS)
    paths = {}
    for t in out.tables:
        buf = io.BytesIO()
        # snappy + millisecond timestamps: readable by the browser (hyparquet) without extra codecs
        out.frames[t.id].to_parquet(buf, index=False, compression="snappy", coerce_timestamps="ms",
                                    allow_truncated_timestamps=True)
        path = f"{prefix}/{t.id}.parquet"
        store.upload(path, buf.getvalue(), {"content-type": "application/octet-stream", "upsert": "true"})
        paths[t.id] = path

    _insert(client, "data_tables", [
        {**base, "id": t.id, "sheet_id": sheet_ids[t.sheet], "position": t.index, "name": t.name, "source": t.source,
         "cell_range": t.cell_range, "header_row": t.header_row, "first_data_row": t.first_data_row,
         "last_data_row": t.last_data_row, "row_count": len(t.rows), "column_count": len(t.columns),
         "confidence": t.confidence, "header_confidence": t.header_conf, "total_rows": t.total_rows,
         "blank_rows": t.blank_rows, "truncated": t.truncated, "artifact_path": paths[t.id]}
        for t in out.tables])

    col_ids, col_rows = {}, []
    for t in out.tables:
        for c in t.columns:
            cid = str(uuid.uuid4())
            col_ids[(t.index, c.position)] = cid
            n = max(1, c.n_rows)
            col_rows.append({
                **base, "id": cid, "table_id": t.id, "position": c.position, "col_letter": c.letter, "name": c.name,
                "original_label": c.original_label, "data_type": c.data_type, "base_type": c.base_type,
                "type_confidence": c.type_confidence, "role": c.role, "role_subtype": c.role_subtype,
                "role_confidence": c.role_confidence, "currency": c.currency, "unit": c.unit,
                "number_format": c.number_format, "formula_share": c.formula_share,
                "missing_count": c.missing_count, "missing_rate": round(c.missing_count / n, 4),
                "distinct_count": c.distinct_count, "uniqueness": c.uniqueness,
                "stats": _native({**c.stats, **({"outliers": c.outliers} if c.outliers else {})})})
    _insert(client, "column_profiles", col_rows)

    by_index = {t.index: t for t in out.tables}
    _insert(client, "findings", [
        {**base, "sheet_id": sheet_ids.get(f.sheet), "table_id": by_index[f.table_index].id if f.table_index is not None else None,
         "column_id": col_ids.get((f.table_index, f.column_pos)) if f.column_pos is not None else None,
         "code": f.code, "severity": f.severity, "title": f.title, "detail": f.detail,
         "affected_count": f.affected, "total_count": f.total, "sample_rows": f.sample_rows,
         "evidence": _native(f.evidence)} for f in out.findings])

    client.table("workbook_profiles").insert({
        **base, "profile_version": out.summary["profile_version"], "summary": _native(out.summary),
        "relationships": _native(out.relationships), "engine_ms": out.engine_ms}).execute()


def save_facts(client: Client, user_id: str, workbook_id: str, out: EngineOutput, result) -> None:
    """Facts reference tables by index in the engine output; map them to the saved table ids."""
    client.table("facts").delete().eq("workbook_id", workbook_id).execute()
    base = {"workbook_id": workbook_id, "user_id": user_id}
    table_ids = {t.index: t.id for t in out.tables}
    rows = [{
        **base, "table_id": table_ids.get(f.table_index), "kind": f.kind, "key": f.key, "rank": rank,
        "title": f.title, "headline": f.headline, "definition": f.definition, "measure": f.measure,
        "dimension": f.dimension, "time_column": f.time_column, "agg": f.agg,
        "payload": _native(f.payload), "spec": _native(f.spec), "source": _native(f.source),
        "caveats": _native(f.caveats), "sample_rows": [int(r) for r in f.sample_rows],
        "usefulness": f.usefulness, "reliability": f.reliability, "score": f.score, "verified": f.verified,
    } for rank, f in enumerate(result.facts, start=1)]
    _insert(client, "facts", rows)


def save_analytics_status(client: Client, workbook_id: str, stats: dict) -> None:
    client.table("workbook_profiles").update({"analytics": _native(stats)}).eq("workbook_id", workbook_id).execute()


def save_charts(client: Client, user_id: str, workbook_id: str, out: EngineOutput, charts: list) -> None:
    client.table("charts").delete().eq("workbook_id", workbook_id).execute()
    table_ids = {t.index: t.id for t in out.tables}
    base = {"workbook_id": workbook_id, "user_id": user_id}
    _insert(client, "charts", [{
        **base, "table_id": table_ids.get(c.table_index), "key": c.key, "kind": c.kind, "role": c.role,
        "placement": c.placement, "position": c.position, "title": c.title, "why": c.why,
        "fact_keys": _native(c.fact_keys), "encoding": _native(c.encoding), "data": _native(c.data),
        "query": _native(c.query), "options": _native(c.options), "usefulness": c.usefulness,
        "reliability": c.reliability, "readability": c.readability, "score": c.score,
        "caveats": _native(c.caveats)} for c in charts])


def save_context_and_insights(client: Client, user_id: str, workbook_id: str, out: EngineOutput, context: dict, insights: list) -> None:
    client.table("workbook_profiles").update({"context": _native(context)}).eq("workbook_id", workbook_id).execute()
    client.table("insights").delete().eq("workbook_id", workbook_id).execute()
    table_ids = {t.index: t.id for t in out.tables}
    base = {"workbook_id": workbook_id, "user_id": user_id}
    _insert(client, "insights", [{
        **base, "table_id": table_ids.get(i.table_index), "key": i.key, "category": i.category, "priority": i.priority,
        "statement": i.statement, "interpretation": i.interpretation, "next_check": i.next_check, "next_plan": _native(i.next_plan),
        "fact_keys": _native(i.fact_keys), "finding_codes": _native(i.finding_codes), "caveats": _native(i.caveats), "source": i.source}
        for i in insights])


def save_guide(client: Client, workbook_id: str, guide: dict) -> None:
    client.table("workbook_profiles").update({"guide": _native(guide)}).eq("workbook_id", workbook_id).execute()
