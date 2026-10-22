import json
import os

import pytest

from app.analytics.run import compute_analytics
from app.ai.llm import LLMError
from app.context.infer import build_context, infer_domain
from app.engine.analyze import analyze_workbook
from app.insights.build import build_insights
from app.qa.run import QAContext, answer_question
from app.qa.schema import make_schema

from .helpers import build
from .test_qa import FakeLLM, load

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def prep(name):
    out = analyze_workbook(open(os.path.join(FIX, name), "rb").read())
    schema, frames = load(name)
    return out, compute_analytics(out), schema, frames


class TestContext:
    def test_sales_workbook_is_recognised_with_its_evidence(self):
        out, res, schema, _ = prep("01_sales_clean.xlsx")
        c = build_context(out, schema)
        assert c["domain"]["key"] == "sales" and c["domain"]["confidence"] >= 0.6
        assert {"product", "quantity"} <= set(c["domain"]["evidence"])  # the guess shows what it is based on
        assert c["time"]["from"] == "2026-01-04" and c["time"]["to"] == "2026-09-27" and c["time"]["granularity"] in ("daily", "weekly")
        kinds = {e["kind"] for e in c["entities"]}
        assert {"product", "location", "category"} <= kinds
        assert any("DZD" in a for a in c["assumptions"]) and any("inferred" in a for a in c["assumptions"])
        assert "Progress against targets or budgets" in c["potential_analyses"]
        assert len(c["suggested_questions"]) >= 4 and all(q["plan"]["op"] for q in c["suggested_questions"])

    def test_french_messy_workbook_and_stated_assumptions(self):
        out, _, schema, _ = prep("02_messy_ventes_fr.xlsx")
        c = build_context(out, schema)
        assert c["domain"]["key"] == "sales"
        assert any("day/month" in a for a in c["assumptions"]) and any("Duplicate" in a for a in c["assumptions"])
        assert "Data-quality review before relying on totals" in c["potential_analyses"]

    def test_unclear_workbooks_say_so(self):
        def f(wb):
            ws = wb.active
            ws.append(["alpha", "beta", "gamma"])
            for i in range(15):
                ws.append([f"a{i % 3}", i, i * 2.5])
        out = analyze_workbook(build(f))
        d = infer_domain(out)
        assert d["key"] == "generic"
        c = build_context(out, make_schema([{"id": t.id, "name": t.name, "rows": len(t.rows), "frame": out.frames[t.id], "columns": [
            {"name": c.name, "data_type": c.data_type, "role": c.role, "role_subtype": c.role_subtype, "currency": c.currency,
             "distinct_count": c.distinct_count, "stats": c.stats} for c in t.columns]} for t in out.tables]))
        assert c["uncertainty"] and "no clear match" in c["uncertainty"]

    def test_every_suggested_question_is_answerable(self):
        out, _, schema, frames = prep("01_sales_clean.xlsx")
        for q in build_context(out, schema)["suggested_questions"]:
            assert answer_question(q["text"], QAContext(schema, frames), q["plan"])["status"] == "ok", q["text"]


class TestInsightsWithoutAI:
    def test_builtin_insights_are_traceable_and_capped(self):
        out, res, schema, _ = prep("01_sales_clean.xlsx")
        ins, st = build_insights(out, res.facts)
        assert 3 <= len(ins) <= 7 and st["ai_requested"] is False and all(i.source == "template" for i in ins)
        keys = {f.key for f in res.facts}
        for i in ins:
            assert i.statement and (set(i.fact_keys) <= keys)
            assert i.next_check
        assert [i.priority for i in ins] == list(range(1, len(ins) + 1))
        cats = [i.category for i in ins]
        assert "target" in cats and cats.count("concentration") + cats.count("contributors") <= 4

    def test_messy_workbook_surfaces_data_quality_and_the_inconsistent_total(self):
        out, res, *_ = prep("02_messy_ventes_fr.xlsx")
        ins, _ = build_insights(out, res.facts)
        cats = {i.category for i in ins}
        assert "quality" in cats and "consistency" in cats
        q = [i for i in ins if i.category == "quality"][0]
        assert "Potential issue" in q.statement

    def test_next_steps_are_answerable_questions(self):
        out, res, schema, frames = prep("01_sales_clean.xlsx")
        ins, _ = build_insights(out, res.facts)
        ran = 0
        for i in ins:
            if i.next_plan:
                assert i.next_plan["op"] and i.next_plan["table"] == "Sales"
                assert answer_question(i.next_check, QAContext(schema, frames), i.next_plan)["status"] == "ok", i.next_check
                ran += 1
        assert ran >= 2


