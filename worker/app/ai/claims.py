"""Claim validation (report §6.1: "a validation layer checks that generated claims correspond to available computed facts",
§6.3: avoid false causality, §22: measure the unsupported-claim rate).

Anything the LLM writes passes through here. A text is accepted only if
  - every number can be traced to the evidence (verified facts or an executed query result),
  - every period/date mentioned appears in the evidence,
  - every proper name mentioned appears in the evidence or the workbook's own vocabulary,
  - it does not state a cause, and does not contradict the direction of a change.
Failing texts are never shown; the caller falls back to deterministic wording.
"""
import math
import re
from dataclasses import dataclass, field

from ..engine.textutil import strip_accents

CAUSAL = re.compile(
    r"\b(because|caus(?:e|es|ed|ing)|due to|driven by|thanks to|as a result|led to|leads? to|results? in|"
    r"resulted in|owing to|responsible for|explains? why|reasons? (?:for|why))\b", re.I)
HEDGE = re.compile(r"\b(may|might|could|possibly|perhaps|suggests?|one possibility|it is possible|worth checking)\b", re.I)
UP = re.compile(r"\b(increas\w*|rose|rise|rising|grew|grow\w*|up|higher|gain\w*|improv\w*)\b", re.I)
DOWN = re.compile(r"\b(decreas\w*|fell|fall\w*|drop\w*|declin\w*|down|lower|loss|shrank|shrink\w*)\b", re.I)

SHARE_KEYS = ("share", "change_pct", "attainment", "pct", "containment", "missing_rate", "uniqueness", "match_share")
_PERIOD = re.compile(r"\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}|\d{4}-\d{2}-\d{2}|\d{4}-\d{2}(?!\d)|\d{4}Q[1-4]|(?<![\d.,])(?:19|20)\d{2}(?![\d.,])")
_NUM = re.compile(
    r"(?<![\w.,/-])[-+\u2212]?(?:\d{1,3}(?:[ \u00a0\u202f,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    r"(?:\s?(?:%|(?:thousand|million|billion|bn|[kmb])(?![a-z])))?", re.I)
_PROPER = re.compile(r"\b[A-ZÀ-ÖØ-Þ][\wÀ-ÿ'’-]*")
_SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "bn": 1e9, "billion": 1e9}
# ordinary words that begin sentences; anything else capitalised at the start must come from the evidence
_STARTERS = {"the", "this", "these", "those", "it", "its", "overall", "in", "on", "for", "between", "compared", "most", "total",
             "average", "sales", "revenue", "quantity", "records", "rows", "prices", "price", "values", "value", "about",
             "around", "both", "each", "every", "there", "over", "during", "from", "across", "among", "with", "within",
             "while", "after", "before", "since", "only", "just", "nearly", "almost", "roughly", "at", "together", "combined",
             "notably", "specifically", "another", "one", "two", "three", "which", "what", "how", "when", "where", "who", "why",
             "compare", "check", "look", "review", "filter", "inspect", "see", "find", "ask", "show", "list", "is", "are",
             "was", "were", "do", "does", "did", "can", "could", "may", "might", "some", "many", "few", "no", "all", "any",
             "if", "but", "and", "so", "as", "by", "to", "of", "a", "an", "i", "we", "you", "amounts", "amount", "numbers",
             "they", "their", "them", "he", "she", "his", "her", "our", "your", "then", "here", "also", "still", "yet", "thus", "hence",
             "meanwhile", "instead", "otherwise", "although", "though", "because", "until", "unless", "whether", "either", "neither",
             "such", "more", "less", "fewer", "other", "others", "least", "first", "last", "next", "previous", "latest", "earlier", "later",
             "recent", "currently", "mostly", "mainly", "largely", "slightly", "sharply", "steadily", "month", "months", "week", "weeks",
             "year", "years", "day", "days", "quarter", "figures", "data", "results", "increase", "decrease", "growth", "decline", "peak",
             "trend", "change", "changes", "top", "bottom", "highest", "lowest", "biggest", "largest", "smallest", "median", "typical",
             "usually", "generally", "typically", "per", "than", "that", "not", "has", "have", "had", "be", "been", "being", "whose", "whom"}
