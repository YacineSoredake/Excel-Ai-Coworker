"""Orchestrates phase F (generate candidates), G (score) and H (validate) for the whole workbook."""
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..engine.context import Ctx, Limits
from ..engine.models import EngineOutput
from .facts_basic import kpi_facts, outlier_facts, ranking_facts
from .facts_relations import correlation_facts, derivation_facts, target_facts
from .facts_time import time_facts
from .model import Fact
from .plan import prepare
from .verify import VCtx, verify

ANALYTICS_VERSION = 1
MAX_FACTS = 150
KEEP_PER_GROUP = {"rank": 3, "corr": 3, "breakdown": 1, "kpi": 2, "anomaly_values": 3}


@dataclass
class AnalyticsResult:
    facts: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def compute_analytics(out: EngineOutput, timeout_seconds: float = 120.0) -> AnalyticsResult:
    t0 = time.monotonic()
    ctx = Ctx(Limits(timeout_seconds=timeout_seconds))
    tcs = prepare(out)
    cands: list[Fact] = []
    skipped = []
    derived: dict[int, set] = {}
    for tc in tcs:
        ctx.tick()
        if not (tc.measures or tc.time):
            reason = ("reference values (targets, budgets), used for comparisons only" if tc.refs
                      else "no numeric measures or dates to analyze")
            skipped.append({"table": tc.t.name, "reason": reason})
            continue
        cands += kpi_facts(tc)
        cands += outlier_facts(tc)
        cands += ranking_facts(tc)
        cands += time_facts(tc)
        dv = derivation_facts(tc)
        cands += dv
        derived[tc.t.index] = {frozenset((f.payload["target"], x)) for f in dv for x in f.payload["factors"]
                               if f.payload["match_share"] >= 0.8}
        cands += correlation_facts(tc, derived[tc.t.index])
    ctx.tick()
    cands += target_facts(tcs)

    # phase G — score: usefulness × reliability; keep only the best few of each redundancy group
    for f in cands:
        f.score = round(f.usefulness * f.reliability, 4)
    groups = defaultdict(list)
    for f in cands:
        groups[f.group].append(f)
    kept = []
    for g, fs in groups.items():
        k = next((n for p, n in KEEP_PER_GROUP.items() if g.startswith(p)), 5)
        kept += sorted(fs, key=lambda f: -f.score)[:k]

    # phase H — validate: an independent recomputation must agree
    v = VCtx({tc.t.index: tc.df for tc in tcs})
    good, dropped = [], []
    for f in kept:
        ctx.tick()
        (good if verify(f, v) else dropped).append(f)
    for f in good:
        f.verified = True
    good.sort(key=lambda f: (-f.score, f.key))
    good = good[:MAX_FACTS]
    return AnalyticsResult(facts=good, stats={
        "analytics_version": ANALYTICS_VERSION, "facts": len(good), "candidates": len(cands),
        "dropped_unverified": len(dropped), "dropped_keys": [f.key for f in dropped][:20],
        "skipped_tables": skipped, "by_kind": dict(Counter(f.kind for f in good)),
        "ms": int((time.monotonic() - t0) * 1000)})
