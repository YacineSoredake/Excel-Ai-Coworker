"""A small in-memory stand-in for Supabase: tables with select/eq/in_/order/limit/insert/update/delete, rpc, and storage."""
import copy
import uuid
from collections import defaultdict


class Res:
    def __init__(self, data):
        self.data = data


class Q:
    def __init__(self, db, name):
        self.db, self.name, self.op, self.payload, self.filters, self._order, self._limit = db, name, "select", None, [], None, None

    def select(self, cols="*"):
        return self

    def insert(self, rows):
        self.op, self.payload = "insert", rows if isinstance(rows, list) else [rows]
        return self

    def update(self, row):
        self.op, self.payload = "update", row
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, col, val):
        self.filters.append((col, lambda x, v=val: x == v))
        return self

    def in_(self, col, vals):
        self.filters.append((col, lambda x, v=set(vals): x in v))
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def _match(self, row):
        return all(f(row.get(c)) for c, f in self.filters)

    def execute(self):
        rows = self.db.t[self.name]
        if self.op == "insert":
            out = []
            for r in self.payload:
                r = copy.deepcopy(r)
                r.setdefault("id", str(uuid.uuid4()))
                rows.append(r)
                out.append(copy.deepcopy(r))
            return Res(out)
        hit = [r for r in rows if self._match(r)]
        if self.op == "update":
            for r in hit:
                r.update(copy.deepcopy(self.payload))
            self.db.log.append((self.name, copy.deepcopy(self.payload)))
            return Res(copy.deepcopy(hit))
        if self.op == "delete":
            self.db.t[self.name] = [r for r in rows if not self._match(r)]
            return Res([])
        out = copy.deepcopy(hit)
        if self._order:
            out.sort(key=lambda r: r.get(self._order[0]), reverse=self._order[1])
        return Res(out[: self._limit] if self._limit else out)


class Store:
    def __init__(self, db, bucket):
        self.db, self.b = db, bucket

    def download(self, path):
        return self.db.files[(self.b, path)]

    def upload(self, path, data, opts=None):
        self.db.files[(self.b, path)] = data

    def list(self, prefix, opts=None):
        return [{"name": p.split("/")[-1], "id": "x"} for (b, p) in self.db.files if b == self.b and p.startswith(prefix + "/")]

    def remove(self, paths):
        for p in paths:
            self.db.files.pop((self.b, p), None)


class FakeDB:
    def __init__(self):
        self.t, self.files, self.log, self.rpcs = defaultdict(list), {}, [], {}
        self.storage = type("S", (), {"from_": lambda s, b: Store(self, b)})()

    def table(self, name):
        return Q(self, name)

    def rpc(self, name, params=None):
        outer = self
        return type("R", (), {"execute": lambda s: Res(outer.rpcs[name](params or {}))})()

    def statuses(self):
        return [u["status"] for n, u in self.log if n == "workbooks" and "status" in u]
