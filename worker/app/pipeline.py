"""Pipeline: download -> checksum -> validate (phase 1) -> understand + profile (phase 2) -> verified facts (phase 3) -> chart specs (phase 4) -> context + insights (phase 5).

Later phases plug in after profiling (analytics, charts, insights, ...).
"""
import hashlib
import logging
from datetime import datetime, timezone

from supabase import Client

from .config import Settings
from .engine.analyze import analyze_workbook
from .engine.context import Limits
from .analytics.run import compute_analytics
from .charts.run import build_charts
from .context.infer import build_context
from .insights.build import build_insights
from .persist import save_analytics_status, save_charts, save_context_and_insights, save_facts, save_profile
from .qa.schema import schema_from_output
from .validate import Rejected, inspect_xlsx

log = logging.getLogger("worker.pipeline")
BUCKET = "workbooks"
MAX_ATTEMPTS = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ai_enabled(client: Client, user_id: str) -> bool:
    try:
        rows = client.table("user_settings").select("ai_enabled").eq("user_id", user_id).execute().data or []
        return bool(rows and rows[0].get("ai_enabled"))
    except Exception:
        return False  # when in doubt, no AI


def run_job(client: Client, settings: Settings, job: dict) -> None:
    job_id, wb_id = job["job_id"], job["wb_id"]
    # Log ids only. Never filenames or cell contents.
    log.info("job_start job=%s attempt=%s", job_id, job["attempts"])

    try:
        client.table("workbooks").update({"status": "validating"}).eq("id", wb_id).execute()
        data = client.storage.from_(BUCKET).download(job["path"])
        sha = hashlib.sha256(data).hexdigest()
        info = inspect_xlsx(data, settings.max_file_bytes)

        client.table("workbooks").update(
            {
                "sha256": sha,
                "sheet_count": info.sheet_count,
                "hidden_sheets": info.hidden_sheets,
                "has_external_links": info.has_external_links,
                "status": "analyzing",
                "rejection_reason": None,
            }
        ).eq("id", wb_id).execute()

        # Phase 2: understand the workbook (deterministic, no LLM)
        limits = Limits(settings.max_cells, settings.max_table_rows, settings.analysis_timeout)
        out = analyze_workbook(data, limits, info.has_external_links)
        save_profile(client, job["owner_id"], wb_id, out)

        # Phase 3: verified facts. Isolated: if this fails, the profile above is still usable.
        try:
            result = compute_analytics(out, settings.analysis_timeout)
            save_facts(client, job["owner_id"], wb_id, out, result)
            stats = result.stats
            # Phase 4: chart specs from the verified facts. Isolated again: facts stay usable if this fails.
            try:
                charts, cstats = build_charts(out, result)
                save_charts(client, job["owner_id"], wb_id, out, charts)
                stats = {**stats, **cstats, "charts": len(charts)}
            except Rejected as r:
                stats = {**stats, "charts_error": r.code}
            except Exception as e:
                log.error("charts_error job=%s type=%s", job_id, type(e).__name__)
                stats = {**stats, "charts_error": "internal_error"}
                try:
                    client.table("charts").delete().eq("workbook_id", wb_id).execute()
                except Exception:
                    pass
            # Phase 5: workbook context + insights. AI wording only if this user opted in and a provider is configured.
            try:
                ai_on = _ai_enabled(client, job["owner_id"]) and settings.llm is not None
                schema = schema_from_output(out)
                context = build_context(out, schema)
                insights, istats = build_insights(out, result.facts, settings.llm if ai_on else None, ai_on, schema)
                save_context_and_insights(client, job["owner_id"], wb_id, out, context, insights)
                stats = {**stats, **istats, "domain": context["domain"]["key"], "ai_configured": settings.llm is not None}
            except Rejected as r:
                stats = {**stats, "insights_error": r.code}
            except Exception as e:
                log.error("insights_error job=%s type=%s", job_id, type(e).__name__)
                stats = {**stats, "insights_error": "internal_error"}
        except Rejected as r:
            stats = {"error": r.code}
        except Exception as e:
            log.error("analytics_error job=%s type=%s", job_id, type(e).__name__)
            stats = {"error": "internal_error"}
        if stats.get("error"):
            try:
                client.table("facts").delete().eq("workbook_id", wb_id).execute()  # never leave partial facts
            except Exception:
                pass
        save_analytics_status(client, wb_id, stats)

        client.table("workbooks").update({"status": "profiled"}).eq("id", wb_id).execute()
        client.table("analysis_jobs").update(
            {"status": "done", "finished_at": _now(), "error": None}
        ).eq("id", job_id).execute()
        log.info("job_done job=%s", job_id)

    except Rejected as r:
        client.table("workbooks").update(
            {"status": "rejected", "rejection_reason": r.message}
        ).eq("id", wb_id).execute()
        client.table("analysis_jobs").update(
            {"status": "failed", "finished_at": _now(), "error": r.code}
        ).eq("id", job_id).execute()
        log.info("job_rejected job=%s code=%s", job_id, r.code)

    except Exception as e:  # unexpected: retry up to MAX_ATTEMPTS
        log.error("job_error job=%s type=%s", job_id, type(e).__name__)
        if job["attempts"] >= MAX_ATTEMPTS:
            client.table("workbooks").update(
                {"status": "failed", "rejection_reason": "Processing failed. Please try uploading again."}
            ).eq("id", wb_id).execute()
            client.table("analysis_jobs").update(
                {"status": "failed", "finished_at": _now(), "error": "internal_error"}
            ).eq("id", job_id).execute()
        else:
            client.table("analysis_jobs").update(
                {"status": "queued", "error": "internal_error"}
            ).eq("id", job_id).execute()
