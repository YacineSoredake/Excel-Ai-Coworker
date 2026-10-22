"""Phase C — normalize + type detection for one column (report §4.2)."""
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from . import hints
from .values import Cell, classify_cell, resolve_date

NUM_KINDS = {"number", "num_text", "pct_text", "cur_text"}
DATE_KINDS = {"datetime", "date_text"}
BOOL_KINDS = {"bool", "boolword"}
MISSING_KINDS = {"empty", "placeholder", "error"}


@dataclass
class ColumnResult:
    position: int  # 0-based position inside the table
    letter: str
    name: str
    original_label: str | None
    rows: list  # Excel row numbers, aligned with values
    values: list  # cleaned python values, None where missing/invalid
    kinds: Counter
    data_type: str = "text"  # text integer decimal currency percentage date datetime boolean identifier empty
    base_type: str = "text"
    type_confidence: float = 0.0
    currency: str | None = None
    unit: str | None = None
    number_format: str | None = None
    formula_share: float = 0.0
    formula_rows: set = field(default_factory=set)
    missing_rows: list = field(default_factory=list)
    placeholder_count: int = 0
    invalid: list = field(default_factory=list)  # [(row, raw text)] text inside numeric/date columns
    mixed_shares: dict = field(default_factory=dict)  # for text columns that also hold numbers/dates
    date_info: dict = field(default_factory=dict)
    # filled later
    role: str = "ignore"
    role_subtype: str | None = None
    role_confidence: float = 0.0
    n_rows: int = 0
    missing_count: int = 0
    distinct_count: int = 0
    uniqueness: float = 0.0
    avg_len: float = 0.0
    stats: dict = field(default_factory=dict)
    outliers: dict | None = None


def _majority(items):
    items = [i for i in items if i]
    return Counter(items).most_common(1)[0][0] if items else None


def analyze_column(*, position, letter, name, original_label, raw, rows, formats, formula_rows) -> ColumnResult:
    cells: list[Cell] = [classify_cell(v) for v in raw]
    kinds = Counter(c.kind for c in cells)
    n = len(cells)
    missing = sum(kinds[k] for k in MISSING_KINDS)
    nm = n - missing
    col = ColumnResult(position=position, letter=letter, name=name, original_label=original_label,
                       rows=rows, values=[None] * n, kinds=kinds, n_rows=n)
    col.missing_rows = [rows[i] for i, c in enumerate(cells) if c.kind in MISSING_KINDS]
    col.missing_count = len(col.missing_rows)
    col.placeholder_count = kinds["placeholder"]
    col.formula_rows = {r for r in rows if r in formula_rows}
    denom = sum(1 for i, c in enumerate(cells) if c.kind != "empty" or rows[i] in formula_rows)
    col.formula_share = round(len(col.formula_rows) / denom, 3) if denom else 0.0
    col.number_format = _majority(formats)
    h_cur, h_unit = hints.header_currency_and_unit(original_label or name)
    col.unit = h_unit

    if nm == 0:
        col.data_type = col.base_type = "empty"
        col.type_confidence = 1.0
        return col

    num = sum(kinds[k] for k in NUM_KINDS)
    dat = sum(kinds[k] for k in DATE_KINDS)
    boo = sum(kinds[k] for k in BOOL_KINDS)
    txt = nm - num - dat - boo
    shares = {"numeric": num / nm, "date": dat / nm, "boolean": boo / nm, "text": txt / nm}
    dominant = max(shares, key=shares.get)
    share = shares[dominant]
    distinct_nonmissing = len({repr(c.val) for c in cells if c.kind not in MISSING_KINDS})
    if dominant == "boolean" and (share < 0.9 or distinct_nonmissing > 3):
        dominant = "text"
    if dominant != "text" and share < 0.6:
        dominant = "text"
    col.type_confidence = round(share if dominant != "text" else max(0.5, shares["text"]), 2)

    if dominant == "numeric":
        _numeric(col, cells, num, h_cur)
    elif dominant == "date":
        _dates(col, cells)
    elif dominant == "boolean":
        col.data_type = col.base_type = "boolean"
        col.values = [c.val if c.kind in BOOL_KINDS else None for c in cells]
        col.invalid = [(rows[i], str(raw[i])[:40]) for i, c in enumerate(cells) if c.kind == "text"]
    else:
        col.data_type = col.base_type = "text"
        col.values = [_as_text(c) for c in cells]
        col.mixed_shares = {k: round(v, 3) for k, v in shares.items() if k != "text" and v >= 0.05}
        if col.mixed_shares:
            col.invalid = []
    return col


