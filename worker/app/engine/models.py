from dataclasses import dataclass, field


@dataclass
class Finding:
    code: str
    severity: str  # info | low | medium | high
    title: str
    detail: str
    sheet: str | None = None
    table_index: int | None = None
    column_pos: int | None = None
    affected: int | None = None
    total: int | None = None
    sample_rows: list = field(default_factory=list)
    evidence: dict = field(default_factory=dict)


@dataclass
class TableResult:
    index: int
    id: str
    sheet: str
    name: str
    source: str
    cell_range: str
    header_row: int | None  # Excel 1-based
    first_data_row: int
    last_data_row: int
    col0: int  # 1-based
    col1: int
    confidence: float
    header_conf: float
    columns: list
    rows: list  # Excel row numbers kept
    total_rows: list
    blank_rows: int = 0
    repeated_header_rows: int = 0
    truncated: bool = False
    dropped_empty_columns: int = 0
    preamble: list = field(default_factory=list)


@dataclass
class EngineOutput:
    sheets: list
    tables: list
    findings: list
    relationships: list
    summary: dict
    frames: dict  # table id -> pandas DataFrame
    engine_ms: int = 0
