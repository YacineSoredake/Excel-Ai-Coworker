"""End to end on an in-memory database: analysis -> insights -> a user turns AI on -> asks questions."""
import os

import pytest

import app.pipeline as pipeline
import app.questions as questions
from app.config import Settings
from app.questions import handle_question

from .fakedb import FakeDB
from .test_qa import FakeLLM

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
OWNER, WB = "user-1", "wb-1"


def settings(llm=None, phrase=True):
    return Settings(supabase_url="x", service_key="k", max_file_bytes=10 * 1024 * 1024, poll_interval=1, llm=llm, ai_phrase_answers=phrase)


def analysed(llm=None, ai=False, fixture="01_sales_clean.xlsx"):
    db = FakeDB()
    db.files[("workbooks", f"{OWNER}/{WB}/original.xlsx")] = open(os.path.join(FIX, fixture), "rb").read()
    db.t["workbooks"].append({"id": WB, "user_id": OWNER})
    if ai:
        db.t["user_settings"].append({"user_id": OWNER, "ai_enabled": True})
    job = {"job_id": "j1", "wb_id": WB, "owner_id": OWNER, "path": f"{OWNER}/{WB}/original.xlsx", "name": "x.xlsx", "attempts": 1}
    pipeline.run_job(db, settings(llm), job)
    return db


def ask(db, text, plan=None, llm=None, attempts=1):
    q = {"q_id": f"q{len(db.t['questions'])}", "wb_id": WB, "owner_id": OWNER, "q_text": text, "q_plan": plan, "q_attempts": attempts}
    db.t["questions"].append({"id": q["q_id"], "workbook_id": WB, "user_id": OWNER, "text": text, "status": "answering"})
    handle_question(db, settings(llm), q)
    return next(r for r in db.t["questions"] if r["id"] == q["q_id"])


@pytest.fixture(autouse=True)
def clear_cache():
    questions._cache.clear()


class TestAnalysisStep:
    def test_context_and_builtin_insights_are_stored_without_any_ai(self):
        db = analysed()
        assert db.statuses()[-1] == "profiled"
        ctx = db.t["workbook_profiles"][0]["context"]
        assert ctx["domain"]["key"] == "sales" and len(ctx["suggested_questions"]) >= 4
        ins = db.t["insights"]
        assert 3 <= len(ins) <= 7 and {i["source"] for i in ins} == {"template"}
        assert all(i["workbook_id"] == WB and i["user_id"] == OWNER and i["statement"] for i in ins)
        stats = [u["analytics"] for n, u in db.log if n == "workbook_profiles" and "analytics" in u][-1]
        assert stats["ai_requested"] is False and stats["domain"] == "sales"

    def test_ai_is_used_only_when_the_user_opted_in(self):
        llm = FakeLLM({"insights": []})
        analysed(llm, ai=False)
        assert llm.sent == []  # provider configured, user has not consented: nothing leaves
        llm = FakeLLM({"insights": []})
        analysed(llm, ai=True)
        assert len(llm.sent) == 1

    def test_no_provider_configured_means_no_ai_even_if_the_user_opted_in(self):
        db = analysed(None, ai=True)
        assert {i["source"] for i in db.t["insights"]} == {"template"}

    def test_insight_failure_does_not_lose_the_profile_or_charts(self, monkeypatch):
        monkeypatch.setattr(pipeline, "build_insights", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        db = analysed()
        assert db.statuses()[-1] == "profiled" and db.t["charts"] and db.t["facts"] and "insights" not in db.t
        stats = [u["analytics"] for n, u in db.log if n == "workbook_profiles" and "analytics" in u][-1]
        assert stats["insights_error"] == "internal_error"


class TestQuestions:
    def test_a_typed_question_is_answered_from_the_stored_tables(self):
        db = analysed()
        row = ask(db, "What is the total sales?")
        a = row["answer"]
        assert row["status"] == "answered" and a["status"] == "ok" and "7,196,350 DZD" in a["text"]
        assert a["source"]["plan"] == "rules" and a["chart"]["kind"] == "kpi"

    def test_suggested_questions_and_insight_follow_ups_run_without_ai(self):
        db = analysed()
        ctx = db.t["workbook_profiles"][0]["context"]
        for sq in ctx["suggested_questions"]:
            r = ask(db, sq["text"], sq["plan"])
            assert r["answer"]["status"] == "ok", sq["text"]
        for ins in db.t["insights"]:
            if ins["next_plan"]:
                assert ask(db, ins["next_check"], ins["next_plan"])["answer"]["status"] == "ok", ins["next_check"]

    def test_a_forged_plan_from_the_browser_is_validated_like_any_other(self):
        db = analysed()
        for bad in ({"op": "agg", "measure": "../../etc/passwd", "agg": "sum"}, {"op": "run_sql"}, {"op": "agg", "table": "Nope", "measure": "total_dzd"}):
            a = ask(db, "anything", bad)["answer"]
            assert a["status"] == "unsupported", bad

    def test_the_users_ai_choice_is_respected_at_question_time(self):
        db = analysed()
        llm = FakeLLM({"op": "agg", "measure": "total_dzd", "agg": "sum"}, {"answer": "Total total_dzd: 7,196,350 DZD, over 339 rows."})
        assert ask(db, "total please", llm=llm)["answer"]["source"]["plan"] == "rules" and llm.sent == []
        db.t["user_settings"].append({"user_id": OWNER, "ai_enabled": True})
        a = ask(db, "How much money overall?", llm=llm)["answer"]
        assert a["source"]["plan"] == "ai" and a["source"]["text"] == "ai" and len(llm.sent) == 2

    def test_another_users_workbook_is_not_reachable(self):
        db = analysed()
        q = {"q_id": "qx", "wb_id": "someone-elses", "owner_id": OWNER, "q_text": "total sales", "q_plan": None, "q_attempts": 2}
        db.t["questions"].append({"id": "qx", "status": "answering"})
        handle_question(db, settings(), q)
        r = next(r for r in db.t["questions"] if r["id"] == "qx")
        assert r["status"] == "failed" and r["answer"]["status"] == "error" and "someone" not in str(r["answer"])

    def test_a_crash_is_retried_once_then_reported_without_details(self, monkeypatch):
        db = analysed()
        monkeypatch.setattr(questions, "answer_question", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("secret internals")))
        r = ask(db, "total sales", attempts=1)
        assert r["status"] == "queued"  # goes back in the queue
        r = ask(db, "total sales", attempts=2)
        assert r["status"] == "failed" and "secret" not in str(r)

    def test_workbooks_are_cached_between_questions_and_reloaded_after_reanalysis(self):
        db = analysed()
        ask(db, "total sales")
        downloads = {"n": 0}
        orig = db.storage.from_

        class Counting:
            def __init__(self, s): self.s = s
            def download(self, p): downloads["n"] += 1; return self.s.download(p)
        db.storage = type("S", (), {"from_": lambda s, b: Counting(orig(b))})()
        ask(db, "total quantity")
        assert downloads["n"] == 0  # served from cache
        pipeline.run_job(db, settings(), {"job_id": "j2", "wb_id": WB, "owner_id": OWNER, "path": f"{OWNER}/{WB}/original.xlsx", "name": "x", "attempts": 1})
        ask(db, "total quantity")
        assert downloads["n"] >= 1  # new table ids: reloaded


