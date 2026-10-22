import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .ai.llm import load_llm

load_dotenv()


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    service_key: str
    max_file_bytes: int
    poll_interval: float
    max_cells: int = 2_000_000
    max_table_rows: int = 200_000
    analysis_timeout: float = 120.0
    llm: object = None
    ai_phrase_answers: bool = False

    @staticmethod
    def load() -> "Settings":
        return Settings(
            supabase_url=os.environ["SUPABASE_URL"],
            service_key=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            max_file_bytes=int(os.getenv("MAX_FILE_MB", "10")) * 1024 * 1024,
            poll_interval=float(os.getenv("POLL_INTERVAL_SECONDS", "2")),
            max_cells=int(os.getenv("MAX_CELLS", "2000000")),
            max_table_rows=int(os.getenv("MAX_TABLE_ROWS", "200000")),
            analysis_timeout=float(os.getenv("ANALYSIS_TIMEOUT_SECONDS", "120")),
            llm=load_llm(os.environ),
            ai_phrase_answers=os.getenv("AI_PHRASE_ANSWERS", "false").strip().lower() == "true",
        )
