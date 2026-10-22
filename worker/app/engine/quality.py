"""Data-quality and anomaly detection (report §10).

An anomaly is a signal, not automatically an error: every message says "potential issue"
and carries the affected rows so the user can inspect them. Nothing is changed in the workbook.
"""
import difflib
import re
from collections import Counter, defaultdict

from . import hints
from .formulas import inconsistent_formulas
from .models import Finding, TableResult
from .textutil import norm_key

DIM_SUBTYPES = {"category", "location", "person", "product", "status"}


def pct(x: float) -> str:
    return "<1%" if 0 < x < 0.005 else f"{x * 100:.0f}%"


def _trunc(s, n=40):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def table_findings(t: TableResult, sheet) -> list[Finding]:
    out: list[Finding] = []
    n = len(t.rows)

    def add(code, sev, title, detail, col=None, affected=None, total=None, rows=None, evidence=None):
        out.append(Finding(code, sev, title, detail, sheet=t.sheet, table_index=t.index,
                           column_pos=None if col is None else col.position, affected=affected, total=total,
                           sample_rows=[int(r) for r in (rows or [])[:10]], evidence=evidence or {}))

    # ---- structure
    if t.header_row is None or t.header_conf < 0.72:
        add("header_uncertain", "medium", "Potential issue: unsure which row holds the column names",
            "No clear header row was found, so some column names may be generic or wrong. "
            "Check the detected table range before relying on the results.")
    if t.total_rows:
        add("suspected_total_row", "info", f"{len(t.total_rows)} total row(s) left out of the data",
            "Rows that look like totals were excluded so they are not counted twice.",
            affected=len(t.total_rows), rows=t.total_rows)
    if t.blank_rows:
        add("blank_rows_inside", "info", f"{t.blank_rows} blank row(s) inside the table",
            "Blank rows were skipped. The rows before and after are treated as one table.")
    if t.repeated_header_rows:
        add("repeated_header_rows", "info", f"{t.repeated_header_rows} repeated header row(s) skipped",
            "Rows that repeat the column names inside the data were ignored.")
    if t.truncated:
        add("table_truncated", "medium", "Potential issue: only part of this table was analyzed",
            "The table is longer than the analysis limit, so the remaining rows were not included.")
    unnamed = [c.name for c in t.columns if c.original_label is None]
    if unnamed:
        add("unnamed_columns", "info", f"{len(unnamed)} column(s) have no header",
            "Columns without a header were given generic names (" + ", ".join(unnamed[:5]) + ").")

    # ---- duplicates (full rows)
    seen, dups = {}, []
    for i in range(n):
        key = tuple(c.values[i] for c in t.columns)
        if sum(1 for v in key if v is not None) < 2:
            continue
        if key in seen:
            dups.append(t.rows[i])
        else:
            seen[key] = t.rows[i]
    if dups:
        rate = len(dups) / n
        add("duplicate_rows", "medium" if rate >= 0.01 else "low",
            f"Potential issue: {len(dups)} duplicate row(s)",
            "These rows are identical to an earlier row in every column. They may be repeated entries "
            "and could be counted twice in totals.", affected=len(dups), total=n, rows=dups)

    for c in t.columns:
        valid = n - c.missing_count
        if c.role == "ignore" and c.role_subtype == "empty":
            continue

        # ---- missing values
        if c.role_subtype == "mostly_empty":
            add("mostly_empty_column", "low", f"“{c.name}” is almost empty ({pct(c.missing_count / n)} missing)",
                "This column has too few values to analyze reliably.", col=c, affected=c.missing_count, total=n,
                rows=c.missing_rows)
        elif c.missing_count:
            rate = c.missing_count / n
            sev = "high" if rate >= 0.3 else "medium" if rate >= 0.1 else "low"
            extra = f" {c.placeholder_count} of them are placeholders such as “N/A”." if c.placeholder_count else ""
            add("missing_values", sev, f"Potential issue: {c.missing_count} row(s) have no value in “{c.name}”",
                f"{pct(rate)} of rows are missing a value here.{extra} Totals and averages ignore these rows.",
                col=c, affected=c.missing_count, total=n, rows=c.missing_rows,
                evidence={"missing_rate": round(rate, 4), "placeholders": c.placeholder_count})

        # ---- identifiers
        if c.role == "identifier" and 0.9 <= c.uniqueness < 1.0 and c.base_type in ("text", "integer"):
            cnt = Counter(v for v in c.values if v is not None)
            repeated = {k for k, v in cnt.items() if v > 1}
            rows = [r for r, v in zip(t.rows, c.values) if v in repeated]
            add("duplicate_ids", "medium", f"Potential issue: repeated values in the identifier “{c.name}”",
                "An identifier column should hold unique values. Repeated ids may be duplicate records.",
                col=c, affected=len(rows), total=valid, rows=rows,
                evidence={"examples": [_trunc(k) for k in list(repeated)[:5]]})

        # ---- label consistency
        if c.role == "dimension" and c.role_subtype in DIM_SUBTYPES and c.base_type == "text" and c.distinct_count <= 500:
            groups = defaultdict(Counter)
            for v in c.values:
                if v is not None:
                    groups[norm_key(v)][str(v).strip()] += 1
            bad = {k: g for k, g in groups.items() if len(g) > 1}
            if bad:
                minority_values, affected = set(), 0
                for g in bad.values():
                    major = g.most_common(1)[0][0]
                    affected += sum(cnt for v, cnt in g.items() if v != major)
                    minority_values |= {v for v in g if v != major}
                rows = [r for r, v in zip(t.rows, c.values) if v is not None and str(v).strip() in minority_values]
                add("inconsistent_labels", "medium",
                    f"Potential issue: “{c.name}” spells the same value in different ways",
                    "Values that differ only by capitalization, accents, or spacing may be counted as separate "
                    "categories in charts and totals.", col=c, affected=affected, total=valid, rows=rows,
                    evidence={"groups": [[{"value": _trunc(v), "count": k} for v, k in g.most_common(4)]
                                         for g in list(bad.values())[:5]]})
            keys = [k for k in groups if k not in bad and len(k) >= 5][:150]
            pairs = []
            for i in range(len(keys)):
                for j in range(i + 1, len(keys)):
                    a, b = keys[i], keys[j]
                    if re.sub(r"\d", "", a) == re.sub(r"\d", "", b):
                        continue
                    if difflib.SequenceMatcher(None, a, b).ratio() >= 0.88:
                        pairs.append((a, b))
            if pairs:
                ex = [{"a": _trunc(next(iter(groups[a]))), "b": _trunc(next(iter(groups[b])))} for a, b in pairs[:5]]
                add("similar_entities", "low", f"Possible near-duplicate values in “{c.name}”",
                    "Some values are very similar and may be the same entity with a typo.", col=c,
                    affected=len(pairs), evidence={"pairs": ex})

        # ---- dates
        if c.base_type in ("date", "datetime") and c.date_info:
            di = c.date_info
            mixed = (di["real_dates"] and di["text_dates"]) or len(di["text_formats"]) > 1
            if di["conflict"]:
                add("mixed_date_formats", "high", f"Potential issue: “{c.name}” mixes day/month and month/day dates",
                    "Some text dates can only be day/month and others only month/day, so ambiguous dates may be "
                    "misread. Check the dates before trusting any monthly comparison.", col=c,
                    affected=di["text_dates"], total=valid, rows=di["text_date_rows"], evidence=di)
            elif mixed:
                add("mixed_date_formats", "low", f"Dates in “{c.name}” are stored in different ways",
                    f"{di['real_dates']} are real Excel dates and {di['text_dates']} are text "
                    f"({', '.join(di['text_formats']) or 'n/a'}). Text dates were converted automatically"
                    + (f"; {di['ambiguous']} could be day/month or month/day, so day/month was assumed."
                       if di["ambiguous"] and di["order_assumed"] == "dmy" else "."),
                    col=c, affected=di["text_dates"], total=valid, rows=di["text_date_rows"], evidence=di)
            elif di["ambiguous"] and di["text_dates"]:
                add("ambiguous_date_order", "low", f"Dates in “{c.name}” could be read two ways",
                    f"{di['ambiguous']} text dates could be day/month or month/day. "
                    f"We assumed {'month/day' if di['order_assumed'] == 'mdy' else 'day/month'}.",
                    col=c, affected=di["ambiguous"], total=valid, rows=di["text_date_rows"], evidence=di)

        # ---- invalid values / mixed types
        if c.invalid and c.base_type in ("integer", "decimal", "currency", "percentage", "date", "datetime", "boolean"):
            rate = len(c.invalid) / max(1, valid)
            kind = "numbers" if c.base_type in ("integer", "decimal", "currency", "percentage") else \
                "dates" if c.base_type in ("date", "datetime") else "yes/no values"
            add("invalid_values", "medium" if rate >= 0.05 else "low",
                f"Potential issue: {len(c.invalid)} value(s) in “{c.name}” are not valid {kind}",
                f"This column is mostly {kind}, but some cells contain text that could not be read as such. "
                "They are left out of calculations.", col=c, affected=len(c.invalid), total=valid,
                rows=[r for r, _ in c.invalid], evidence={"examples": [_trunc(v, 30) for _, v in c.invalid[:5]]})
        if c.mixed_shares and c.base_type == "text":
            add("mixed_types", "low", f"“{c.name}” mixes different kinds of values",
                "This column contains text together with numbers or dates, which may indicate inconsistent entry.",
                col=c, evidence={"shares": c.mixed_shares})

        # ---- suspicious negatives / zeros
        if c.role == "measure" and valid >= 10 and hints.any_hint(hints.tokens(c.name), hints.NON_NEGATIVE):
            vals = [(r, v) for r, v in zip(t.rows, c.values) if v is not None]
            pos = sum(1 for _, v in vals if v > 0)
            neg = [r for r, v in vals if v < 0]
            zero = [r for r, v in vals if v == 0]
            if pos / len(vals) >= 0.9 and (neg or zero):
                bits = ([f"{len(neg)} negative"] if neg else []) + ([f"{len(zero)} zero"] if zero else [])
                add("unexpected_negative_or_zero", "medium" if neg else "low",
                    f"Potential issue: {' and '.join(bits)} value(s) in “{c.name}”",
                    "Almost all values here are positive, so negatives or zeros may be entry errors "
                    "(or refunds, returns, or missing data).", col=c, affected=len(neg) + len(zero), total=len(vals),
                    rows=neg + zero, evidence={"negatives": len(neg), "zeros": len(zero)})

        # ---- outliers
        o = c.outliers
        if o and o["count_extreme"] and c.role != "identifier":
            k = o["count_extreme"]
            share = k / max(1, valid)
            fences = o["fences_extreme"]
            high = any(s["value"] is not None and fences[1] is not None and s["value"] > fences[1] for s in o["sample"])
            if k <= max(5, int(0.01 * valid)):
                add("extreme_outliers", "medium", f"Potential issue: {k} unusually {'large' if high else 'small'} "
                    f"value(s) in “{c.name}”",
                    "These values are far outside the usual range of this column. They may be genuine "
                    "exceptions or entry errors, and they can distort totals and averages.",
                    col=c, affected=k, total=valid, rows=[s["row"] for s in o["sample"]],
                    evidence={"method": o["method"], "fences": fences, "examples": o["sample"]})
            elif share < 0.15:
                add("wide_spread", "info", f"Values in “{c.name}” vary widely",
                    f"{k} values ({pct(share)}) are far above or below the typical range. This may be a normal "
                    "long tail rather than an error.", col=c, affected=k, total=valid,
                    rows=[s["row"] for s in o["sample"]], evidence={"method": o["method"], "fences": fences})

        if valid >= 10 and c.distinct_count == 1 and c.role != "ignore":
            add("constant_column", "info", f"“{c.name}” has the same value in every row",
                "A column that never changes cannot show differences between rows.", col=c, total=valid)

        # ---- formulas
        if c.formula_rows:
            frm = {r: sheet.formulas[(r, t.col0 + c.position)] for r in c.formula_rows
                   if (r, t.col0 + c.position) in sheet.formulas}
            bad = inconsistent_formulas(frm, t.col0 + c.position)
            if bad:
                add("formula_inconsistency", "medium",
                    f"Potential issue: {len(bad['rows'])} formula(s) in “{c.name}” differ from the rest",
                    f"{pct(bad['pattern_share'])} of formulas in this column follow one pattern; the others do not. "
                    "That can mean a copy-paste slip.", col=c, affected=len(bad["rows"]), total=len(frm),
                    rows=bad["rows"], evidence=bad)
            if 0.7 <= c.formula_share < 1.0:
                manual = [r for r, v in zip(t.rows, c.values) if v is not None and r not in c.formula_rows]
                if manual:
                    add("hardcoded_in_formula_column", "medium",
                        f"Potential issue: {len(manual)} typed value(s) among formulas in “{c.name}”",
                        "Most cells here are formulas, but a few were typed in by hand and will not update.",
                        col=c, affected=len(manual), total=n, rows=manual)

    # ---- formula errors inside this table
    errs = {k: v for k, v in sheet.errors.items()
            if t.first_data_row - 1 <= k[0] <= t.last_data_row and t.col0 <= k[1] <= t.col1}
    if errs:
        by = Counter(errs.values())
        add("formula_errors", "high", f"Potential issue: {len(errs)} cell(s) show an Excel error",
            "Errors such as " + ", ".join(list(by)[:3]) + " usually mean a broken formula or reference. "
            "Those cells are left out of calculations.", affected=len(errs),
            rows=sorted({r for r, _ in errs})[:10], evidence={"by_error": dict(by)})
    return out
