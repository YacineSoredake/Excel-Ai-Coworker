"""Answers queued questions. Everything the browser sends is untrusted: the plan is re-validated, the result re-verified."""
import io
import logging
import time
from datetime import datetime, timezone

import pandas as pd
from supabase import Client

from .config import Settings
from .persist import _native
from .qa.highlights import highlights_answer, is_attention
from .qa.run import QAContext, answer_question
from .qa.schema import make_schema

log = logging.getLogger("worker.questions")
ARTIFACTS = "artifacts"
TTL = 300
_cache: dict = {}  # workbook_id -> (loaded_at, table_ids, schema, frames)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_workbook(client: Client, workbook_id: str) -> tuple[dict, dict]:
    tabs = client.table("data_tables").select("id, name, artifact_path, row_count, position").eq("workbook_id", workbook_id).execute().data or []
    ids = tuple(sorted(t["id"] for t in tabs))
    hit = _cache.get(workbook_id)
    if hit and time.time() - hit[0] < TTL and hit[1] == ids:
        return hit[2], hit[3]
    if not tabs:
        raise LookupError("no_tables")
    cols = client.table("column_profiles").select("table_id, name, data_type, role, role_subtype, currency, distinct_count, stats, position") \
        .eq("workbook_id", workbook_id).execute().data or []
    entries, frames = [], {}
    for t in sorted(tabs, key=lambda x: x["position"]):
        raw = client.storage.from_(ARTIFACTS).download(t["artifact_path"])
        df = pd.read_parquet(io.BytesIO(raw))
        frames[t["name"]] = df
        entries.append({"id": t["id"], "name": t["name"], "rows": t["row_count"], "frame": df,
                        "columns": sorted((c for c in cols if c["table_id"] == t["id"]), key=lambda c: c["position"])})
    schema = make_schema(entries)
    if len(_cache) >= 4:
        _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
    _cache[workbook_id] = (time.time(), ids, schema, frames)
    return schema, frames


def _ai_enabled(client: Client, user_id: str) -> bool:
    try:
        rows = client.table("user_settings").select("ai_enabled").eq("user_id", user_id).execute().data or []
        return bool(rows and rows[0].get("ai_enabled"))
    except Exception:
        return False


def handle_question(client: Client, settings: Settings, q: dict) -> None:
    qid = q["q_id"]
    log.info("question_start q=%s attempt=%s", qid, q["q_attempts"])  # ids only: never the question text
    try:
        # defense in depth: this process bypasses row-level security, so ownership is checked here as well
        own = client.table("workbooks").select("id").eq("id", q["wb_id"]).eq("user_id", q["owner_id"]).execute().data
        if not own:
            raise PermissionError("not_owner")
        if q.get("q_plan") is None and is_attention(q["q_text"]):
            rows = client.table("insights").select("category, priority, statement, next_check, next_plan").eq("workbook_id", q["wb_id"]).execute().data or []
            answer = _native(highlights_answer(q["q_text"], rows))
            client.table("questions").update({"status": "answered", "answer": answer, "answered_at": _now(), "error": None}).eq("id", qid).execute()
            return
        schema, frames = load_workbook(client, q["wb_id"])
        ai_on = settings.llm is not None and _ai_enabled(client, q["owner_id"])
        ctx = QAContext(schema, frames, settings.llm if ai_on else None, ai_on, settings.ai_phrase_answers)
        answer = _native(answer_question(q["q_text"], ctx, q.get("q_plan")))
        client.table("questions").update({"status": "answered", "answer": answer, "answered_at": _now(), "error": None}).eq("id", qid).execute()
        log.info("question_done q=%s status=%s", qid, answer["status"])
    except Exception as e:
        log.error("question_error q=%s type=%s", qid, type(e).__name__)
        final = q["q_attempts"] >= 2
        msg = {"status": "error", "text": "Something went wrong while answering. Please try again.", "plan": None, "result": None,
               "chart": None, "caveats": [], "notes": [], "followups": [], "source": {"plan": None, "text": "template"}}
        upd = {"status": "failed", "answer": msg, "answered_at": _now(), "error": "internal_error"} if final else {"status": "queued", "error": "internal_error"}
        try:
            client.table("questions").update(upd).eq("id", qid).execute()
        except Exception:
            pass