class TestInsightsWithAI:
    def setup_method(self):
        self.out, self.res, *_ = prep("01_sales_clean.xlsx")

    def ids(self, ins):
        return {i.category: i.priority for i in ins}

    def test_valid_ai_wording_is_used_and_marked(self):
        base, _ = build_insights(self.out, self.res.facts)
        top = next(i for i in base if i.category == "target")
        llm = FakeLLM({"insights": [{"id": top.priority, "statement": "Total total_dzd reached 53% of target_dzd over 9 months.",
                                     "interpretation": "This may be worth a closer look by month.", "next_check": "Which months fell shortest?"}]})
        ins, st = build_insights(self.out, self.res.facts, llm, True)
        t = next(i for i in ins if i.category == "target")
        assert t.source == "ai" and t.interpretation.startswith("This may") and st["ai_used"] == 1 and st["ai_error"] is None

    def test_invented_numbers_causes_and_names_are_rejected_per_insight(self):
        base, _ = build_insights(self.out, self.res.facts)
        a, b, c = base[0], base[1], base[2]
        llm = FakeLLM({"insights": [
            {"id": a.priority, "statement": "Sales reached 97% of target."},
            {"id": b.priority, "statement": "Electronics grew because of a new campaign."},
            {"id": c.priority, "statement": "Furniture leads the table.", "interpretation": "", "next_check": ""}]})
        ins, st = build_insights(self.out, self.res.facts, llm, True)
        assert st["ai_used"] == 0 and st["ai_rejected"] == 3
        by = {i.priority: i for i in ins}
        for x in (a, b, c):
            assert by[x.priority].source == "template" and by[x.priority].statement == x.statement and by[x.priority].issues

    def test_a_partly_good_response_keeps_the_good_part(self):
        base, _ = build_insights(self.out, self.res.facts)
        tgt = next(i for i in base if i.category == "target")
        other = next(i for i in base if i.category != "target")
        llm = FakeLLM({"insights": [{"id": tgt.priority, "statement": "Total total_dzd reached 53% of target_dzd."},
                                    {"id": other.priority, "statement": "Everything doubled to 14,000,000."}]})
        ins, st = build_insights(self.out, self.res.facts, llm, True)
        assert (st["ai_used"], st["ai_rejected"]) == (1, 1)

    @pytest.mark.parametrize("response", [LLMError("rate_limited"), {"insights": "nonsense"}, {"insights": [{"id": "x"}, 5, None]}, {}])
    def test_provider_problems_leave_the_builtin_insights_intact(self, response):
        base, _ = build_insights(self.out, self.res.facts)
        ins, st = build_insights(self.out, self.res.facts, FakeLLM(response), True)
        assert [i.statement for i in ins] == [i.statement for i in base] and st["ai_used"] == 0

    def test_people_are_never_sent_to_the_provider(self):
        out, res, *_ = prep("02_messy_ventes_fr.xlsx")
        llm = FakeLLM({"insights": []})
        build_insights(out, res.facts, llm, True)
        sent = " ".join(u for _, u in llm.sent)
        assert llm.sent and "Benali" not in sent and "Mansouri" not in sent and "Khelifi" not in sent

    def test_ai_off_never_calls_the_provider(self):
        llm = FakeLLM()
        build_insights(self.out, self.res.facts, llm, False)
        assert llm.sent == []
