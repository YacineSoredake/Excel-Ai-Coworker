"""Key figures (KPIs), rankings by dimension, and unusual values."""
import pandas as pd

from .model import Fact
from .numfmt import fmt, num, pct
from .plan import TableCtx, dim_suitability, importance, reliability

MIN_GROUP_FOR_MEAN = 5


def labels(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip()


def kpi_facts(tc: TableCtx) -> list[Fact]:
    t, df, n = tc.t, tc.df, len(tc.df)
    if not (tc.measures or tc.time) or n == 0:
        return []
    out: list[Fact] = []
    rel, cav = reliability(tc, [], n)
    out.append(Fact(
        kind="kpi", key=f"kpi:{t.index}:records:count", table_index=t.index,
        title=f"How many records are in {t.name}?", headline=f"{n:,} records in {t.name}",
        definition=f"Number of data rows in “{t.name}” ({t.cell_range}), excluding the header and total rows.",
        payload={"agg": "count", "value": n}, spec={"op": "agg", "agg": "count", "measure": None}, agg="count",
        source={"table": t.name, "range": t.cell_range, "rows_used": n}, usefulness=0.8, reliability=rel,
        caveats=cav, group=f"kpi:{t.index}:count"))
    for c, mode in tc.measures:
        vals = df[c.name].dropna()
        if vals.empty:
            continue
        k, missing, cur, imp = len(vals), n - len(vals), c.currency, importance(c)
        src = {"table": t.name, "columns": [c.name], "rows_used": k, "rows_left_out": missing}
        if mode == "sum":
            rel, cav = reliability(tc, [c], k, "sum")
            top = df.loc[vals.nlargest(5).index, "row_number"].tolist()
            out.append(Fact(
                kind="kpi", key=f"kpi:{t.index}:{c.name}:sum", table_index=t.index,
                title=f"What is the total {c.name}?", headline=f"Total {c.name}: {fmt(vals.sum(), cur)}",
                definition=f"Sum of “{c.name}” over the {k:,} rows that have a value ({missing} rows without a value are left out).",
                payload={"agg": "sum", "value": num(vals.sum()), "count": k, "missing": missing, "currency": cur},
                spec={"op": "agg", "agg": "sum", "measure": c.name}, source=src, measure=c.name, agg="sum",
                sample_rows=[int(r) for r in top], usefulness=round(0.9 * imp, 3), reliability=rel, caveats=cav,
                group=f"kpi:{t.index}:{c.name}"))
        rel, cav = reliability(tc, [c], k, "mean")
        out.append(Fact(
            kind="kpi", key=f"kpi:{t.index}:{c.name}:mean", table_index=t.index,
            title=f"What is the typical {c.name}?",
            headline=f"Average {c.name}: {fmt(vals.mean(), cur)} (median {fmt(vals.median(), cur)})",
            definition=f"Mean and median of “{c.name}” over the {k:,} rows that have a value.",
            payload={"agg": "mean", "value": num(vals.mean()), "median": num(vals.median()), "min": num(vals.min()),
                     "max": num(vals.max()), "count": k, "missing": missing, "currency": cur},
            spec={"op": "agg", "agg": "mean", "measure": c.name}, source=src, measure=c.name, agg="mean",
            usefulness=round(0.6 * imp, 3), reliability=rel, caveats=cav, group=f"kpi:{t.index}:{c.name}"))
    return out


def ranking_facts(tc: TableCtx) -> list[Fact]:
    t, df = tc.t, tc.df
    out: list[Fact] = []
    for d in tc.dims:
        lab = labels(df[d.name])
        sd = dim_suitability(d.distinct_count)
        for c, mode in [(None, "count")] + list(tc.measures):
            if c is None:
                mask = lab.notna()
                g = df[mask].groupby(lab[mask]).size().astype(float)
                sizes, left_label, left_value, small = g, int((~mask).sum()), 0, 0
            else:
                mask = lab.notna() & df[c.name].notna()
                grp = pd.DataFrame({"l": lab[mask], "v": df.loc[mask, c.name]}).groupby("l")["v"]
                g, sizes = (grp.sum() if mode == "sum" else grp.mean()), grp.size()
                left_label, left_value, small = int(lab.isna().sum()), int((lab.notna() & df[c.name].isna()).sum()), 0
                if mode == "mean":
                    keep = sizes >= MIN_GROUP_FOR_MEAN
                    small = int((~keep).sum())
                    g, sizes = g[keep], sizes[keep]
            rows_used = int(sizes.sum())
            if len(g) < 2 or rows_used < 8:
                continue
            g = (g.rename("v").reset_index().rename(columns={g.index.name or "index": "l"})
                 .sort_values(["v", "l"], ascending=[False, True], kind="mergesort").reset_index(drop=True))
            sizes = sizes.to_dict()
            additive = mode in ("sum", "count")
            total = float(g["v"].sum())
            shares_ok = additive and total > 0 and (g["v"] >= 0).all()

            def row(r):
                return {"label": str(r.l), "value": num(r.v), "share": num(r.v / total) if shares_ok else None,
                        "rows": int(sizes[r.l])}
            groups = [row(r) for r in g.head(10).itertuples()]
            rest = g.iloc[10:]
            other = ({"value": num(rest["v"].sum()), "share": num(rest["v"].sum() / total) if shares_ok else None,
                      "n_groups": len(rest)} if len(rest) and additive else None)
            bottom = [row(r) for r in g.tail(3).iloc[::-1].itertuples()] if len(g) >= 6 else []
            top1 = groups[0]["share"] if shares_ok else None
            top3 = num(g["v"].head(3).sum() / total) if shares_ok else None
            # rows behind the top group, for "which rows are behind this?"
            top_label = groups[0]["label"]
            if c is None:
                sample = df.loc[mask & (lab == top_label), "row_number"].head(10).tolist()
            else:
                sub = df.loc[mask & (lab == top_label), [c.name, "row_number"]]
                sample = sub.nlargest(10, c.name)["row_number"].tolist()
            cur = c.currency if c is not None else None
            cols = [x for x in (d, c) if x is not None]
            rel, cav = reliability(tc, cols, rows_used, mode)
            if small:
                cav.append(f"{small} group(s) with fewer than {MIN_GROUP_FOR_MEAN} rows were left out of the ranking.")
            if c is None:
                title, head = (f"Which {d.name} has the most records?",
                               f"{top_label} has the most records ({groups[0]['rows']:,}" + (f", {pct(top1)}" if top1 is not None else "") + ")")
                defin = f"Number of rows per “{d.name}”, ranked from most to fewest."
                use = 0.55 * sd
            elif mode == "sum":
                title, head = (f"Which {d.name} brings in the most {c.name}?",
                               f"{top_label} has the highest {c.name} ({fmt(groups[0]['value'], cur)}"
                               + (f", {pct(top1)} of the total" if top1 is not None else "") + ")")
                defin = f"Sum of “{c.name}” per “{d.name}”, ranked from highest to lowest."
                use = 0.8 * sd * importance(c)
            else:
                title, head = (f"Which {d.name} has the highest average {c.name}?",
                               f"{top_label} has the highest average {c.name} ({fmt(groups[0]['value'], cur)})")
                defin = (f"Average of “{c.name}” per “{d.name}”, ranked from highest to lowest; groups with fewer "
                         f"than {MIN_GROUP_FOR_MEAN} rows are excluded.")
                use = 0.65 * sd * importance(c)
            if top3 is not None:
                use *= 0.7 + 0.3 * min(1.0, top3)
            out.append(Fact(
                kind="ranking", key=f"ranking:{t.index}:{c.name if c else 'records'}:{mode}:{d.name}",
                table_index=t.index, title=title, headline=head, definition=defin,
                payload={"agg": mode, "n_groups": int(len(g)), "total": num(total) if additive else None,
                         "groups": groups, "other": other, "bottom": bottom, "top1_share": top1, "top3_share": top3,
                         "composition_suitable": bool(shares_ok and len(g) <= 6), "currency": cur,
                         "excluded": {"missing_label": left_label, "missing_value": left_value, "small_groups": small}},
                spec={"op": "group", "dim": d.name, "measure": c.name if c else None, "agg": mode,
                      "min_group": MIN_GROUP_FOR_MEAN if mode == "mean" else 0},
                source={"table": t.name, "columns": [x.name for x in cols], "rows_used": rows_used,
                        "rows_left_out": left_label + left_value},
                measure=c.name if c else None, dimension=d.name, agg=mode, sample_rows=[int(r) for r in sample],
                caveats=cav, usefulness=round(use, 3), reliability=rel,
                group=f"rank:{t.index}:{c.name if c else 'records'}:{mode}"))
    return out


def outlier_facts(tc: TableCtx) -> list[Fact]:
    out = []
    for c, mode in tc.measures:
        o = c.outliers
        valid = c.n_rows - c.missing_count
        if not o or not o["count_extreme"] or o["count_extreme"] > max(5, int(0.01 * valid)):
            continue
        ex = o["sample"][0]
        rel, cav = reliability(tc, [c], valid, "mean")
        out.append(Fact(
            kind="anomaly_values", key=f"anomaly_values:{tc.t.index}:{c.name}", table_index=tc.t.index,
            title=f"Are there unusual values in {c.name}?",
            headline=(f"{o['count_extreme']} value(s) in {c.name} are far outside the usual range "
                      f"(for example {fmt(ex['value'], c.currency)} in row {ex['row']})"),
            definition=("Values beyond 3× the interquartile range" +
                        (" (measured on a log scale because the values are very skewed)" if o["method"] == "iqr_log10" else "") + "."),
            payload={"count": o["count_extreme"], "fences": o["fences_extreme"], "method": o["method"],
                     "examples": o["sample"], "valid_count": valid, "currency": c.currency},
            spec={"op": "outliers", "measure": c.name, "fences": o["fences_extreme"]},
            source={"table": tc.t.name, "columns": [c.name], "rows_used": valid},
            measure=c.name, sample_rows=[s["row"] for s in o["sample"]], caveats=cav,
            usefulness=round(0.7 * importance(c), 3), reliability=rel, group=f"anomaly_values:{tc.t.index}"))
    return out