def test_a_question_cannot_read_a_workbook_owned_by_someone_else():
    db = analysed()  # workbook wb-1 belongs to user-1 and its tables are fully loaded
    q = {"q_id": "qy", "wb_id": WB, "owner_id": "attacker", "q_text": "What is the total sales?", "q_plan": None, "q_attempts": 2}
    db.t["questions"].append({"id": "qy", "status": "answering"})
    handle_question(db, settings(), q)
    r = next(r for r in db.t["questions"] if r["id"] == "qy")
    assert r["status"] == "failed" and r["answer"]["status"] == "error" and "7,196,350" not in str(r["answer"])


def test_ai_wording_of_answers_is_off_unless_asked_for(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.delenv("AI_PHRASE_ANSWERS", raising=False)
    assert Settings.load().ai_phrase_answers is False  # measured: the AI adds nothing to the wording and costs a call
    monkeypatch.setenv("AI_PHRASE_ANSWERS", "true")
    assert Settings.load().ai_phrase_answers is True
    monkeypatch.setenv("AI_PHRASE_ANSWERS", "true   ")  # a trailing space in .env must not silently turn it off
    assert Settings.load().ai_phrase_answers is True


def test_with_wording_off_the_ai_is_called_once_per_question():
    db = analysed()
    db.t["user_settings"].append({"user_id": OWNER, "ai_enabled": True})
    llm = FakeLLM({"op": "agg", "measure": "total_dzd", "agg": "sum"})
    q = {"q_id": "qz", "wb_id": WB, "owner_id": OWNER, "q_text": "How much money overall?", "q_plan": None, "q_attempts": 1}
    db.t["questions"].append({"id": "qz", "status": "answering"})
    handle_question(db, settings(llm, phrase=False), q)
    a = next(r for r in db.t["questions"] if r["id"] == "qz")["answer"]
    assert a["source"]["plan"] == "ai" and a["source"]["text"] == "template" and len(llm.sent) == 1
