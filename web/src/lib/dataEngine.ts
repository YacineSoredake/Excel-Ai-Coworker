/**
 * Browser-side re-computation for filters and drill-down (report §14 phase J: "filters trigger targeted recomputation").
 *
 * Pure functions over the cleaned table (Parquet). They mirror the Python analytics rules exactly:
 * same period buckets, same "complete period" rule, same ranking order, same sampling.
 * `web/tests/dataEngine.test.ts` checks them against values computed by the Python worker.
 */
import { parquetReadObjects } from "hyparquet";

export type Row = Record<string, unknown>;
export type Grain = "D" | "W" | "M" | "Q" | "Y";

export interface Filters {
  timeCol?: string | null;
  from?: string | null; // YYYY-MM-DD, inclusive
  to?: string | null;
  dims: Record<string, string[]>;
}
export const NO_FILTERS: Filters = { dims: {} };

export function filtersActive(f: Filters): boolean {
  return !!(f.from || f.to || Object.values(f.dims).some((v) => v.length));
}

export async function readTable(buf: ArrayBuffer): Promise<Row[]> {
  const rows = (await parquetReadObjects({ file: buf })) as Row[];
  for (const r of rows) for (const k in r) if (typeof r[k] === "bigint") r[k] = Number(r[k]);
  return rows;
}

/* ------------------------------------------------------------------ helpers */

const DAY = 86_400_000;
const pad = (n: number) => String(n).padStart(2, "0");
const iso = (ms: number) => new Date(ms).toISOString().slice(0, 10);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const label = (v: unknown): string | null => {
  if (v == null) return null;
  const s = String(v).trim();
  return s === "" ? null : s;
};
const dayOf = (d: unknown): number | null => {
  if (!(d instanceof Date) || Number.isNaN(d.getTime())) return null;
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
};

interface Per { key: string; start: number; end: number }

export function periodOf(ms: number, g: Grain): Per {
  const d = new Date(ms);
  const y = d.getUTCFullYear(), m = d.getUTCMonth();
  switch (g) {
    case "D": return { key: iso(ms), start: ms, end: ms };
    case "W": {
      const start = ms - ((d.getUTCDay() + 6) % 7) * DAY; // weeks run Monday to Sunday
      return { key: `${iso(start)}/${iso(start + 6 * DAY)}`, start, end: start + 6 * DAY };
    }
    case "M": return { key: `${y}-${pad(m + 1)}`, start: Date.UTC(y, m, 1), end: Date.UTC(y, m + 1, 0) };
    case "Q": {
      const q = Math.floor(m / 3);
      return { key: `${y}Q${q + 1}`, start: Date.UTC(y, q * 3, 1), end: Date.UTC(y, q * 3 + 3, 0) };
    }
    case "Y": return { key: `${y}`, start: Date.UTC(y, 0, 1), end: Date.UTC(y + 1, 0, 0) };
  }
}

/* ------------------------------------------------------------------ filters */

export function applyFilters(rows: Row[], f: Filters): Row[] {
  const lo = f.from ? Date.parse(`${f.from}T00:00:00Z`) : -Infinity;
  const hi = f.to ? Date.parse(`${f.to}T23:59:59.999Z`) : Infinity;
  const useTime = !!f.timeCol && (f.from || f.to);
  const dimSets = Object.entries(f.dims).filter(([, v]) => v.length).map(([c, v]) => [c, new Set(v)] as const);
  return rows.filter((r) => {
    if (useTime) {
      const d = r[f.timeCol as string];
      if (!(d instanceof Date)) return false;
      const t = d.getTime();
      if (t < lo || t > hi) return false;
    }
    for (const [c, set] of dimSets) {
      const l = label(r[c]);
      if (l == null || !set.has(l)) return false;
    }
    return true;
  });
}

/** What the data covers, used to decide whether the first/last period is complete. */
export interface Ctx { lo: number | null; hi: number | null }

