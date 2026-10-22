"""Phase B/C — find the real tables inside a sheet.

The report says: do not assume every workbook has a clean rectangular table.
So we split a sheet into blocks of content, find each block's header row,
drop title/notes above it, drop total rows below it, and keep a confidence.
"""
import re
from dataclasses import dataclass, field

from .parse import SheetData
from .textutil import norm_key
from .values import classify_cell

TOTAL_RE = re.compile(
    r"^(total|totaux|sous[\s-]?total|grand\s+total|somme|moyenne|average|sum|subtotal|المجموع|الإجمالي|اجمالي)\b",
    re.I)
SUM_FN = re.compile(r"\b(SUM|SUBTOTAL|AVERAGE|SOMME)\s*\(", re.I)


def is_empty(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


@dataclass
class TableCandidate:
    source: str  # detected | excel_table
    name: str | None
    c0: int  # 0-based inclusive columns
    c1: int
    header_row: int | None  # 0-based row index in sheet.rows
    data_r0: int
    data_r1: int
    block_r0: int
    block_r1: int
    header_conf: float
    confidence: float = 0.0
    preamble: list = field(default_factory=list)
    total_rows: list = field(default_factory=list)  # 0-based
    blank_rows_inside: int = 0


def _bands(flags):
    out, start = [], None
    for i, h in enumerate(flags):
        if h and start is None:
            start = i
        if not h and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(flags) - 1))
    return out


def _header_scores(rows, r0, r1, c0, c1):
    width = c1 - c0 + 1
    scores = {}
    for r in range(r0, min(r1, r0 + 14)):
        cells = [rows[r][c] for c in range(c0, c1 + 1) if not is_empty(rows[r][c])]
        if not cells:
            continue
        fill = len(cells) / width
        strs = [v for v in cells if isinstance(v, str)]
        str_share = len(strs) / len(cells)
        keys = [norm_key(s) for s in strs]
        uniq = len(set(keys)) / len(keys) if keys else 0.0
        datalike = 0.0
        if strs:
            bad = sum(1 for s in strs if len(s) > 60 or classify_cell(s).kind in
                      ("num_text", "pct_text", "cur_text", "date_text"))
            datalike = bad / len(strs)
        nxt = rows[r + 1] if r + 1 <= r1 else []
        nxt_cells = [nxt[c] for c in range(c0, c1 + 1) if not is_empty(nxt[c])] if nxt else []
        nxt_fill = len(nxt_cells) / width
        contrast = any(
            isinstance(rows[r][c], str) and not is_empty(rows[r][c]) and not isinstance(nxt[c], str)
            and not is_empty(nxt[c]) for c in range(c0, c1 + 1)) if nxt else False
        score = (0.30 * fill + 0.30 * str_share + 0.15 * uniq + 0.15 * (1 - datalike)
                 + 0.10 * (1.0 if (contrast or nxt_fill >= 0.5) else 0.0))
        scores[r] = (score, fill, str_share)
    return scores


def _find_header(rows, r0, r1, c0, c1):
    """A header row is mostly text, nearly as wide as the table, and unlike the rows below it."""
    scores = _header_scores(rows, r0, r1, c0, c1)
    if not scores:
        return None, 0.0
    max_fill = max(v[1] for v in scores.values())
    for r in sorted(scores):
        sc, f, ss = scores[r]
        if sc >= 0.72 and f >= 0.6 * max_fill and ss >= 0.75:
            return r, sc
    ok = {r: v for r, v in scores.items() if v[2] >= 0.6 and v[1] >= 0.6 * max_fill and v[0] >= 0.55}
    if ok:
        r, v = max(ok.items(), key=lambda kv: kv[1][0])
        return r, min(v[0], 0.65)  # accepted, but flagged as a weak header
    return None, max(v[0] for v in scores.values())


def _row_has_total_formula(sheet: SheetData, r: int, c0: int, c1: int) -> bool:
    return any(SUM_FN.search(sheet.formulas.get((r + 1, c + 1), "")) for c in range(c0, c1 + 1))


def _is_total_row(sheet: SheetData, r: int, c0: int, c1: int) -> bool:
    row = sheet.rows[r]
    width = c1 - c0 + 1
    filled = [c for c in range(c0, c1 + 1) if not is_empty(row[c])]
    if not filled:
        return False
    label = row[filled[0]]
    has_formula = _row_has_total_formula(sheet, r, c0, c1)
    if isinstance(label, str) and TOTAL_RE.match(label.strip()):
        return len(filled) / width <= 0.8 or has_formula
    return False