_COMMON = {"excel", "dzd", "usd", "eur", "gbp", "january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday",
           "saturday", "sunday", "i", "this", "the", "a", "an", "it", "these", "those", "there", "overall", "however"}


@dataclass
class Evidence:
    texts: list = field(default_factory=list)  # headlines, labels, column names, definitions...
    data: list = field(default_factory=list)  # payload-like structures holding the numbers


@dataclass
class Check:
    ok: bool
    issues: list = field(default_factory=list)


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def parse_number(tok: str):
    """'7,196,350' -> (7196350.0, 0, 1, False); '1.2M' -> (1.2, 1, 1e6, False); '-26%' -> (26.0, 0, 1, True)."""
    m = re.match(r"^([-+\u2212]?)(.*?)(?:\s?(%|thousand|million|billion|bn|[kmb]))?$", tok.strip(), re.I)
    sign, body, suf = m.group(1), m.group(2), (m.group(3) or "").lower()
    s = re.sub(r"[ \u00a0\u202f]", "", body)
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    elif s.count(".") > 1 or re.fullmatch(r"\d{1,3}(\.\d{3}){2,}", s):
        s = s.replace(".", "")
    frac = s.split(".")[1] if "." in s else ""
    try:
        v = float(s)
    except ValueError:
        return None
    return v, len(frac), _SCALE.get(suf, 1.0), suf == "%"


def _collect(obj, key: str, plain: set, pct: set) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if _finite(obj):
        plain.add(abs(float(obj)))
        if key.endswith(SHARE_KEYS):
            pct.add(abs(float(obj)) * 100)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _collect(v, str(k), plain, pct)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect(v, key, plain, pct)
    elif isinstance(obj, str):
        for t in [m.group(0) for m in _NUM.finditer(_PERIOD.sub(' ', obj))]:
            p = parse_number(t)
            if p:
                plain.add(p[0] * p[2])


def allowed_numbers(ev: Evidence):
    plain, pct = set(), set()
    for d in ev.data:
        _collect(d, "", plain, pct)
    for t in ev.texts:  # headlines contain formatted numbers too
        for m in _NUM.finditer(PERIODS_STRIPPED(t)):
            p = parse_number(m.group(0))
            if p:
                plain.add(p[0] * p[2])
                if p[3]:
                    pct.add(p[0])
    return plain, pct


def PERIODS_STRIPPED(s: str) -> str:
    return _PERIOD.sub(" ", s)


def _norm_words(s: str) -> set:
    return {w for w in re.split(r"\W+", strip_accents(s).casefold()) if w}


def _corpus(ev: Evidence) -> tuple[str, set]:
    parts = list(ev.texts)

    def walk(o):
        if isinstance(o, str):
            parts.append(o)
        elif isinstance(o, dict):
            for k, v in o.items():
                parts.append(str(k))
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)
    for d in ev.data:
        walk(d)
    joined = " ".join(parts)
    return joined, _norm_words(joined)


