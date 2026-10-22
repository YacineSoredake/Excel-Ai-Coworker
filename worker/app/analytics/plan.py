"""Which columns of a table can be summed, ranked, or plotted over time — and how much to trust them."""
from dataclasses import dataclass, field

import pandas as pd

from ..engine import hints
from ..engine.columns import ColumnResult
from ..engine.models import EngineOutput, Finding, TableResult
from .periods import choose_grain

SUMMABLE = {"amount", "quantity"}  # totals make sense. Prices and rates are only ever averaged.
REFERENCE = {"target", "objectif", "budget", "forecast", "prevision", "quota", "plan", "goal", "cible"}
DIM_SUBTYPES = {"category", "location", "person", "product", "status"}


@dataclass
class TableCtx:
    t: TableResult
    df: pd.DataFrame
    measures: list  # [(ColumnResult, 'sum' | 'mean')]
    refs: list  # reference measures (targets, budgets): used only for comparisons
    dims: list
    time: ColumnResult | None
    findings: list
    min_d: pd.Timestamp | None = None
    max_d: pd.Timestamp | None = None
    grain: str | None = None
    others: dict = field(default_factory=dict)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def prepare(out: EngineOutput) -> list[TableCtx]:
    ctxs = []
    for t in out.tables:
        df = out.frames[t.id]
        measures, refs, dims, times = [], [], [], []
        for c in t.columns:
            if c.role == "measure":
                if any(tok in REFERENCE for tok in hints.tokens(c.name)):
                    refs.append(c)
                else:
                    measures.append((c, "sum" if c.role_subtype in SUMMABLE else "mean"))
            elif c.role == "dimension" and c.role_subtype in DIM_SUBTYPES and 2 <= c.distinct_count <= 200:
                dims.append(c)
            elif c.role == "time":
                times.append(c)
        time = max(times, key=lambda c: c.n_rows - c.missing_count, default=None)
        tc = TableCtx(t=t, df=df, measures=measures, refs=refs, dims=dims, time=time,
                      findings=[f for f in out.findings if f.table_index == t.index])
        if time is not None:
            d = df[time.name].dropna()
            if len(d):
                tc.min_d, tc.max_d = d.min(), d.max()
                tc.grain = choose_grain(tc.min_d, tc.max_d)
        ctxs.append(tc)
    return ctxs


def reliability(tc: TableCtx, cols: list, n: int, agg: str | None = None, extra: float = 1.0):
    """Returns (reliability 0.3-1, caveats). Every deduction comes from something we can name."""
    caveats, f = [], 1.0
    names = {c.name for c in cols}

    def col_of(fd: Finding):
        return tc.t.columns[fd.column_pos].name if fd.column_pos is not None else None

    for fd in tc.findings:
        cn = col_of(fd)
        if fd.code == "duplicate_rows":
            caveats.append(f"{fd.affected} duplicate row(s) in this table may be counted twice.")
            f *= 0.92
        elif fd.code == "missing_values" and cn in names:
            rate = (fd.affected or 0) / max(1, fd.total or 1)
            caveats.append(f"{fd.affected} row(s) have no value in “{cn}” and are left out.")
            f *= max(0.7, 1 - 0.5 * rate)
        elif fd.code == "inconsistent_labels" and cn in names:
            caveats.append(f"“{cn}” spells some values in different ways, so groups may be split.")
            f *= 0.9
        elif fd.code in ("extreme_outliers",) and cn in names:
            caveats.append(f"“{cn}” contains {fd.affected} unusually extreme value(s).")
            f *= 0.85 if agg == "mean" else 0.95
        elif fd.code == "mixed_date_formats" and cn in names:
            caveats.append(f"Dates in “{cn}” are stored in different formats.")
            f *= 0.8 if fd.severity == "high" else 0.95
        elif fd.code == "invalid_values" and cn in names:
            caveats.append(f"{fd.affected} value(s) in “{cn}” could not be read and are left out.")
            f *= 0.9
        elif fd.code == "formula_errors":
            caveats.append("Some cells show Excel errors and are left out.")
            f *= 0.95
    conf = min([(c.role_confidence or 1.0) for c in cols] or [1.0])
    role_f = 0.5 + 0.5 * min(1.0, conf)
    support = n / (n + 5)
    return round(clamp(support * role_f * f * extra, 0.3, 1.0), 3), list(dict.fromkeys(caveats))


def importance(c: ColumnResult | None) -> float:
    """How central a measure usually is to the story of a workbook."""
    if c is None:
        return 0.8
    return {"amount": 1.0, "quantity": 0.9, "generic": 0.75, "price": 0.7, "rate": 0.7}.get(c.role_subtype or "", 0.75)


def dim_suitability(distinct: int) -> float:
    if distinct < 2:
        return 0.0
    return 0.6 if distinct == 2 else 1.0 if distinct <= 12 else 0.8 if distinct <= 30 else 0.5
