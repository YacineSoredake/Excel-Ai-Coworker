"""Phase 3 benchmark: facts must match independent calculations, and the failure paths must hold."""
import copy
import json
import os
import random
import re
from datetime import date, timedelta

import openpyxl
import pandas as pd
import pytest

from app.analytics.facts_time import direction, kendall_tau
from app.analytics.periods import choose_grain
from app.analytics.run import compute_analytics
from app.analytics.verify import VCtx, verify
from app.engine.analyze import analyze_workbook
from app.validate import Rejected

from .helpers import build

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
CAUSAL = re.compile(r"\b(because|caused by|due to|driven by|leads to|results in|reason|thanks to)\b", re.I)


def run(name):
    out = analyze_workbook(open(os.path.join(FIX, name), "rb").read())
    return out, compute_analytics(out)


def by_key(res, prefix):
    return [f for f in res.facts if f.key.startswith(prefix)]


def one(res, prefix):
    fs = by_key(res, prefix)
    assert len(fs) == 1, (prefix, [f.key for f in res.facts])
    return fs[0]


def synth(rows, headers=("date", "category", "region", "amount", "quantity")):
    def f(wb):
        ws = wb.active
        ws.title = "Data"
        ws.append(list(headers))
        for r in rows:
            ws.append(list(r))
    out = analyze_workbook(build(f))
    return out, compute_analytics(out)


def daily(start, end, per_day=3, seed=1, amount=lambda d, i: 100.0 + i, cats=("A", "B", "C", "D")):
    rnd = random.Random(seed)
    rows, d = [], start
    while d <= end:
        for i in range(per_day):
            rows.append((d, rnd.choice(cats), rnd.choice(["N", "S", "E"]), amount(d, i), rnd.randint(1, 5)))
        d += timedelta(days=1)
    return rows


# ------------------------------------------------------------------ the fixtures, against pandas

def test_clean_sales_figures_match_pandas():
    out, res = run("01_sales_clean.xlsx")
    df = pd.read_excel(os.path.join(FIX, "01_sales_clean.xlsx"), sheet_name="Sales")
    assert one(res, "kpi:0:total_dzd:sum").payload["value"] == pytest.approx(df["total_dzd"].sum())
    assert one(res, "kpi:0:records:count").payload["value"] == len(df)
    m = df.groupby(df["date"].dt.to_period("M"))["total_dzd"].sum()
    trend = one(res, "trend:0:total_dzd")
    assert [p["period"] for p in trend.payload["periods"]] == [str(p) for p in m.index]
    assert [p["value"] for p in trend.payload["periods"]] == pytest.approx(m.tolist())
    pc = one(res, "period_change:0:total_dzd")
    assert pc.payload["latest"]["period"] == "2026-09" and pc.payload["latest"]["value"] == pytest.approx(m.iloc[-1])
    assert pc.payload["change_abs"] == pytest.approx(m.iloc[-1] - m.iloc[-2])
    rk = one(res, "ranking:0:total_dzd:sum:category")
    by_cat = df.groupby("category")["total_dzd"].sum().sort_values(ascending=False)
    assert rk.payload["groups"][0]["label"] == by_cat.index[0]
    assert rk.payload["groups"][0]["value"] == pytest.approx(by_cat.iloc[0])
    assert rk.payload["top1_share"] == pytest.approx(by_cat.iloc[0] / by_cat.sum())
    assert rk.payload["composition_suitable"] is True  # 4 categories


def test_everything_is_verified_json_safe_and_non_causal():
    for name in ("01_sales_clean.xlsx", "02_messy_ventes_fr.xlsx"):
        out, res = run(name)
        assert res.stats["dropped_unverified"] == 0 and res.facts
        assert all(f.verified for f in res.facts)
        for f in res.facts:
            json.dumps([f.payload, f.spec, f.source], allow_nan=False)
            assert not CAUSAL.search(f.headline + " " + f.title), f.headline
            assert 0.3 <= f.reliability <= 1 and 0 <= f.usefulness <= 1
        assert len({f.key for f in res.facts}) == len(res.facts)
        assert [f.score for f in res.facts] == sorted((f.score for f in res.facts), reverse=True)


def test_prices_are_averaged_never_summed():
    _, res = run("01_sales_clean.xlsx")
    assert by_key(res, "kpi:0:unit_price_dzd:sum") == []
    assert one(res, "kpi:0:unit_price_dzd:mean").payload["agg"] == "mean"
    assert not [f for f in res.facts if f.kind == "ranking" and f.measure == "unit_price_dzd" and f.agg == "sum"]


