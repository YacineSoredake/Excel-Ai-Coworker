import time
from dataclasses import dataclass, field

from ..validate import Rejected


@dataclass
class Limits:
    max_cells: int = 2_000_000
    max_table_rows: int = 200_000
    timeout_seconds: float = 120.0


class Ctx:
    """Cooperative time limit (report §15: limit analysis duration)."""

    def __init__(self, limits: Limits):
        self.limits = limits
        self.deadline = time.monotonic() + limits.timeout_seconds

    def tick(self) -> None:
        if time.monotonic() > self.deadline:
            raise Rejected("timeout", "The analysis took too long. Try a smaller workbook or fewer sheets.")
