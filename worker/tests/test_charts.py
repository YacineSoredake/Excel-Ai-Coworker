"""Phase 4: chart specs follow the report's §5 rules and stay traceable to verified facts."""
import json
import os
import random
from datetime import date, timedelta

import pytest

from app.analytics.run import compute_analytics
from app.charts.run import build_charts
from app.engine.analyze import analyze_workbook

from .helpers import build
from .test_analytics import daily, synth

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def charts_of(name):
    out = analyze_workbook(open(os.path.join(FIX, name), "rb").read())
    res = compute_analytics(out)
    charts, stats = build_charts(out, res)
    return out, res, charts, stats


def at(charts, placement):
    return sorted((c for c in charts if c.placement == placement), key=lambda c: c.position)


def test_first_screen_is_small_and_varied():
    _, _, charts, _ = charts_of("01_sales_clean.xlsx")
    kpi, prim, sec = at(charts, "kpi"), at(charts, "primary"), at(charts, "secondary")
    assert len(kpi) == 4 and len(prim) == 1 and 3 <= len(sec) <= 4
    assert prim[0].kind == "line" and prim[0].encoding["measure"] == "total_dzd" and prim[0].encoding["time"] == "date"
    kinds = [c.kind for c in sec]
    assert "target" in kinds and kinds.count("hbar") >= 2
    dims = [c.encoding["dim"] for c in sec if c.encoding.get("dim")]
    assert len(dims) == len(set(dims))  # a different angle each time, not the same category twice


def test_kpi_cards_carry_deltas_and_the_target():
    _, _, charts, _ = charts_of("01_sales_clean.xlsx")
    cards = {c.data["label"]: c for c in at(charts, "kpi")}
    total = cards["Total total_dzd"]
    assert total.data["value"] == pytest.approx(7196350) and total.data["format"] == "currency"
    assert total.data["delta"]["latest"] == "2026-09" and total.data["delta"]["pct"] == pytest.approx(0.7087, abs=1e-3)
    tgt = [c for c in at(charts, "kpi") if c.encoding.get("variant") == "target"][0]
    assert tgt.data["format"] == "percent" and 0.5 < tgt.data["value"] < 0.55 and tgt.query is None
    assert len({c.encoding["measure"] for c in at(charts, "kpi") if c.encoding.get("variant") is None}) == 3  # no total+average twins


def test_titles_are_questions_and_every_chart_traces_to_facts():
    for name in ("01_sales_clean.xlsx", "02_messy_ventes_fr.xlsx"):
        out, res, charts, _ = charts_of(name)
        keys = {f.key for f in res.facts}
        for c in charts:
            assert c.title.endswith("?"), c.title
            assert c.fact_keys and set(c.fact_keys) <= keys
            assert c.why and 0 < c.score <= 1 and c.readability > 0
            json.dumps([c.data, c.query, c.options, c.encoding], allow_nan=False)
        assert len({c.key for c in charts}) == len(charts)


def test_chart_numbers_are_the_verified_fact_numbers():
    out, res, charts, _ = charts_of("01_sales_clean.xlsx")
    facts = {f.key: f for f in res.facts}
    for c in charts:
        f = facts[c.fact_keys[0]]
        if c.kind == "line":
            assert c.data["y"] == [i["value"] for i in f.payload["periods"]]
        elif c.kind == "hbar":
            assert [g["value"] for g in c.data["groups"] if not g.get("muted")] == [g["value"] for g in f.payload["groups"]]
        elif c.kind == "target":
            assert c.data["attainment"] == f.payload["attainment"]
        elif c.kind == "kpi":
            assert c.data["value"] in (f.payload.get("value"), f.payload.get("attainment"))


def test_bars_for_rankings_donut_only_as_an_offered_alternative():
    _, res, charts, _ = charts_of("01_sales_clean.xlsx")
    assert not [c for c in charts if c.kind == "donut"]
    facts = {f.key: f for f in res.facts}
    for c in charts:
        if c.kind != "hbar":
            continue
        p = facts[c.fact_keys[0]].payload
        vals = [g["value"] for g in c.data["groups"] if not g.get("muted")]
        assert vals == sorted(vals, reverse=True)  # rankings are sorted
        assert (c.options["alt_kinds"] == ["donut"]) == (p["composition_suitable"] and 2 <= p["n_groups"] <= 5)
        if c.options["alt_kinds"]:
            assert c.options["additive"] and p["n_groups"] <= 5  # never offered for many categories


def test_partial_periods_and_annotations_are_marked_on_the_trend():
    rows = daily(date(2026, 1, 1), date(2026, 9, 12), seed=4)
    o, r = synth(rows)
    charts, _ = build_charts(o, r)
    line = [c for c in charts if c.kind == "line" and c.encoding["measure"] == "amount"][0]
    assert line.data["x"][-1] == "2026-09" and line.data["complete"][-1] is False
    assert all(line.data["complete"][:-1])
    assert "incomplete" in line.why


def test_a_table_without_dates_gets_a_comparison_as_its_main_chart():
    rows = [(f"P{i % 6}", ["N", "S"][i % 2], 10.0 + i) for i in range(60)]
    def f(wb):
        ws = wb.active
        ws.append(["produit", "region", "montant"])
        for r in rows:
            ws.append(list(r))
    o = analyze_workbook(build(f))
    charts, _ = build_charts(o, compute_analytics(o))
    assert not [c for c in charts if c.kind == "line"]
    assert at(charts, "primary") and at(charts, "primary")[0].kind == "hbar"


def test_scatter_and_histogram_candidates():
    rnd = random.Random(2)
    rows = []
    for i in range(900):
        q = rnd.randint(1, 50)
        rows.append((date(2026, 1, 1) + timedelta(days=i % 200), rnd.choice("AB"), "N", q * 10 + rnd.uniform(0, 120), q))
    o, r = synth(rows)
    charts, _ = build_charts(o, r)
    sc = [c for c in charts if c.kind == "scatter"][0]
    assert len(sc.data["points"]) == 500 and sc.data["sampled"] and sc.data["n"] == 900
    assert sc.query["op"] == "scatter" and sc.data["rho"] > 0.8
    rowsn = {p[2] for p in sc.data["points"]}
    assert rowsn <= set(o.tables[0].rows)  # every dot links back to a real Excel row
    assert [c for c in charts if c.kind == "histogram"]


def test_selection_is_deterministic():
    a = charts_of("01_sales_clean.xlsx")[2]
    b = charts_of("01_sales_clean.xlsx")[2]
    assert [(c.key, c.placement, c.position) for c in a] == [(c.key, c.placement, c.position) for c in b]


def test_filterable_charts_have_a_recomputable_query():
    _, _, charts, _ = charts_of("01_sales_clean.xlsx")
    for c in charts:
        if c.kind == "target" or c.encoding.get("variant") == "target":
            assert c.query is None
        else:
            assert c.query and c.query["op"] in ("agg", "series", "group", "breakdown", "scatter", "histogram")
