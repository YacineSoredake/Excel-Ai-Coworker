"""Associations between measures, columns that are computed from others, and actual-vs-target."""
from itertools import combinations

import numpy as np
import pandas as pd

from ..engine import hints
from .model import Fact
from .numfmt import fmt, num, pct
from .periods import build_series
from .plan import REFERENCE, TableCtx, importance, reliability


def derivation_facts(tc: TableCtx) -> list[Fact]:
    """Finds columns like total = quantity × unit_price, and lists the rows where the identity breaks."""
    df, meas = tc.df, [c for c, _ in tc.measures]
    best = None
    for z in meas:
        for x, y in combinations([m for m in meas if m is not z], 2):
            d = df[[z.name, x.name, y.name]].dropna()
            if len(d) < 10:
                continue
            exp = d[x.name] * d[y.name]
            ok = (d[z.name] - exp).abs() <= 1e-6 + 1e-6 * exp.abs()
            share = float(ok.mean())
            if share >= 0.8 and (best is None or share > best[0]):
                best = (share, z, x, y, d, exp, ok)
    if not best:
        return []
    share, z, x, y, d, exp, ok = best
    bad = d[~ok]
    k = len(bad)
    rel_err = ((bad[z.name] - exp[~ok]).abs() / exp[~ok].abs().clip(lower=1e-9)).sort_values(ascending=False)
    worst = rel_err.head(5).index
    mism = [{"row": int(df.loc[i, "row_number"]), "actual": num(d.loc[i, z.name]), "expected": num(exp.loc[i])} for i in worst]
    rel, cav = reliability(tc, [z, x, y], len(d), "sum")
    head = (f"{z.name} equals {x.name} × {y.name} in every row ({len(d):,} rows checked)" if k == 0 else
            f"{z.name} equals {x.name} × {y.name} in {pct(share)} of rows; {k} row(s) do not match")
    return [Fact(
        kind="derivation", key=f"derivation:{tc.t.index}:{z.name}", table_index=tc.t.index,
        title=f"Is {z.name} consistent with {x.name} and {y.name}?", headline=head,
        definition=f"For each row, “{z.name}” is compared with “{x.name}” × “{y.name}” (tolerance 0.0001%).",
        payload={"formula": f"{z.name} = {x.name} × {y.name}", "target": z.name, "factors": [x.name, y.name],
                 "checked_rows": int(len(d)), "match_share": num(share, 6), "mismatch_count": k, "mismatches": mism},
        spec={"op": "derivation", "z": z.name, "x": x.name, "y": y.name},
        source={"table": tc.t.name, "columns": [z.name, x.name, y.name], "rows_used": int(len(d))},
        measure=z.name, sample_rows=[m["row"] for m in mism], caveats=cav,
        usefulness=0.4 if k == 0 else 0.85, reliability=rel, group=f"derivation:{tc.t.index}")]


def correlation_facts(tc: TableCtx, derived: set) -> list[Fact]:
    out = []
    for a, b in combinations([c for c, _ in tc.measures], 2):
        if frozenset((a.name, b.name)) in derived:
            continue
        d = tc.df[[a.name, b.name]].dropna()
        if len(d) < 30 or d[a.name].nunique() < 5 or d[b.name].nunique() < 5:
            continue
        rho = float(np.corrcoef(d[a.name].rank(), d[b.name].rank())[0, 1])
        if np.isnan(rho) or abs(rho) < 0.5 or abs(rho) > 0.98:
            continue
        rel, cav = reliability(tc, [a, b], len(d), "mean")
        cav.append("This shows that the two move together, not that one causes the other.")
        out.append(Fact(
            kind="correlation", key=f"correlation:{tc.t.index}:{a.name}:{b.name}", table_index=tc.t.index,
            title=f"Do {a.name} and {b.name} move together?",
            headline=(f"{a.name} and {b.name} tend to {'rise together' if rho > 0 else 'move in opposite directions'} "
                      f"(rank correlation {rho:+.2f} over {len(d):,} rows)"),
            definition="Spearman rank correlation between the two columns, over rows where both have a value.",
            payload={"method": "spearman", "rho": num(rho, 6), "n": int(len(d))},
            spec={"op": "corr", "a": a.name, "b": b.name},
            source={"table": tc.t.name, "columns": [a.name, b.name], "rows_used": int(len(d))},
            caveats=cav, usefulness=round((0.5 + 0.4 * abs(rho)) * min(importance(a), importance(b)), 3),
            reliability=rel, group=f"corr:{tc.t.index}"))
    return out


