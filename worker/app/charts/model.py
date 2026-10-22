from dataclasses import dataclass, field


@dataclass
class ChartSpec:
    key: str
    kind: str  # kpi | line | multi_line | hbar | donut | stacked_bar | target | scatter | histogram
    role: str  # kpi | trend | comparison | composition | breakdown | target | relationship | distribution
    table_index: int
    title: str  # always the analytical question
    why: str  # why this visualization exists (shown to the user)
    fact_keys: list
    encoding: dict  # {"measure":..., "dim":..., "time":...}
    data: dict  # everything needed to draw without any query
    query: dict | None  # re-runnable in the browser for filters; None = not filterable
    options: dict = field(default_factory=dict)
    usefulness: float = 0.0
    reliability: float = 1.0
    readability: float = 1.0
    score: float = 0.0
    placement: str = "explore"  # kpi | primary | secondary | explore
    position: int = 0
    caveats: list = field(default_factory=list)
