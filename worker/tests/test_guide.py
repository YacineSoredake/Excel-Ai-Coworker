"""Guide Me: an ordered path from verified facts, where every button runs and nothing claims a cause."""
import json
import os

import pytest

import app.pipeline as pipeline
from app.ai.claims import CAUSAL, Evidence, check_text
from app.analytics.run import compute_analytics
from app.charts.run import build_charts
from app.context.infer import build_context
from app.engine.analyze import analyze_workbook
from app.guide.build import build_guide
from app.qa.highlights import highlights_answer, is_attention
from app.qa.run import QAContext, answer_question
from app.qa.schema import schema_from_output

from .fakedb import FakeDB
from .helpers import build
from .test_flow import OWNER, WB, analysed, ask, clear_cache, settings  # noqa: F401
from .test_qa import FakeLLM, load

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def prep(name):
    out = analyze_workbook(open(os.path.join(FIX, name), "rb").read())
    res = compute_analytics(out)
    charts, _ = build_charts(out, res)
    schema = schema_from_output(out)
    ctx = build_context(out, schema)
    return out, res, charts, schema, ctx, build_guide(out, res.facts, charts, schema, ctx)


def ids(g):
    return [s["id"] for s in g["steps"]]


class TestPath:
    def test_the_sales_file_gets_the_tour_from_the_report(self):
        *_, g = prep("01_sales_clean.xlsx")
        assert ids(g) == ["overview", "sources", "change", "unusual", "target", "next"]
        by = {s["id"]: s for s in g["steps"]}
        assert "7,196,350 DZD" in by["overview"]["narrative"] and "339 records" in by["overview"]["narrative"]
        assert "2026-01-04" in by["overview"]["narrative"]
        assert by["unusual"]["narrative"].endswith("not conclusions.") and "+93%" in by["unusual"]["narrative"]
        assert [a["kind"] for a in by["next"]["actions"]][-1] == "ask_tab"

    def test_the_messy_file_adds_a_data_quality_step_and_shows_caveats(self):
        *_, g = prep("02_messy_ventes_fr.xlsx")
        assert ids(g) == ["overview", "sources", "change", "unusual", "quality", "next"]
        by = {s["id"]: s for s in g["steps"]}
        assert any("extreme" in n for n in by["sources"]["notes"])  # the 99% share is driven by one extreme value: say so
        assert by["quality"]["actions"][0]["kind"] == "details" and "duplicate" in by["quality"]["narrative"]

    def test_steps_adapt_to_the_data(self):
        def f(wb):
            ws = wb.active
            ws.append(["produit", "region", "montant"])
            for i in range(60):
                ws.append([f"P{i % 6}", ["N", "S"][i % 2], 10.0 + i])
        out = analyze_workbook(build(f))
        res = compute_analytics(out)
        charts, _ = build_charts(out, res)
        schema = schema_from_output(out)
        g = build_guide(out, res.facts, charts, schema, build_context(out, schema))
        assert ids(g) == ["overview", "sources", "next"]  # no dates: no "over time" or "unusual month" steps, and nothing invented

    def test_structure_is_stable(self):
        for name in ("01_sales_clean.xlsx", "02_messy_ventes_fr.xlsx"):
            out, res, charts, schema, ctx, g = prep(name)
            assert g["steps"][0]["id"] == "overview" and g["steps"][-1]["id"] == "next" and len(set(ids(g))) == len(ids(g))
            chart_keys, fact_keys = {c.key for c in charts}, {f.key for f in res.facts}
            for s in g["steps"]:
                assert s["title"] and s["narrative"] and 0 <= s["value"] <= 1
                assert set(s["chart_keys"]) <= chart_keys and set(s["fact_keys"]) <= fact_keys, s["id"]
            json.dumps(g, allow_nan=False)
            assert prep(name)[-1] == g  # deterministic


class TestEveryButtonRuns:
    @pytest.mark.parametrize("name", ["01_sales_clean.xlsx", "02_messy_ventes_fr.xlsx"])
    def test_actions_are_answered_and_verified(self, name):
        out, res, charts, schema, ctx, g = prep(name)
        _, frames = load(name)
        n = 0
        for s in g["steps"]:
            for a in s["actions"]:
                if a["kind"] != "ask":
                    assert a["plan"] is None and a["kind"] in ("details", "ask_tab")
                    continue
                r = answer_question(a["text"], QAContext(schema, frames), a["plan"])
                assert r["status"] == "ok", (s["id"], a["label"], r["text"])
                n += 1
        assert n >= 6

    def test_inspecting_a_period_returns_the_rows_of_that_period(self):
        out, res, charts, schema, ctx, g = prep("01_sales_clean.xlsx")
        _, frames = load("01_sales_clean.xlsx")
        act = next(a for a in next(s for s in g["steps"] if s["id"] == "unusual")["actions"] if "Inspect" in a["label"])
        assert act["plan"]["filters"] == [{"col": "date", "from": "2026-05-01", "to": "2026-05-31"}]
        r = answer_question(act["text"], QAContext(schema, frames), act["plan"])
        dates = {row[1] for row in r["result"]["data"]["rows"]}
        assert r["result"]["kind"] == "table" and all(d.startswith("2026-05") for d in dates)


