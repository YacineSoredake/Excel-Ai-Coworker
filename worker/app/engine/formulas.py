"""Formula metadata: formula-derived vs manual cells, and inconsistent formulas in a column."""
import re
from collections import Counter

from openpyxl.utils import column_index_from_string

_REF = re.compile(r"(?<![A-Za-z0-9_.])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![\d(A-Za-z_])")


def relativize(formula: str, row: int, col: int) -> str:
    """'=A5*2' in B5 and '=A6*2' in B6 share the pattern '=R[0]C[-1]*2'."""
    def sub(m):
        cabs, cl, rabs, rn = m.groups()
        try:
            c = column_index_from_string(cl)
        except ValueError:
            return m.group(0)
        r = int(rn)
        return (f"R{r}" if rabs else f"R[{r - row}]") + (f"C{c}" if cabs else f"C[{c - col}]")

    parts = re.split(r'("[^"]*")', formula)  # leave string literals alone
    return "".join(p if p.startswith('"') else _REF.sub(sub, p) for p in parts)


def inconsistent_formulas(formulas: dict, col: int, min_count: int = 5, majority: float = 0.8):
    """formulas: {row: text} for one column. Returns None or the rows that break the dominant pattern."""
    if len(formulas) < min_count:
        return None
    pats = {r: relativize(f, r, col) for r, f in formulas.items()}
    top, cnt = Counter(pats.values()).most_common(1)[0]
    if cnt == len(pats) or cnt / len(pats) < majority:
        return None
    example = next(formulas[r] for r, p in pats.items() if p == top)
    return {"pattern_share": round(cnt / len(pats), 3),
            "rows": sorted(r for r, p in pats.items() if p != top),
            "dominant_example": example[:120]}