def month_keys(tc: TableCtx):
    """A 'YYYY-MM' key per row, from a date column or from text such as 2026-03."""
    if tc.time is not None:
        s = tc.df[tc.time.name]
        return s.dt.to_period("M").astype("string"), tc.time.name
    for c in tc.t.columns:
        if c.base_type in ("text", "identifier"):
            s = tc.df[c.name].astype("string").str.strip()
            m = s.str.extract(r"^(\d{4})[-/](\d{1,2})$")
            if s.notna().sum() >= 3 and m[0].notna().sum() / s.notna().sum() >= 0.9:
                return m[0] + "-" + m[1].str.zfill(2), c.name
    return None, None


def target_facts(ctxs: list[TableCtx]) -> list[Fact]:
    out = []
    for rt in ctxs:
        if not rt.refs:
            continue
        keys, kname = month_keys(rt)
        if keys is None:
            continue
        for ref in rt.refs:
            tgt = pd.DataFrame({"k": keys, "v": rt.df[ref.name]}).dropna().groupby("k")["v"].sum()
            if tgt.empty:
                continue
            for mt in ctxs:
                if mt is rt or mt.time is None or mt.grain != "M":
                    continue
                cands = [c for c, m in mt.measures
                         if m == "sum" and c.role_subtype == "amount" and (c.currency in (None, ref.currency) or ref.currency is None)]
                if not cands:
                    continue
                want = set(hints.tokens(ref.name)) - REFERENCE
                scored = sorted(((len(want & set(hints.tokens(c.name))), c) for c in cands), key=lambda s: -s[0])
                if len(scored) > 1 and scored[0][0] == scored[1][0]:
                    continue  # ambiguous which column the target refers to
                meas = scored[0][1]
                items = build_series(mt.df, mt.time.name, "M", meas.name, "sum", mt.min_d, mt.max_d)
                actual = {i["period"]: i for i in items if i["complete"] and i["value"] is not None}
                matched = [p for p in actual if p in tgt.index]
                if len(matched) < 3:
                    continue
                rows = []
                for p in matched:
                    a, tv = actual[p]["value"], float(tgt[p])
                    rows.append({"period": p, "actual": num(a), "target": num(tv), "variance": num(a - tv),
                                 "attainment": num(a / tv) if tv > 0 else None})
                ta, tt = sum(r["actual"] for r in rows), sum(r["target"] for r in rows)
                att = ta / tt if tt > 0 else None
                if att is None:
                    continue
                skipped = [p for p in tgt.index if p not in actual]
                rel1, cav = reliability(mt, [mt.time, meas], sum(actual[p]["rows"] for p in matched), "sum")
                # a targets table has one row per month by design, so its row count says nothing about support
                rel2, cav2 = reliability(rt, [ref], 10 ** 6, "sum")
                cav = list(dict.fromkeys(cav + cav2 + ["Actuals and targets are matched by calendar month."]))
                if skipped:
                    cav.append(f"Target months without a complete month of data were left out: {', '.join(map(str, skipped[:6]))}.")
                out.append(Fact(
                    kind="target", key=f"target:{mt.t.index}:{meas.name}:{ref.name}", table_index=mt.t.index,
                    title=f"Is {meas.name} on track against {ref.name}?",
                    headline=f"{meas.name} reached {pct(att)} of {ref.name} over {len(rows)} months ({fmt(ta, meas.currency)} vs {fmt(tt, ref.currency)})",
                    definition=(f"Monthly sum of “{meas.name}” compared with “{ref.name}” from “{rt.t.name}”, "
                                "over complete months present in both."),
                    payload={"grain": "M", "periods": rows, "total_actual": num(ta), "total_target": num(tt),
                             "attainment": num(att), "matched_periods": len(rows), "currency": meas.currency,
                             "target_table": rt.t.name, "target_column": ref.name},
                    spec={"op": "target", "time": mt.time.name, "measure": meas.name, "ref_table_index": rt.t.index,
                          "ref_column": ref.name, "key_column": kname},
                    source={"table": mt.t.name, "columns": [mt.time.name, meas.name], "rows_used": sum(actual[p]["rows"] for p in matched)},
                    measure=meas.name, time_column=mt.time.name, agg="sum", caveats=cav,
                    usefulness=round(0.9 * importance(meas), 3), reliability=min(rel1, rel2), group=f"target:{mt.t.index}"))
    return out