export function coverage(all: Row[], f: Filters, timeCol: string | null | undefined): Ctx {
  if (!timeCol) return { lo: null, hi: null };
  let lo = Infinity, hi = -Infinity;
  for (const r of all) {
    const d = dayOf(r[timeCol]);
    if (d != null) { if (d < lo) lo = d; if (d > hi) hi = d; }
  }
  if (lo === Infinity) return { lo: null, hi: null };
  if (f.from) lo = Math.max(lo, Date.parse(`${f.from}T00:00:00Z`));
  if (f.to) hi = Math.min(hi, Date.parse(`${f.to}T00:00:00Z`));
  return { lo, hi };
}

/* ------------------------------------------------------------------ operations */

export interface PeriodItem { period: string; value: number | null; rows: number; complete: boolean; empty: boolean }

export function series(rows: Row[], q: { time: string; grain: Grain; measure: string | null; agg: string }, ctx: Ctx): PeriodItem[] {
  const acc = new Map<string, { rows: number; sum: number; n: number }>();
  let lo = Infinity, hi = -Infinity;
  for (const r of rows) {
    const d = dayOf(r[q.time]);
    if (d == null) continue;
    if (d < lo) lo = d;
    if (d > hi) hi = d;
    const k = periodOf(d, q.grain).key;
    const a = acc.get(k) ?? { rows: 0, sum: 0, n: 0 };
    a.rows++;
    const v = q.measure ? r[q.measure] : null;
    if (isNum(v)) { a.sum += v; a.n++; }
    acc.set(k, a);
  }
  if (lo === Infinity) return [];
  const first = periodOf(lo, q.grain), last = periodOf(hi, q.grain);
  const cLo = ctx.lo ?? lo, cHi = ctx.hi ?? hi;
  const out: PeriodItem[] = [];
  for (let p = first; p.start <= last.start; p = periodOf(p.end + DAY, q.grain)) {
    const a = acc.get(p.key);
    const n = a?.rows ?? 0;
    let value: number | null;
    if (q.agg === "count") value = n;
    else if (q.agg === "sum") value = n === 0 ? 0 : a!.n === 0 ? null : a!.sum;
    else value = !a || a.n === 0 ? null : a.sum / a.n;
    const length = (p.end - p.start) / DAY + 1;
    let complete = true;
    if (p.key === first.key && (cLo - p.start) / DAY > 0.2 * length) complete = false;
    if (p.key === last.key && (p.end - cHi) / DAY > 0.2 * length) complete = false;
    out.push({ period: p.key, value, rows: n, complete, empty: n === 0 });
  }
  return out;
}

export function seriesData(items: PeriodItem[]) {
  return { x: items.map((i) => i.period), y: items.map((i) => i.value), rows: items.map((i) => i.rows), complete: items.map((i) => i.complete) };
}

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b), m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

export function aggregate(rows: Row[], q: { agg: string; measure: string | null }) {
  if (q.measure == null) return { value: rows.length, count: rows.length, median: null as number | null };
  const xs = rows.map((r) => r[q.measure as string]).filter(isNum);
  if (!xs.length) return { value: null, count: 0, median: null as number | null };
  const sum = xs.reduce((a, b) => a + b, 0);
  return { value: q.agg === "sum" ? sum : sum / xs.length, count: xs.length, median: median(xs) };
}

const MIN_ROWS = 5;
/** Change between the last two complete, adjacent periods (needs enough rows behind each). */
export function delta(items: PeriodItem[]) {
  const done = items.filter((i) => i.complete && i.value != null);
  if (done.length < 2) return null;
  const a = done[done.length - 2], b = done[done.length - 1];
  const names = items.map((i) => i.period);
  if (names.indexOf(b.period) - names.indexOf(a.period) !== 1 || Math.min(a.rows, b.rows) < MIN_ROWS) return null;
  const abs = (b.value as number) - (a.value as number);
  return { pct: a.value ? abs / Math.abs(a.value as number) : null, abs, latest: b.period, previous: a.period };
}

export interface GroupItem { label: string; value: number; share: number | null; rows: number | null; muted?: boolean }