def test_target_comparison_matches_manual_calculation():
    out, res = run("01_sales_clean.xlsx")
    sales = pd.read_excel(os.path.join(FIX, "01_sales_clean.xlsx"), sheet_name="Sales")
    tg = pd.read_excel(os.path.join(FIX, "01_sales_clean.xlsx"), sheet_name="Targets")
    act = sales.groupby(sales["date"].dt.to_period("M").astype(str))["total_dzd"].sum()
    t = one(res, "target:0:total_dzd:target_dzd")
    assert t.payload["matched_periods"] == 9
    assert t.payload["attainment"] == pytest.approx(act.sum() / tg["target_dzd"].sum())
    assert t.payload["periods"][0]["target"] == pytest.approx(tg["target_dzd"].iloc[0])
    assert t.table_index == 0 and "calendar month" in " ".join(t.caveats)


def test_derived_column_is_found_and_not_reported_as_correlation():
    _, res = run("01_sales_clean.xlsx")
    d = one(res, "derivation:0")
    assert d.payload["factors"] == ["quantity", "unit_price_dzd"] and d.payload["mismatch_count"] == 0
    assert not [f for f in res.facts if f.kind == "correlation"]


def test_messy_file_flags_the_inconsistent_total_and_carries_caveats():
    out, res = run("02_messy_ventes_fr.xlsx")
    d = one(res, "derivation:0")
    assert d.payload["mismatch_count"] == 1 and d.payload["mismatches"][0]["row"] == 25
    assert d.payload["mismatches"][0]["actual"] == 9999999.0
    a = one(res, "anomaly_values:0:Montant (DA)")
    assert a.sample_rows == [25]
    total = one(res, "kpi:0:Montant (DA):sum")
    cav = " ".join(total.caveats)
    assert "duplicate" in cav and "unusually extreme" in cav
    assert total.reliability < one(run("01_sales_clean.xlsx")[1], "kpi:0:total_dzd:sum").reliability
    # thin weekly data must not produce 'change' claims
    assert not [f for f in res.facts if f.kind in ("period_change", "swing", "anomaly_period")]
    assert all("noisy" in " ".join(f.caveats) for f in res.facts if f.kind == "trend")


# ------------------------------------------------------------------ periods

def test_partial_last_month_is_excluded_from_comparisons():
    _, res = synth(daily(date(2026, 1, 1), date(2026, 9, 12)))
    tr = one(res, "trend:0:records")
    assert tr.payload["excluded_partial"] == ["2026-09"] and tr.payload["last"]["period"] == "2026-08"
    pc = one(res, "period_change:0:records")
    assert (pc.payload["latest"]["period"], pc.payload["previous"]["period"]) == ("2026-08", "2026-07")
    assert any("2026-09" in c and "incomplete" in c for c in pc.caveats)


def test_missing_month_counts_as_zero_and_is_disclosed():
    rows = [r for r in daily(date(2026, 1, 1), date(2026, 8, 31)) if r[0].month != 4]
    _, res = synth(rows)
    tr = one(res, "trend:0:amount:date")
    assert tr.payload["empty_periods"] == ["2026-04"]
    apr = [p for p in tr.payload["periods"] if p["period"] == "2026-04"][0]
    assert apr["value"] == 0.0 and apr["rows"] == 0
    assert any("no rows at all" in c for c in tr.caveats)
    assert tr.reliability < one(synth(daily(date(2026, 1, 1), date(2026, 8, 31)))[1], "trend:0:amount:date").reliability


def test_rising_series_is_labelled_rising_and_noise_is_not():
    rows = daily(date(2026, 1, 1), date(2026, 8, 31), per_day=1, amount=lambda d, i: 100.0 + d.month * 40)
    _, res = synth(rows)
    assert one(res, "trend:0:amount:date").payload["direction"] == "rising"
    rnd = random.Random(3)
    flat = daily(date(2026, 1, 1), date(2026, 8, 31), per_day=1, amount=lambda d, i: 100.0 + rnd.uniform(-5, 5))
    _, res = synth(flat)
    assert one(res, "trend:0:amount:date").payload["direction"] == "flat_or_mixed"


def test_grain_choice():
    ts = pd.Timestamp
    assert choose_grain(ts("2026-01-01"), ts("2026-01-03")) is None
    assert choose_grain(ts("2026-01-01"), ts("2026-01-15")) == "D"
    assert choose_grain(ts("2026-07-01"), ts("2026-09-30")) == "W"
    assert choose_grain(ts("2026-01-01"), ts("2026-09-30")) == "M"
    assert choose_grain(ts("2022-01-01"), ts("2026-09-30")) == "Q"
    assert choose_grain(ts("2000-01-01"), ts("2026-09-30")) == "Y"


def test_kendall_and_direction():
    assert kendall_tau([1, 2, 3, 4]) == 1 and kendall_tau([4, 3, 2, 1]) == -1
    assert direction([10, 12, 14, 18, 22])[0] == "rising"
    assert direction([22, 18, 14, 12, 10])[0] == "falling"
    assert direction([10, 11, 10, 11, 10])[0] == "flat_or_mixed"
    assert direction([10, 20, 30])[0] == "flat_or_mixed"  # fewer than 4 periods


