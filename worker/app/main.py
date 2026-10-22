import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from supabase import create_client

from .config import Settings
from .pipeline import run_job
from .questions import handle_question

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("worker")


def poll_loop(settings: Settings, stop: threading.Event) -> None:
    client = create_client(settings.supabase_url, settings.service_key)
    log.info("worker_started ai=%s", settings.llm.name if settings.llm else "off")
    while not stop.is_set():
        try:
            qs = client.rpc("claim_next_question", {}).execute().data or []  # people are waiting on questions: they go first
            if qs:
                handle_question(client, settings, qs[0])
                continue
            rows = client.rpc("claim_next_job", {}).execute().data or []
            if not rows:
                stop.wait(settings.poll_interval)
                continue
            run_job(client, settings, rows[0])
        except Exception as e:
            log.error("poll_error type=%s", type(e).__name__)
            stop.wait(5)
    log.info("worker_stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.load()
    stop = threading.Event()
    thread = threading.Thread(target=poll_loop, args=(settings, stop), daemon=True)
    thread.start()
    app.state.worker_thread = thread
    yield
    stop.set()
    thread.join(timeout=10)


app = FastAPI(title="Excel Copilot worker", lifespan=lifespan)


@app.get("/health")
def health():
    alive = app.state.worker_thread.is_alive()
    return {"status": "ok" if alive else "degraded", "worker_alive": alive}