def _as_text(c: Cell):
    if c.kind in MISSING_KINDS:
        return None
    if c.kind == "datetime":
        return c.val.isoformat(sep=" ") if (c.val.hour or c.val.minute or c.val.second) else c.val.date().isoformat()
    if c.kind in ("boolword", "date_text"):
        return str(c.extra)
    if c.kind == "bool":
        return str(c.val)
    if c.kind == "number":
        return str(int(c.val)) if c.extra else repr(c.val)
    if c.kind in ("num_text", "pct_text", "cur_text"):
        return None if c.val is None else str(c.val)
    return c.val


def _numeric(col: ColumnResult, cells, num_count, header_currency):
    rows = col.rows
    pct_cells = sum(1 for c in cells if c.kind == "pct_text")
    cur_cells = [c.extra[0] for c in cells if c.kind == "cur_text"]
    fmt = col.number_format or ""
    pct = (pct_cells / max(1, num_count) >= 0.5) or ("%" in fmt and "%%" not in fmt)
    fmt_cur = hints.currency_from_format(fmt)
    cur_code = _majority(cur_cells) or fmt_cur or header_currency
    is_cur = len(cur_cells) / max(1, num_count) >= 0.3 or fmt_cur is not None or header_currency is not None
    vals, ints = [], True
    for i, c in enumerate(cells):
        if c.kind in NUM_KINDS:
            v = c.val
            vals.append(v)
            is_int = c.extra if c.kind == "number" else c.extra[1]
            ints = ints and bool(is_int)
        else:
            vals.append(None)
            if c.kind not in MISSING_KINDS:
                col.invalid.append((rows[i], str(c.extra if c.extra and c.kind != "text" else c.val)[:40]))
    col.values = vals
    if pct:
        col.data_type = "percentage"
    elif is_cur:
        col.data_type = "currency"
        col.currency = cur_code
    elif ints:
        col.data_type = "integer"
    else:
        col.data_type = "decimal"
    col.base_type = col.data_type
    if col.data_type == "currency" and ints:
        col.base_type = "currency"
    nn = [v for v in vals if v is not None]
    if nn and set(nn) <= {0.0, 1.0} and len(nn) >= 5 and col.data_type == "integer" \
            and hints.any_hint(hints.tokens(col.name), hints.BOOLEAN_HINTS):
        col.data_type = col.base_type = "boolean"
        col.values = [None if v is None else bool(v) for v in vals]


def _dates(col: ColumnResult, cells):
    rows = col.rows
    real = sum(1 for c in cells if c.kind == "datetime")
    texts = [c for c in cells if c.kind == "date_text"]
    orders = Counter(c.val.order for c in texts)
    prefer = "mdy" if orders["mdy_certain"] and not orders["dmy_certain"] else "dmy"
    fmts = Counter(c.val.fmt for c in texts)
    vals, has_time = [], False
    for i, c in enumerate(cells):
        d = None
        if c.kind == "datetime":
            d = c.val
        elif c.kind == "date_text":
            d = resolve_date(c.val, prefer)
            if d is None:
                col.invalid.append((rows[i], str(c.extra)[:40]))
        elif c.kind not in MISSING_KINDS:
            col.invalid.append((rows[i], str(c.val if c.kind == "text" else c.extra)[:40]))
        if d is not None and (d.hour or d.minute or d.second):
            has_time = True
        vals.append(d)
    col.values = vals
    col.data_type = col.base_type = "datetime" if has_time else "date"
    col.date_info = {
        "real_dates": real, "text_dates": len(texts), "text_formats": dict(fmts),
        "order_assumed": prefer, "ambiguous": orders["ambiguous"],
        "conflict": bool(orders["mdy_certain"] and orders["dmy_certain"]),
        "mdy_certain": orders["mdy_certain"], "dmy_certain": orders["dmy_certain"],
        "text_date_rows": [rows[i] for i, c in enumerate(cells) if c.kind == "date_text"][:20],
    }
