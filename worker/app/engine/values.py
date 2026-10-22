"""Cell-level classification: what kind of value is this, and what does it mean?"""
import math
import re
from collections import namedtuple
from datetime import date, datetime, time, timedelta

from .hints import CURRENCY_TOKENS
from .textutil import strip_accents

# kind: empty | placeholder | error | bool | boolword | number | datetime |
#       num_text | pct_text | cur_text | date_text | text
Cell = namedtuple("Cell", "kind val extra")

MISSING_MARKERS = {"", "n/a", "na", "n.a.", "null", "none", "nan", "-", "--", "—", "#n/a", "nd", "n.d.",
                   "vide", "?", "غير متوفر"}
ERROR_CODES = {"#DIV/0!", "#REF!", "#VALUE!", "#N/A", "#NAME?", "#NUM!", "#NULL!"}
BOOL_WORDS = {"true": True, "false": False, "vrai": True, "faux": False, "oui": True, "non": False,
              "yes": True, "no": False}

_CUR_RE = re.compile(r"(?<![a-z])(dzd|da|usd|eur|gbp)(?![a-z])|د\.?\s?ج|[$€£]", re.I)
_SPACED = re.compile(r"\d{1,3}( \d{3})+([.,]\d+)?")


def parse_numeric_text(s: str):
    """'1 234,50 DA' -> (1234.5, 'currency', 'DZD'); '15 %' -> (0.15, 'percent', None); else None."""
    t = s.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2212", "-").strip()
    if not t:
        return None
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg, t = True, t[1:-1].strip()
    currency = None
    m = _CUR_RE.search(t)
    if m:
        currency = CURRENCY_TOKENS.get(re.sub(r"[.\s]", "", m.group(0)).casefold())
        t = (t[: m.start()] + " " + t[m.end():]).strip()
    pct = False
    if t.endswith("%"):
        pct, t = True, t[:-1].strip()
    if t.startswith("+"):
        t = t[1:].strip()
    elif t.startswith("-"):
        neg, t = True, t[1:].strip()
    if not t or not re.fullmatch(r"[\d ,.']+", t) or not re.search(r"\d", t):
        return None
    if " " in t and not _SPACED.fullmatch(t):
        return None
    t = t.replace(" ", "").replace("'", "")
    if re.fullmatch(r"0\d+", t):  # leading-zero codes (phones, ids) stay text
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", t) else t.replace(",", ".")
    elif t.count(".") > 1:
        if not re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
            return None
        t = t.replace(".", "")
    try:
        v = float(t)
    except ValueError:
        return None
    if neg:
        v = -v
    if pct:
        return v / 100.0, "percent", currency
    return v, ("currency" if currency else "number"), currency


# ------------------------------------------------------------------ dates

MONTHS: dict[str, int] = {}
for _m, _names in enumerate(
    [["janvier", "janv", "jan", "january"], ["fevrier", "fevr", "fev", "feb", "february"], ["mars", "mar", "march"],
     ["avril", "avr", "apr", "april"], ["mai", "may"], ["juin", "jun", "june"], ["juillet", "juil", "jul", "july"],
     ["aout", "aou", "aug", "august"], ["septembre", "sept", "sep", "september"], ["octobre", "oct", "october"],
     ["novembre", "nov", "november"], ["decembre", "dec", "december"]], start=1):
    for _n in _names:
        MONTHS[_n] = _m

_TIME = r"(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?"
_RE_NUMERIC = re.compile(r"^(\d{1,2})([/\-.])(\d{1,2})\2(\d{4}|\d{2})" + _TIME + r"$")
_RE_YMD = re.compile(r"^(\d{4})([/\-.])(\d{1,2})\2(\d{1,2})" + _TIME + r"$")
_RE_DMONY = re.compile(r"^(\d{1,2})(?:er)?[ \-/]+([^\W\d_]+)\.?[ \-/,]+(\d{4})$")
_RE_MONDY = re.compile(r"^([^\W\d_]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})$")

# order: fixed (unambiguous) | dmy_certain | mdy_certain | ambiguous
DateText = namedtuple("DateText", "fmt order day month year hour minute second")


def _year(y: str) -> int:
    n = int(y)
    return n if len(y) == 4 else (2000 + n if n < 70 else 1900 + n)


def parse_date_text(s: str):
    t = s.strip()
    m = _RE_YMD.match(t)
    if m:
        y, sep, mo, d, hh, mi, ss = m.groups()
        return DateText(f"Y{sep}m{sep}d", "fixed", int(d), int(mo), int(y), int(hh or 0), int(mi or 0), int(ss or 0))
    m = _RE_NUMERIC.match(t)
    if m:
        a, sep, b, y, hh, mi, ss = m.groups()
        a, b = int(a), int(b)
        if a > 12 and b > 12:
            return None
        if a > 12:
            order, day, month = "dmy_certain", a, b
        elif b > 12:
            order, day, month = "mdy_certain", b, a
        else:
            order, day, month = "ambiguous", a, b
        fmt = f"d{sep}m{sep}" + ("Y" if len(y) == 4 else "y")
        return DateText(fmt, order, day, month, _year(y), int(hh or 0), int(mi or 0), int(ss or 0))
    m = _RE_DMONY.match(t)
    if m:
        mo = MONTHS.get(strip_accents(m.group(2)).casefold())
        if mo:
            return DateText("d month Y", "fixed", int(m.group(1)), mo, int(m.group(3)), 0, 0, 0)
    m = _RE_MONDY.match(t)
    if m:
        mo = MONTHS.get(strip_accents(m.group(1)).casefold())
        if mo:
            return DateText("month d, Y", "fixed", int(m.group(2)), mo, int(m.group(3)), 0, 0, 0)
    return None


def resolve_date(dt: DateText, prefer: str = "dmy"):
    """Build a datetime. `prefer` only matters for ambiguous dd/mm vs mm/dd values."""
    day, month = dt.day, dt.month
    if dt.order == "ambiguous" and prefer == "mdy":
        day, month = month, day
    try:
        return datetime(dt.year, month, day, dt.hour, dt.minute, dt.second)
    except ValueError:
        return None


# ------------------------------------------------------------------ classification

def classify_cell(v) -> Cell:
    if v is None:
        return Cell("empty", None, None)
    if isinstance(v, bool):
        return Cell("bool", v, None)
    if isinstance(v, (int, float)):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return Cell("empty", None, None)
        return Cell("number", float(v), float(v).is_integer())
    if isinstance(v, datetime):
        return Cell("datetime", v, None)
    if isinstance(v, date):
        return Cell("datetime", datetime(v.year, v.month, v.day), None)
    if isinstance(v, (time, timedelta)):
        return Cell("text", str(v), None)
    s = str(v).strip()
    low = s.casefold()
    if low in MISSING_MARKERS:
        return Cell("placeholder" if s else "empty", None, s)
    if s.upper() in ERROR_CODES:
        return Cell("error", None, s)
    if low in BOOL_WORDS:
        return Cell("boolword", BOOL_WORDS[low], s)
    num = parse_numeric_text(s)
    if num is not None:
        value, kind, cur = num
        k = {"percent": "pct_text", "currency": "cur_text"}.get(kind, "num_text")
        return Cell(k, value, (cur, float(value).is_integer()))
    dt = parse_date_text(s)
    if dt is not None:
        return Cell("date_text", dt, s)
    return Cell("text", s, None)
