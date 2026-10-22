"""run_job end to end against a fake Supabase: validate -> profile -> facts, and failure isolation."""
import json
import os

import app.pipeline as pipeline
from app.config import Settings

from .test_persist import FakeClient

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


class _Q2:
    def __init__(self, c, name):
        self.c, self.name, self._op = c, name, None

    def insert(self, rows):
        rows = rows if isinstance(rows, list) else [rows]
        json.dumps(rows, allow_nan=False)  # what Postgres will receive must be strictly valid JSON
        self.c.rows.setdefault(self.name, []).extend(rows)
        return self

    def update(self, row):
        self._op = ("update", row)
        return self

    def delete(self):
        self._op = ("delete", None)
        self.c.deleted.append(self.name)
        return self

    def eq(self, *a):
        return self

    def execute(self):
        if self._op and self._op[0] == "update":
            self.c.updates.append((self.name, self._op[1]))
        return self


class _Store2:
    def __init__(self, c):
        self.c = c

    def download(self, path):
        return open(os.path.join(FIX, "01_sales_clean.xlsx"), "rb").read()

    def upload(self, *a, **k):
        pass

    def list(self, *a, **k):
        return []

    def remove(self, *a):
        pass


class Client(FakeClient):
    def __init__(self):
        super().__init__()
        self.updates = []
        self.storage = type("S", (), {"from_": lambda s, b: _Store2(self)})()

    def table(self, name):
        return _Q2(self, name)

    def statuses(self):
        return [u["status"] for n, u in self.updates if n == "workbooks" and "status" in u]


JOB = {"job_id": "j1", "wb_id": "w1", "owner_id": "u1", "path": "u1/w1/original.xlsx", "name": "x.xlsx", "attempts": 1}
SETTINGS = Settings(supabase_url="x", service_key="k", max_file_bytes=10 * 1024 * 1024, poll_interval=1)


def test_job_runs_all_three_phases():
    c = Client()
    pipeline.run_job(c, SETTINGS, dict(JOB))
    assert c.statuses() == ["validating", "analyzing", "profiled"]
    assert len(c.rows["data_tables"]) == 3 and len(c.rows["facts"]) > 20
    assert any(n == "analysis_jobs" and u["status"] == "done" for n, u in c.updates)
    analytics = [u["analytics"] for n, u in c.updates if n == "workbook_profiles" and "analytics" in u][-1]
    assert analytics["dropped_unverified"] == 0 and analytics["facts"] == len(c.rows["facts"])
    assert analytics["charts"] == len(c.rows["charts"]) > 10
    placements = [r["placement"] for r in c.rows["charts"]]
    assert placements.count("kpi") == 4 and placements.count("primary") == 1


def test_analytics_failure_never_breaks_the_profile(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret detail that must not be logged")
    monkeypatch.setattr(pipeline, "compute_analytics", boom)
    c = Client()
    pipeline.run_job(c, SETTINGS, dict(JOB))
    assert c.statuses()[-1] == "profiled"  # the profile is still usable
    assert len(c.rows["data_tables"]) == 3 and "facts" not in c.rows
    assert "facts" in c.deleted  # no partial facts left behind
    assert [u["analytics"] for n, u in c.updates if n == "workbook_profiles" and "analytics" in u][-1] == {"error": "internal_error"}
    assert any(n == "analysis_jobs" and u["status"] == "done" for n, u in c.updates)


def test_chart_failure_keeps_the_facts(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("detail that must not be logged")
    monkeypatch.setattr(pipeline, "build_charts", boom)
    c = Client()
    pipeline.run_job(c, SETTINGS, dict(JOB))
    assert c.statuses()[-1] == "profiled" and len(c.rows["facts"]) > 20
    assert "charts" not in c.rows and "charts" in c.deleted
    assert [u["analytics"] for n, u in c.updates if n == "workbook_profiles" and "analytics" in u][-1]["charts_error"] == "internal_error"