def detect_tables(sheet: SheetData):
    rows = sheet.rows
    notes: list[str] = []
    if not rows:
        return [], notes
    nrows, ncols = len(rows), len(rows[0])
    nonempty = [[not is_empty(v) for v in row] for row in rows]
    candidates: list[TableCandidate] = []

    # 1) tables the author defined in Excel
    for et in sheet.excel_tables:
        r0, r1, c0, c1 = et.min_row - 1, et.max_row - 1, et.min_col - 1, et.max_col - 1
        if r0 >= nrows or c0 >= ncols:
            continue
        r1, c1 = min(r1, nrows - 1), min(c1, ncols - 1)
        hdr = r0 if et.header_rows else None
        d0 = r0 + (1 if et.header_rows else 0)
        d1 = r1 - et.totals_rows
        candidates.append(TableCandidate("excel_table", et.name, c0, c1, hdr, d0, d1, r0, r1, 0.99, 0.99))
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                nonempty[r][c] = False

    # 2) everything else: bands separated by empty rows, split by empty columns
    for (br0, br1) in _bands([any(r) for r in nonempty]):
        col_flags = [any(nonempty[r][c] for r in range(br0, br1 + 1)) for c in range(ncols)]
        for (c0, c1) in _bands(col_flags):
            rr = [r for r in range(br0, br1 + 1) if any(nonempty[r][c] for c in range(c0, c1 + 1))]
            r0, r1 = rr[0], rr[-1]
            n_rows, n_cols = r1 - r0 + 1, c1 - c0 + 1
            cells = sum(1 for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if nonempty[r][c])
            if n_rows < 2 or cells <= 3 or (n_cols == 1 and n_rows < 3):
                notes.extend(str(rows[r][c]).strip()[:200] for r in range(r0, r1 + 1)
                             for c in range(c0, c1 + 1) if nonempty[r][c])
                continue
            hdr, hscore = _find_header(rows, r0, r1, c0, c1)
            pre = []
            if hdr is None:
                d0 = r0
            else:
                d0 = hdr + 1
                for r in range(r0, hdr):
                    pre.extend(str(rows[r][c]).strip()[:200] for c in range(c0, c1 + 1) if nonempty[r][c])
            cand = TableCandidate("detected", None, c0, c1, hdr, d0, r1, r0, r1, hscore, preamble=pre[:5])
            candidates.append(cand)

    candidates.sort(key=lambda t: (t.block_r0, t.c0))

    # 3) a block with no header that sits right under a table of the same width is a continuation
    merged: list[TableCandidate] = []
    for cand in candidates:
        prev = merged[-1] if merged else None
        weak = cand.header_row is None or cand.header_conf < 0.72
        if (prev and cand.source == "detected" and weak and prev.source == "detected"
                and prev.header_row is not None and abs(prev.c0 - cand.c0) <= 1 and abs(prev.c1 - cand.c1) <= 1
                and 0 < cand.block_r0 - prev.data_r1 <= 4):
            prev.blank_rows_inside += cand.block_r0 - prev.data_r1 - 1
            prev.data_r1 = cand.data_r1
            prev.block_r1 = cand.block_r1
            continue
        merged.append(cand)

    # 4) total rows at the bottom, then confidence
    for t in merged:
        r = t.data_r1
        while r >= t.data_r0 and len(t.total_rows) < 3:
            if is_empty_row(rows[r], t.c0, t.c1):
                r -= 1
                continue
            if _is_total_row(sheet, r, t.c0, t.c1):
                t.total_rows.append(r)
                r -= 1
            else:
                break
        if t.total_rows:
            t.data_r1 = min(t.total_rows) - 1
            while t.data_r1 >= t.data_r0 and is_empty_row(rows[t.data_r1], t.c0, t.c1):
                t.data_r1 -= 1
        n = max(0, t.data_r1 - t.data_r0 + 1)
        data_cells = sum(1 for r in range(t.data_r0, t.data_r1 + 1) for c in range(t.c0, t.c1 + 1)
                         if not is_empty(rows[r][c]))
        fill = data_cells / max(1, n * (t.c1 - t.c0 + 1))
        if t.source == "detected":
            t.confidence = round(min(0.99, 0.5 * t.header_conf + 0.3 * min(1.0, n / 10) + 0.2 * fill), 2)
            if t.header_row is None:
                t.confidence = min(t.confidence, 0.4)
        t.header_conf = round(t.header_conf, 2)
    return [t for t in merged if t.data_r1 >= t.data_r0], notes


def is_empty_row(row, c0, c1) -> bool:
    return all(is_empty(row[c]) for c in range(c0, c1 + 1))
