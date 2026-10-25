import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from supabase import create_client

from .config import Settings
from .pipeline import run_job
from .questions import handle_question

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("worker")

class Metrics:
    def __init__(self) -> None:
        self.started_at = time.time()
        self.jobs_completed = 0
        self.questions_completed = 0
        self.errors = 0
        self.lock = threading.Lock()

    def increment(self, name: str) -> None:
        with self.lock:
            setattr(self, name, getattr(self, name) + 1)

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "uptime_seconds": int(time.time() - self.started_at),
                "jobs_completed": self.jobs_completed,
                "questions_completed": self.questions_completed,
                "errors": self.errors,
            }


def poll_loop(settings: Settings, stop: threading.Event, metrics: Metrics) -> None:
    client = create_client(settings.supabase_url, settings.service_key)
    log.info("worker_started ai=%s", settings.llm.name if settings.llm else "off")
    while not stop.is_set():
        try:
            qs = client.rpc("claim_next_question", {}).execute().data or []  # people are waiting on questions: they go first
            if qs:
                handle_question(client, settings, qs[0])
                metrics.increment("questions_completed")
                continue
            rows = client.rpc("claim_next_job", {}).execute().data or []
            if not rows:
                stop.wait(settings.poll_interval)
                continue
            run_job(client, settings, rows[0])
            metrics.increment("jobs_completed")
        except Exception as e:
            metrics.increment("errors")
            log.error("poll_error type=%s", type(e).__name__)
            stop.wait(5)
    log.info("worker_stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.load()
    stop = threading.Event()
    metrics = Metrics()
    thread = threading.Thread(target=poll_loop, args=(settings, stop, metrics), daemon=True)
    thread.start()
    app.state.worker_thread = thread
    app.state.metrics = metrics
    yield
    stop.set()
    thread.join(timeout=10)


app = FastAPI(title="Excel Copilot worker", lifespan=lifespan)


@app.get("/health")
def health():
    alive = app.state.worker_thread.is_alive()
    return {"status": "ok" if alive else "degraded", "worker_alive": alive, "metrics": app.state.metrics.snapshot()}
