from dataclasses import dataclass, field


@dataclass
class Fact:
    kind: str  # kpi | ranking | trend | period_change | swing | anomaly_period | anomaly_values |
    #            breakdown | correlation | derivation | target
    key: str
    table_index: int
    title: str  # the question this answers (neutral)
    headline: str  # one deterministic factual sentence, never causal
    definition: str  # how the number is computed (inspectable)
    payload: dict
    spec: dict  # enough to recompute the fact (also used for verification and drill-down)
    source: dict = field(default_factory=dict)
    measure: str | None = None
    dimension: str | None = None
    time_column: str | None = None
    agg: str | None = None
    sample_rows: list = field(default_factory=list)
    caveats: list = field(default_factory=list)
    usefulness: float = 0.0
    reliability: float = 1.0
    score: float = 0.0
    group: str = ""  # redundancy group: only the best few of a group are kept
    verified: bool = False