export function group(rows: Row[], q: { dim: string; measure: string | null; agg: string; limit?: number; min_group?: number }) {
  const acc = new Map<string, { sum: number; n: number }>();
  for (const r of rows) {
    const l = label(r[q.dim]);
    if (l == null) continue;
    let v = 1;
    if (q.measure) {
      const x = r[q.measure];
      if (!isNum(x)) continue;
      v = x;
    }
    const a = acc.get(l) ?? { sum: 0, n: 0 };
    a.sum += v;
    a.n++;
    acc.set(l, a);
  }
  const additive = q.agg !== "mean";
  const all: { label: string; value: number; rows: number }[] = [];
  for (const [l, a] of acc) {
    if (q.agg === "mean") {
      if (a.n < (q.min_group ?? 0)) continue;
      all.push({ label: l, value: a.sum / a.n, rows: a.n });
    } else all.push({ label: l, value: a.sum, rows: a.n });
  }
  all.sort((a, b) => (b.value !== a.value ? b.value - a.value : a.label < b.label ? -1 : a.label > b.label ? 1 : 0));
  const total = all.reduce((s, g) => s + g.value, 0);
  const sharesOk = additive && total > 0 && all.every((g) => g.value >= 0);
  const limit = q.limit ?? 10;
  const groups: GroupItem[] = all.slice(0, limit).map((g) => ({ ...g, share: sharesOk ? g.value / total : null }));
  const rest = all.slice(limit);
  if (rest.length && additive) {
    const v = rest.reduce((s, g) => s + g.value, 0);
    groups.push({ label: `Other (${rest.length})`, value: v, share: sharesOk ? v / total : null, rows: null, muted: true });
  }
  return { groups, n_groups: all.length, total: additive ? total : null };
}

export function breakdown(rows: Row[], q: { time: string; grain: Grain; measure: string; dim: string; top?: number }, ctx: Ctx) {
  const base = series(rows, { time: q.time, grain: q.grain, measure: q.measure, agg: "sum" }, ctx);
  const periods = base.filter((i) => i.complete && i.value != null).map((i) => i.period);
  const want = new Set(periods);
  const cell = new Map<string, Map<string, number>>();
  for (const r of rows) {
    const d = dayOf(r[q.time]), l = label(r[q.dim]), v = r[q.measure];
    if (d == null || l == null || !isNum(v)) continue;
    const p = periodOf(d, q.grain).key;
    if (!want.has(p)) continue;
    const m = cell.get(l) ?? new Map<string, number>();
    m.set(p, (m.get(p) ?? 0) + v);
    cell.set(l, m);
  }
  const totals = [...cell].map(([l, m]) => ({ l, t: [...m.values()].reduce((a, b) => a + b, 0) }));
  totals.sort((a, b) => (b.t !== a.t ? b.t - a.t : a.l < b.l ? -1 : 1));
  const top = totals.slice(0, q.top ?? 5), rest = totals.slice(q.top ?? 5);
  const series_ = top.map(({ l }) => ({ label: l, values: periods.map((p) => cell.get(l)!.get(p) ?? 0) }));
  if (rest.length) series_.push({ label: "Other", values: periods.map((p) => rest.reduce((s, { l }) => s + (cell.get(l)!.get(p) ?? 0), 0)) });
  return { x: periods, series: series_ };
}

export function scatter(rows: Row[], q: { x: string; y: string; limit: number }) {
  const d = rows.filter((r) => isNum(r[q.x]) && isNum(r[q.y]));
  const n = d.length, k = Math.min(n, q.limit);
  const step = k > 1 ? (n - 1) / (k - 1) : 0;
  const points: [number, number, number][] = [];
  for (let i = 0; i < k; i++) {
    const idx = k > 1 && i === k - 1 ? n - 1 : Math.floor(i * step);
    const r = d[idx];
    points.push([r[q.x] as number, r[q.y] as number, Number(r.row_number)]);
  }
  return { points, n, sampled: k < n };
}

export function histogram(rows: Row[], q: { measure: string; bins: number }) {
  const xs = rows.map((r) => r[q.measure]).filter(isNum);
  const distinct = new Set(xs).size;
  const nb = Math.min(q.bins, distinct);
  if (nb < 2) return { edges: [] as number[], counts: [] as number[] };
  const lo = Math.min(...xs), hi = Math.max(...xs);
  const edges = Array.from({ length: nb + 1 }, (_, i) => lo + (i * (hi - lo)) / nb);
  edges[nb] = hi;
  const counts = new Array(nb).fill(0);
  for (const v of xs) {
    let b = nb - 1;
    while (b > 0 && v < edges[b]) b--;
    counts[b]++;
  }
  return { edges, counts };
}

