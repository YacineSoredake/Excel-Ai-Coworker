/**
 * Parity: the browser engine must reproduce what the Python worker / pandas computed
 * (see worker/scripts/export_golden.py), for every filter combination and every period grain.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import * as E from "../src/lib/dataEngine";

const G = JSON.parse(readFileSync(join(__dirname, "golden/golden.json"), "utf8"));

async function load(file: string) {
  const b = readFileSync(join(__dirname, "golden", file));
  return E.readTable(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer);
}

function same(actual: unknown, expected: unknown, path = "$"): void {
  if (expected === null || expected === undefined) return void expect(actual ?? null, path).toBeNull();
  if (typeof expected === "number") {
    expect(typeof actual, path).toBe("number");
    const a = actual as number;
    expect(Math.abs(a - expected), `${path}: ${a} vs ${expected}`).toBeLessThanOrEqual(1e-9 + 1e-9 * Math.abs(expected));
    return;
  }
  if (Array.isArray(expected)) {
    expect(Array.isArray(actual), path).toBe(true);
    expect((actual as unknown[]).length, `${path} length`).toBe(expected.length);
    expected.forEach((e, i) => same((actual as unknown[])[i], e, `${path}[${i}]`));
    return;
  }
  if (typeof expected === "object") {
    for (const [k, v] of Object.entries(expected)) same((actual as Record<string, unknown>)?.[k], v, `${path}.${k}`);
    return;
  }
  expect(actual, path).toBe(expected);
}

function run(rows: E.Row[], all: E.Row[], filters: E.Filters, timeCol: string, q: any) {
  const ctx = E.coverage(all, filters, timeCol);
  switch (q.op) {
    case "agg": {
      const r: any = E.aggregate(rows, q);
      if (q.delta) r.delta = E.delta(E.series(rows, { ...q.delta, measure: q.measure, agg: q.agg }, ctx));
      return r;
    }
    case "series": return E.series(rows, q, ctx);
    case "group": return E.group(rows, q);
    case "breakdown": return E.breakdown(rows, q, ctx);
    case "histogram": return E.histogram(rows, q);
  }
}

describe.each(["sales", "messy", "multiyear"])("parity with the Python worker: %s", (name) => {
  const g = G[name];
  for (const c of g.cases) {
    it(`${c.name} (${c.rows} rows after filtering)`, async () => {
      const all = await load(g.parquet);
      const f: E.Filters = { timeCol: g.timeCol, from: c.filters.from ?? null, to: c.filters.to ?? null, dims: c.filters.dims ?? {} };
      const rows = E.applyFilters(all, f);
      expect(rows.length).toBe(c.rows);
      for (const r of c.results) same(run(rows, all, f, g.timeCol, r.query), r.expect, JSON.stringify(r.query));
    });
  }
});

describe("drill-down returns exactly the rows behind a bar or a month", () => {
  it("group, period and breakdown selections", async () => {
    const all = await load(G.sales.parquet);
    const rn = (rows: E.Row[]) => rows.map((r) => Number(r.row_number)).sort((a, b) => a - b);
    const d = G.sales.drill;
    expect(rn(E.matchRows(all, { op: "group", dim: "category", measure: "total_dzd" }, { type: "group", label: "Electronics" })))
      .toEqual(d["group_category_Electronics"]);
    expect(rn(E.matchRows(all, { op: "series", time: "date", grain: "M", measure: "total_dzd" }, { type: "period", period: "2026-05" })))
      .toEqual(d["period_2026-05"]);
    expect(rn(E.matchRows(all, { op: "breakdown", time: "date", grain: "M", dim: "channel", measure: "total_dzd" },
      { type: "breakdown", label: "Online", period: "2026-05" }))).toEqual(d["breakdown_Online_2026-05"]);
  });
});

describe("scatter sampling matches numpy.linspace", () => {
  it("same points, same order, links back to Excel rows", async () => {
    const rows = await load(G.scatter.parquet);
    const r = E.scatter(rows, { x: "x", y: "y", limit: 500 });
    expect(r.n).toBe(G.scatter.n);
    expect(r.sampled).toBe(true);
    same(r.points, G.scatter.points);
  });
});

describe("filters and periods", () => {
  it("reads typed columns from Parquet", async () => {
    const rows = await load(G.sales.parquet);
    expect(rows[0].date).toBeInstanceOf(Date);
    expect(typeof rows[0].row_number).toBe("number"); // not a BigInt
    expect(E.filtersActive({ dims: {} })).toBe(false);
    expect(E.filtersActive({ dims: { channel: [] } })).toBe(false);
    expect(E.filtersActive({ dims: { channel: ["Online"] } })).toBe(true);
    expect(E.filtersActive({ dims: {}, from: "2026-01-01" })).toBe(true);
  });
  it("period keys follow the Python labels", () => {
    const d = Date.UTC(2026, 6, 1); // Wed 1 July 2026
    expect(E.periodOf(d, "M").key).toBe("2026-07");
    expect(E.periodOf(d, "W").key).toBe("2026-06-29/2026-07-05");
    expect(E.periodOf(d, "Q").key).toBe("2026Q3");
    expect(E.periodOf(d, "Y").key).toBe("2026");
    expect(E.periodOf(d, "D").key).toBe("2026-07-01");
  });
  it("a date filter that cuts a month makes that month incomplete", async () => {
    const all = await load(G.sales.parquet);
    const f: E.Filters = { timeCol: "date", from: "2026-03-10", to: "2026-06-20", dims: {} };
    const items = E.series(E.applyFilters(all, f), { time: "date", grain: "M", measure: "total_dzd", agg: "sum" }, E.coverage(all, f, "date"));
    expect(items.map((i) => [i.period, i.complete])).toEqual([["2026-03", false], ["2026-04", true], ["2026-05", true], ["2026-06", false]]);
  });
  it("filtering by category alone does not shrink what the file covers", async () => {
    const all = await load(G.sales.parquet);
    const f: E.Filters = { timeCol: "date", dims: { category: ["Grocery"] } };
    const items = E.series(E.applyFilters(all, f), { time: "date", grain: "M", measure: "total_dzd", agg: "sum" }, E.coverage(all, f, "date"));
    expect(items.every((i) => i.complete)).toBe(true);
  });
});

describe("periodRange is the inverse of periodOf", () => {
  it("round-trips every grain", () => {
    for (const g of ["D", "W", "M", "Q", "Y"] as const) {
      const per = E.periodOf(Date.UTC(2026, 4, 14), g);
      const r = E.periodRange(per.key, g)!;
      expect(Date.parse(r.from + "T00:00:00Z")).toBe(per.start);
      expect(Date.parse(r.to + "T00:00:00Z")).toBe(per.end);
    }
    expect(E.periodRange("nonsense", "M")).toBeNull();
  });
});
