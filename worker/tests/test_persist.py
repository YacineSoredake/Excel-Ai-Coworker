"""persist.save_profile against a fake Supabase client: JSON-safe rows and consistent foreign keys."""
import json
import os

from app.engine.analyze import analyze_workbook
from app.analytics.run import compute_analytics
from app.persist import save_analytics_status, save_facts, save_profile

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


class _Q:
    def __init__(self, client, name):
        self.c, self.name = client, name

    def insert(self, rows):
        rows = rows if isinstance(rows, list) else [rows]
        json.dumps(rows, allow_nan=False)  # must be strictly JSON-serializable
        self.c.rows.setdefault(self.name, []).extend(rows)
        return self

    def delete(self):
        self.c.deleted.append(self.name)
        return self

    def update(self, row):
        json.dumps(row, allow_nan=False)
        self.c.updated.append((self.name, row))
        return self

    def eq(self, *a):
        return self

    def execute(self):
        return self


class _Store:
    def __init__(self, client, bucket):
        self.c, self.b = client, bucket

    def list(self, prefix, opts=None):
        return []

    def remove(self, paths):
        pass

    def upload(self, path, data, opts=None):
        assert len(data) > 100 and data[:4] == b"PAR1"  # a real parquet file
        self.c.uploads.append((self.b, path))


class FakeClient:
    def __init__(self):
        self.rows, self.deleted, self.uploads, self.updated = {}, [], [], []
        self.storage = type("S", (), {"from_": lambda s, b: _Store(self, b)})()

    def table(self, name):
        return _Q(self, name)


def test_save_profile_is_consistent():
    out = analyze_workbook(open(os.path.join(FIX, "01_sales_clean.xlsx"), "rb").read())
    c = FakeClient()
    save_profile(c, "user-1", "wb-1", out)
    r = c.rows
    assert {"sheets", "data_tables", "column_profiles", "findings", "workbook_profiles"} <= set(r)
    assert len(r["data_tables"]) == 3 and len(r["sheets"]) == 3
    sheet_ids = {s["id"] for s in r["sheets"]}
    table_ids = {t["id"] for t in r["data_tables"]}
    col_ids = {x["id"] for x in r["column_profiles"]}
    assert all(t["sheet_id"] in sheet_ids for t in r["data_tables"])
    assert all(x["table_id"] in table_ids for x in r["column_profiles"])
    for f in r["findings"]:
        assert f["sheet_id"] in sheet_ids | {None} and f["table_id"] in table_ids | {None}
        assert f["column_id"] in col_ids | {None}
    assert all(row["user_id"] == "user-1" and row["workbook_id"] == "wb-1" for rows in r.values() for row in rows)
    assert len(c.uploads) == 3 and all(b == "artifacts" and p.startswith("user-1/wb-1/tables/") for b, p in c.uploads)
    assert {"sheets", "findings", "workbook_profiles"} <= set(c.deleted)  # idempotent re-run
    assert r["workbook_profiles"][0]["summary"]["table_count"] == 3


def test_save_facts_is_consistent_and_ranked():
    out = analyze_workbook(open(os.path.join(FIX, "01_sales_clean.xlsx"), "rb").read())
    res = compute_analytics(out)
    c = FakeClient()
    save_profile(c, "user-1", "wb-1", out)
    save_facts(c, "user-1", "wb-1", out, res)
    save_analytics_status(c, "wb-1", res.stats)
    facts = c.rows["facts"]
    table_ids = {t["id"] for t in c.rows["data_tables"]}
    assert len(facts) == len(res.facts) > 20
    assert [f["rank"] for f in facts] == list(range(1, len(facts) + 1))
    assert len({f["key"] for f in facts}) == len(facts)
    assert all(f["table_id"] in table_ids and f["verified"] for f in facts)
    assert all(f["payload"] and f["spec"]["op"] for f in facts)
    assert "facts" in c.deleted  # re-running replaces the previous facts
    assert c.updated[-1][0] == "workbook_profiles" and c.updated[-1][1]["analytics"]["dropped_unverified"] == 0
