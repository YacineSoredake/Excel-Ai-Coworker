import re
import unicodedata

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_key(s) -> str:
    """Case/accent/punctuation-insensitive key used to compare labels."""
    s = strip_accents(str(s)).casefold().replace("_", " ")
    s = re.sub(r"[^\w]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def name_tokens(label) -> list[str]:
    toks = norm_key(_CAMEL.sub(" ", str(label))).split()
    # Arabic definite article: الكمية ("the quantity") -> كمية
    return [t[2:] if t.startswith("ال") and len(t) > 3 else t for t in toks]


def clean_label(v) -> str:
    s = re.sub(r"\s+", " ", str(v)).strip()
    return s.rstrip(":").strip()
