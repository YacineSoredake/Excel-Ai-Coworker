from ..analytics.run import AnalyticsResult
from ..engine.models import EngineOutput
from .build import build_candidates
from .select import select

CHARTS_VERSION = 1


def build_charts(out: EngineOutput, result: AnalyticsResult):
    cands = build_candidates(out, result.facts)
    return select(cands), {"charts_version": CHARTS_VERSION, "chart_candidates": len(cands)}