class TestHonestWording:
    @pytest.mark.parametrize("name", ["01_sales_clean.xlsx", "02_messy_ventes_fr.xlsx"])
    def test_narratives_are_traceable_and_never_causal(self, name):
        out, res, charts, schema, ctx, g = prep(name)
        ev = Evidence(texts=[f.headline for f in res.facts] + [f.definition for f in res.facts] +
                      [f"{ctx['time']['from']} {ctx['time']['to']}", out.tables[0].name] + [c.name for t in out.tables for c in t.columns],
                      data=[f.payload for f in res.facts] + [{"records": len(out.tables[0].rows)}])
        for s in g["steps"]:
            assert not CAUSAL.search(s["narrative"]), s["narrative"]
            for sentence in [x.strip() for x in s["narrative"].split(". ") if x.strip()]:
                issues = [i for i in check_text(sentence, ev).issues if i not in ("not_a_sentence", "too_long")]
                assert not issues, (s["id"], sentence, issues)

    def test_unusual_step_describes_patterns_not_explanations(self):
        *_, g = prep("01_sales_clean.xlsx")
        assert "not conclusions" in next(s for s in g["steps"] if s["id"] == "unusual")["narrative"]


class TestAttentionQuestions:
    @pytest.mark.parametrize("q", ["What should I pay attention to?", "what stands out", "Find suspicious data", "anything unusual?",
                                   "Is there anything wrong with this data", "find anomalies", "Qu'est-ce qui ressort ?", "points d'attention"])
    def test_recognised(self, q):
        assert is_attention(q), q

    @pytest.mark.parametrize("q", ["What is the total sales?", "Which wilaya has the highest sales?", "how did sales change", "show the largest orders"])
    def test_data_questions_are_not_mistaken_for_attention_questions(self, q):
        assert not is_attention(q), q

    def test_answered_from_the_stored_insights_without_ai(self):
        db = analysed()
        llm = FakeLLM()
        general = ask(db, "What should I pay attention to?", llm=llm)["answer"]
        assert general["status"] == "ok" and general["result"]["kind"] == "highlights" and llm.sent == []
        items = general["result"]["data"]["items"]
        assert 3 <= len(items) <= 5 and items[0]["statement"] and "not explanations" in general["text"]
        asked = [i["next_check"] for i in items if i["next_check"]]
        assert len(asked) == len(set(asked))  # the same next question is never offered twice
        stored = {i["statement"] for i in db.t["insights"]}
        assert {i["statement"] for i in items} <= stored  # nothing invented: only what was already verified
        sus = ask(db, "Find suspicious data")["answer"]
        assert {i["category"] for i in sus["result"]["data"]["items"]} <= {"anomaly", "consistency", "quality"}
        assert "not conclusions" in sus["text"]

    def test_a_repeated_next_question_is_shown_once(self):
        rows = [{"category": "trend", "priority": k, "statement": f"s{k}", "next_check": "Which category contributed most?",
                 "next_plan": {"op": "contribution", "measure": "m"}} for k in (1, 2, 3)]
        items = highlights_answer("what stands out", rows)["result"]["data"]["items"]
        assert [i["next_check"] for i in items] == ["Which category contributed most?", "", ""]
        assert items[1]["next_plan"] is None

    def test_an_honest_empty_answer(self):
        a = highlights_answer("find suspicious data", [{"category": "trend", "priority": 1, "statement": "x", "next_check": "", "next_plan": None}])
        assert a["result"]["data"]["items"] == [] and a["text"].startswith("Nothing looks suspicious")
        assert highlights_answer("what stands out", [])["text"] == "Nothing in particular stands out in this workbook."

    def test_follow_ups_from_highlights_are_runnable_plans(self):
        db = analysed()
        a = ask(db, "What should I pay attention to?")["answer"]
        for fu in a["followups"]:
            assert ask(db, fu["text"], fu["plan"])["answer"]["status"] == "ok", fu["text"]


class TestPipeline:
    def test_the_guide_is_stored_with_the_profile(self):
        db = analysed()
        guide = db.t["workbook_profiles"][0]["guide"]
        assert [s["id"] for s in guide["steps"]][0] == "overview" and guide["table"] == "Sales"
        stats = [u["analytics"] for n, u in db.log if n == "workbook_profiles" and "analytics" in u][-1]
        assert stats["guide_steps"] == len(guide["steps"])

    def test_a_guide_failure_loses_nothing_else(self, monkeypatch):
        monkeypatch.setattr(pipeline, "build_guide", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        db = analysed()
        assert db.statuses()[-1] == "profiled" and db.t["charts"] and db.t["insights"]
        stats = [u["analytics"] for n, u in db.log if n == "workbook_profiles" and "analytics" in u][-1]
        assert stats["guide_error"] == "internal_error" and "guide" not in db.t["workbook_profiles"][0]
