"""Phase G for charts: choose a small, varied first screen (report §5: 'prefer a small number of high-value visualizations')."""
from .model import ChartSpec

MAX_KPI, MAX_SECONDARY, MAX_EXPLORE = 4, 4, 30


def _adjust(c: ChartSpec, picked: list) -> float:
    """Redundancy penalties: same chart type, same question (measure + dimension + purpose), same dimension."""
    f = 1.0
    f *= 0.9 ** sum(1 for p in picked if p.kind == c.kind)
    same = lambda p: (p.encoding.get("measure"), p.encoding.get("dim"), p.role) == \
        (c.encoding.get("measure"), c.encoding.get("dim"), c.role)
    if any(same(p) for p in picked):
        f *= 0.75
    if c.encoding.get("dim") and any(p.encoding.get("dim") == c.encoding.get("dim") for p in picked):
        f *= 0.85  # prefer a different angle over the same category again
    if sum(1 for p in picked if p.encoding.get("measure") == c.encoding.get("measure")) >= 4:
        f *= 0.85  # the main measure may fill most of the screen, but not all of it
    if any(set(p.fact_keys[:1]) & set(c.fact_keys[:1]) for p in picked):
        f = 0.0  # an alternative view of a fact that is already shown
    return c.score * f


def select(cands: list[ChartSpec]) -> list[ChartSpec]:
    out: list[ChartSpec] = []
    for ti in sorted({c.table_index for c in cands}):
        cs = [c for c in cands if c.table_index == ti and c.score > 0]
        kpis = sorted((c for c in cs if c.kind == "kpi"), key=lambda c: (-c.score, c.key))
        rest = sorted((c for c in cs if c.kind != "kpi"), key=lambda c: (-c.score, c.key))

        used, chosen = set(), []
        for c in kpis:
            if len(chosen) == MAX_KPI:
                break
            m = (c.encoding.get("measure"), c.encoding.get("variant"))
            if m[1] is None and (m[0], None) in used:
                continue  # one card per measure (a total OR an average, not both)
            used.add(m)
            chosen.append(c)
        for i, c in enumerate(chosen):
            c.placement, c.position = "kpi", i
        out += chosen

        lines = [c for c in rest if c.kind == "line"]
        primary = lines[0] if lines else (rest[0] if rest else None)
        picked = []
        if primary:
            primary.placement, primary.position = "primary", 0
            picked.append(primary)
            out.append(primary)
        pool = [c for c in rest if c is not primary]
        sec = 0
        while pool and sec < MAX_SECONDARY:
            best = max(pool, key=lambda c: (_adjust(c, picked), c.key))
            if _adjust(best, picked) <= 0:
                break
            best.placement, best.position = "secondary", sec
            picked.append(best)
            out.append(best)
            pool.remove(best)
            sec += 1
        seen = {k for p in picked for k in p.fact_keys[:1]}
        pos = 0
        for c in pool:
            if pos >= MAX_EXPLORE:
                break
            if set(c.fact_keys[:1]) & seen:
                continue  # alternates of facts already shown are not repeated
            seen |= set(c.fact_keys[:1])
            c.placement, c.position = "explore", pos
            out.append(c)
            pos += 1
    return out