/* ------------------------------------------------------------------ chart specs */

export interface ChartQuery {
  op: "agg" | "series" | "group" | "breakdown" | "scatter" | "histogram";
  [k: string]: unknown;
}

/** Re-computes the `data` of a chart spec from (filtered) rows, in the same shape the worker produced. */
export function runChart(kind: string, staticData: Record<string, unknown>, q: ChartQuery, rows: Row[], ctx: Ctx): Record<string, unknown> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const a = q as any;
  switch (q.op) {
    case "agg": {
      const r = aggregate(rows, a);
      let d = null;
      if (a.delta) d = delta(series(rows, { time: a.delta.time, grain: a.delta.grain, measure: a.measure, agg: a.agg }, ctx));
      return { ...staticData, value: r.value, median: r.median, delta: d };
    }
    case "series": return seriesData(series(rows, a, ctx));
    case "group": return group(rows, a);
    case "breakdown": return breakdown(rows, a, ctx);
    case "scatter": return { ...staticData, ...scatter(rows, a) };
    case "histogram": return histogram(rows, a);
  }
}

/* ------------------------------------------------------------------ drill-down */

export type Selection =
  | { type: "group"; label: string }
  | { type: "period"; period: string }
  | { type: "breakdown"; label: string; period: string }
  | { type: "row"; row: number }
  | { type: "bin"; lo: number; hi: number; last: boolean }
  | { type: "all" };

/** The rows behind a clicked bar, point, or cell. */
export function matchRows(rows: Row[], q: ChartQuery, sel: Selection): Row[] {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const a = q as any;
  const inPeriod = (r: Row, g: Grain, key: string) => {
    const d = dayOf(r[a.time]);
    return d != null && periodOf(d, g).key === key;
  };
  switch (sel.type) {
    case "all": return rows;
    case "group": return rows.filter((r) => label(r[a.dim]) === sel.label && (!a.measure || isNum(r[a.measure])));
    case "period": return rows.filter((r) => inPeriod(r, a.grain ?? a.delta?.grain, sel.period));
    case "breakdown": return rows.filter((r) => label(r[a.dim]) === sel.label && inPeriod(r, a.grain, sel.period));
    case "row": return rows.filter((r) => Number(r.row_number) === sel.row);
    case "bin": return rows.filter((r) => {
      const v = r[a.measure];
      return isNum(v) && v >= sel.lo && (sel.last ? v <= sel.hi : v < sel.hi);
    });
  }
}

export function distinctValues(rows: Row[], col: string, limit = 40): { value: string; count: number }[] {
  const m = new Map<string, number>();
  for (const r of rows) { const l = label(r[col]); if (l) m.set(l, (m.get(l) ?? 0) + 1); }
  return [...m].map(([value, count]) => ({ value, count })).sort((a, b) => b.count - a.count || (a.value < b.value ? -1 : 1)).slice(0, limit);
}

/** The first and last day (YYYY-MM-DD) of a period key such as 2026-05, 2026Q2, or 2026-06-29/2026-07-05. */
export function periodRange(key: string, g: Grain): { from: string; to: string } | null {
  let m: RegExpMatchArray | null;
  switch (g) {
    case "D": return /^\d{4}-\d{2}-\d{2}$/.test(key) ? { from: key, to: key } : null;
    case "W": { const [a, b] = key.split("/"); return a && b ? { from: a, to: b } : null; }
    case "M":
      m = key.match(/^(\d{4})-(\d{2})$/);
      return m ? { from: `${m[1]}-${m[2]}-01`, to: iso(Date.UTC(+m[1], +m[2], 0)) } : null;
    case "Q":
      m = key.match(/^(\d{4})Q([1-4])$/);
      return m ? { from: iso(Date.UTC(+m[1], (+m[2] - 1) * 3, 1)), to: iso(Date.UTC(+m[1], +m[2] * 3, 0)) } : null;
    case "Y": return /^\d{4}$/.test(key) ? { from: `${key}-01-01`, to: `${key}-12-31` } : null;
  }
}
