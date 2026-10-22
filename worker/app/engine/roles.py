"""Phase E (deterministic part) — assign each column a role (report §4.2).

Roles: measure | dimension | time | identifier | text | ignore
Subtypes: quantity amount price rate generic | category location person product status period flag ordinal | date
Every assignment carries a confidence; low-confidence guesses are never presented as certain.
"""
import re

from . import hints
from .columns import ColumnResult

_CODE_LIKE = re.compile(r"^[A-Za-z]{1,6}[-_/ ]?\d{2,}$")


def _is_identifier(col: ColumnResult, toks: list[str]) -> float:
    n_valid = col.n_rows - col.missing_count
    id_hint = hints.any_hint(toks, hints.ID) or bool(re.match(r"^n[°o]\b", (col.original_label or "").strip(), re.I))
    if col.base_type in ("integer", "text") or col.base_type == "decimal":
        if id_hint and col.uniqueness >= 0.9:
            return 0.95
        if id_hint and col.uniqueness >= 0.5 and col.base_type != "decimal":
            return 0.8
    if col.base_type == "text" and n_valid >= 10 and col.uniqueness >= 0.98 and col.avg_len <= 24:
        vals = [str(v) for v in col.values if v is not None][:200]
        if sum(1 for v in vals if _CODE_LIKE.match(v)) / len(vals) >= 0.8:
            return 0.9
    if col.base_type == "integer" and n_valid >= 10 and col.uniqueness == 1.0 \
            and not hints.any_hint(toks, hints.QUANTITY | hints.AMOUNT | hints.PRICE):
        vals = [v for v in col.values if v is not None]
        if all(b >= a for a, b in zip(vals, vals[1:])):
            return 0.6
    return 0.0


def assign_role(col: ColumnResult) -> None:
    toks = hints.tokens(col.name)
    t = col.base_type
    n_valid = col.n_rows - col.missing_count

    if t == "empty" or n_valid == 0:
        col.role, col.role_subtype, col.role_confidence = "ignore", "empty", 1.0
        return
    if col.n_rows >= 10 and col.missing_count / col.n_rows >= 0.95:
        col.role, col.role_subtype, col.role_confidence = "ignore", "mostly_empty", 0.9
        return

    idc = _is_identifier(col, toks)
    if idc:
        col.role, col.role_subtype, col.role_confidence = "identifier", None, idc
        col.data_type = "identifier"
        return
    if t in ("date", "datetime"):
        col.role, col.role_subtype, col.role_confidence = "time", "date", col.type_confidence
        return
    if t == "boolean":
        col.role, col.role_subtype, col.role_confidence = "dimension", "flag", 0.8
        return

    if t in ("integer", "decimal", "currency", "percentage"):
        if hints.any_hint(toks, hints.PERIOD) and t == "integer" and col.distinct_count <= 40:
            col.role, col.role_subtype, col.role_confidence = "dimension", "period", 0.85
            return
        measure_hint = hints.any_hint(toks, hints.QUANTITY | hints.AMOUNT | hints.PRICE | hints.RATE)
        if t == "integer" and col.distinct_count <= 10 and col.uniqueness < 0.05 and not measure_hint:
            col.role, col.role_subtype, col.role_confidence = "dimension", "ordinal", 0.55
            return
        if t == "percentage" or hints.any_hint(toks, hints.RATE):
            sub = "rate"
        elif hints.any_hint(toks, hints.PRICE):
            sub = "price"
        elif t == "currency" or hints.any_hint(toks, hints.AMOUNT):
            sub = "amount"
        elif hints.any_hint(toks, hints.QUANTITY):
            sub = "quantity"
        else:
            sub = "generic"
        conf = 0.9 if (measure_hint or t in ("currency", "percentage")) else 0.75
        col.role, col.role_subtype, col.role_confidence = "measure", sub, conf
        return

    # text
    sub = None
    for vocab, name in ((hints.LOCATION, "location"), (hints.PERSON, "person"), (hints.PRODUCT, "product"),
                        (hints.STATUS, "status"), (hints.CATEGORY, "category"), (hints.PERIOD, "period")):
        if hints.any_hint(toks, vocab):
            sub = name
            break
    free_text = col.avg_len > 40 or (col.uniqueness > 0.8 and col.distinct_count > 50)
    if free_text and sub not in ("person", "product"):
        col.role, col.role_subtype, col.role_confidence = "text", None, 0.7
        return
    low_card = col.distinct_count <= 100 or col.uniqueness <= 0.5
    if low_card:
        col.role, col.role_subtype = "dimension", sub or "category"
        col.role_confidence = 0.9 if sub else 0.7
        return
    if sub in ("person", "product", "location"):
        col.role, col.role_subtype, col.role_confidence = "dimension", sub, 0.7
        return
    col.role, col.role_subtype, col.role_confidence = "text", None, 0.5