def check_text(text: str, ev: Evidence, *, kind: str = "statement", known_good: str | None = None) -> Check:
    """kind: statement (facts only) | interpretation (hedged, no numbers) | next_check (a suggestion, no numbers)."""
    issues = []
    t = (text or "").strip()
    if not t:
        return Check(False, ["empty"])
    if len(t) > (300 if kind == "statement" else 220):
        issues.append("too_long")
    if CAUSAL.search(t):
        issues.append("causal_claim")
    joined, words = _corpus(ev)

    if kind in ("interpretation", "next_check"):
        if re.search(r"\d", t):
            issues.append("numbers_in_" + kind)
        if kind == "interpretation" and not HEDGE.search(t):
            issues.append("interpretation_not_hedged")
        if kind == "next_check" and not (t.endswith("?") or re.match(r"^(check|compare|look|review|filter|inspect|see|find|ask)\b", t, re.I)):
            issues.append("next_check_not_actionable")
    else:
        letter_words = re.findall(r"[^\W\d_]+", t)
        own = [w for w in letter_words if strip_accents(w).casefold() not in words]
        if (len(letter_words) < 3 or not own) and t != (known_good or "").strip():
            # a bare number, a label, or the label repeated with its number: true but unhelpful, so the built-in wording is better
            issues.append("not_a_sentence")
        if re.search(r"(?<![\d.,])\d{5,}(?:\.\d+)?(?![\d,])|(?<![\d.,])\d{4}\.\d+|(?<![\d.])\d[\d,]{3,}\.0(?!\d)", _PERIOD.sub(" ", t)):
            issues.append("unformatted_number")  # 7196350.0 instead of 7,196,350
        plain, pct = allowed_numbers(ev)
        remaining = t
        for m in _PERIOD.finditer(t):
            tok = m.group(0)
            if tok in joined:
                continue
            if re.fullmatch(r"(?:19|20)\d{2}", tok):
                continue  # a bare 4-digit number: checked as a number below
            issues.append(f"unknown_period:{tok}")
        remaining = _PERIOD.sub(lambda m: m.group(0) if (re.fullmatch(r"(?:19|20)\d{2}", m.group(0)) and m.group(0) not in joined) else " ", t)
        for m in _NUM.finditer(remaining):
            p = parse_number(m.group(0))
            if not p:
                continue
            v, d, scale, is_pct = p
            n = abs(v) * scale
            tol = 0.5 * 10 ** (-d) * scale + 1e-9 * max(1.0, n)
            pool = (pct | plain) if is_pct else plain
            ok = any(abs(a - n) <= tol for a in pool)
            if not ok and not is_pct and scale == 1 and d == 0 and n <= 10:
                ok = bool(re.search(r"(top|first|last|bottom)\s+$", remaining[: m.start()], re.I))
            if not ok:
                issues.append(f"unsupported_number:{m.group(0).strip()}")

        # direction words must not contradict the sign of the changes in the evidence
        signs = set()

        def signs_of(o, key=""):
            if _finite(o) and key in ("change_abs", "change_pct", "variance"):
                signs.add(1 if o > 0 else -1 if o < 0 else 0)
            elif isinstance(o, dict):
                for k, v in o.items():
                    signs_of(v, str(k))
            elif isinstance(o, (list, tuple)):
                for v in o:
                    signs_of(v, key)
        for d in ev.data:
            signs_of(d)
        if signs and signs <= {1} and DOWN.search(t) and not UP.search(t):
            issues.append("direction_mismatch")
        if signs and signs <= {-1} and UP.search(t) and not DOWN.search(t):
            issues.append("direction_mismatch")

    # names: capitalised words must exist in the evidence or the workbook vocabulary.
    # A sentence-initial word is also checked (that is where an invented category usually appears),
    # but ordinary sentence starters are allowed.
    for m in _PROPER.finditer(t):
        w = m.group(0)
        start = t[: m.start()].rstrip()
        initial = not start or start[-1] in ".!?:\n"
        nw = strip_accents(w).casefold().strip("'’-")
        if nw in _COMMON or re.fullmatch(r"q[1-4]", nw) or nw in words or (initial and nw in _STARTERS):
            continue
        issues.append(f"unknown_name:{w}")
    return Check(not issues, issues)


def check_insight(ins: dict, ev: Evidence) -> Check:
    issues = []
    for field_, kind, required in (("statement", "statement", True), ("interpretation", "interpretation", False),
                                   ("next_check", "next_check", False)):
        v = ins.get(field_)
        if not v:
            if required:
                issues.append("missing_statement")
            continue
        c = check_text(str(v), ev, kind=kind)
        issues += [f"{field_}:{i}" for i in c.issues]
    return Check(not issues, issues)