# ------------------------------------------------------------------ rankings and associations

def _skewed_rows():
    rows = [(date(2026, 1, 1) + timedelta(days=i), "Big" if i % 10 else "Small", "N", 1000.0 if i % 10 else 10.0, 1)
            for i in range(120)]
    return rows + [(date(2026, 1, 1), "Rare", "N", 9999.0, 1) for _ in range(2)]  # only 2 rows


def test_concentration_is_reported_for_summed_measures():
    _, res = synth(_skewed_rows())
    rk = one(res, "ranking:0:amount:sum:category")
    assert rk.payload["groups"][0]["label"] == "Big"
    assert rk.payload["top1_share"] == pytest.approx(108000 / (108000 + 120 + 2 * 9999))
    assert rk.payload["n_groups"] == 3 and rk.payload["excluded"]["small_groups"] == 0


def test_averages_ignore_groups_with_too_few_rows():
    _, res = synth(_skewed_rows(), headers=("date", "category", "region", "price", "quantity"))
    assert not by_key(res, "ranking:0:price:sum")  # a price is never ranked by its sum
    mean = one(res, "ranking:0:price:mean:category")
    assert "Rare" not in [g["label"] for g in mean.payload["groups"]]  # 2 rows: its 9,999 average would mislead
    assert mean.payload["excluded"]["small_groups"] == 1
    assert [g["label"] for g in mean.payload["groups"]] == ["Big", "Small"]
    assert any("fewer than 5 rows" in c for c in mean.caveats)


def test_correlation_reported_with_association_wording_only():
    rnd = random.Random(2)
    rows = []
    for i in range(80):
        q = rnd.randint(1, 50)
        rows.append((date(2026, 1, 1) + timedelta(days=i), rnd.choice("AB"), "N", q * 10 + rnd.uniform(0, 120), q))
    _, res = synth(rows)
    c = one(res, "correlation:0:")
    assert c.payload["rho"] > 0.8 and "move together" in " ".join(c.caveats)
    assert not CAUSAL.search(c.headline)


def test_ambiguous_target_column_is_skipped():
    def f(wb):
        ws = wb.active
        ws.title = "Data"
        ws.append(["date", "category", "amount", "cost"])
        d = date(2026, 1, 1)
        for i in range(240):
            ws.append([d + timedelta(days=i), "A" if i % 2 else "B", 100.0 + i % 7, 40.0 + i % 5])
        t = wb.create_sheet("Plan")
        t.append(["month", "budget"])
        for m in range(1, 8):
            t.append([f"2026-{m:02d}", 5000 + m])
    res = compute_analytics(analyze_workbook(build(f)))
    assert not by_key(res, "target:")  # 'budget' could mean amount or cost: don't guess


# ------------------------------------------------------------------ verification and limits

def test_tampered_facts_fail_verification():
    out, res = run("01_sales_clean.xlsx")
    v = VCtx({i: out.frames[t.id] for i, t in enumerate(out.tables)})
    for prefix, edit in [
        ("kpi:0:total_dzd:sum", lambda p: p.update(value=p["value"] + 1000)),
        ("ranking:0:total_dzd:sum:category", lambda p: p["groups"][0].update(value=p["groups"][0]["value"] * 1.01)),
        ("trend:0:total_dzd", lambda p: p["periods"][2].update(value=p["periods"][2]["value"] + 500)),
        ("trend:0:total_dzd", lambda p: p.update(direction="rising" if p["direction"] != "rising" else "falling")),
        ("period_change:0:total_dzd", lambda p: p.update(change_abs=0.0)),
        ("target:0:total_dzd:target_dzd", lambda p: p.update(attainment=0.99)),
        ("derivation:0", lambda p: p.update(mismatch_count=3)),
        ("breakdown:0:total_dzd", lambda p: p["series"][0]["values"].__setitem__(0, 1.0)),
    ]:
        f = one(res, prefix) if prefix != "breakdown:0:total_dzd" else by_key(res, prefix)[0]
        assert verify(f, v), prefix
        bad = copy.deepcopy(f)
        edit(bad.payload)
        assert not verify(bad, v), prefix


def test_analytics_respects_the_time_limit():
    out, _ = run("01_sales_clean.xlsx")
    with pytest.raises(Rejected) as e:
        compute_analytics(out, timeout_seconds=-1)
    assert e.value.code == "timeout"


def test_workbook_without_measures_produces_no_facts():
    def f(wb):
        ws = wb.active
        ws.append(["Nom", "Ville"])
        for i in range(12):
            ws.append([f"N{i}", ["Alger", "Oran"][i % 2]])
    res = compute_analytics(analyze_workbook(build(f)))
    assert res.facts == [] and res.stats["skipped_tables"]
