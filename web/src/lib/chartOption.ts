/**
 * Chart spec -> ECharts option. Pure functions (no DOM, no echarts import) so they can be unit-tested.
 * Visual rules (report §5): bars for comparisons, lines for ordered time, no 3D, no decoration without meaning.
 */
/* eslint-disable @typescript-eslint/no-explicit-any */

export const COLORS = { accent: "#5E6AD2", accentSoft: "#C9CDF0", ink: "#18181B", text: "#52525B", muted: "#A1A1AA", grid: "#E4E4E7" };
export const PALETTE = ["#5E6AD2", "#8B93E0", "#B9BEEC", "#71717A", "#A1A1AA", "#D4D4D8"];

/** Spreadsheet text ends up inside tooltip HTML, so it is always escaped. */
export function esc(s: unknown): string {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);
}

export function fmtNum(v: number | null | undefined, cur?: string | null, compact = false): string {
  if (v == null || !Number.isFinite(v)) return "–";
  const a = Math.abs(v);
  let s: string;
  if (compact && a >= 1e9) s = `${+(v / 1e9).toFixed(1)}B`;
  else if (compact && a >= 1e6) s = `${+(v / 1e6).toFixed(1)}M`;
  else if (compact && a >= 1e4) s = `${+(v / 1e3).toFixed(0)}K`;
  else s = a >= 1000 || Number.isInteger(v) ? v.toLocaleString("en-US", { maximumFractionDigits: 0 }) : v.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return cur && !compact ? `${s} ${cur}` : s;
}
const pct = (x: number | null | undefined) => (x == null ? "" : `${Math.round(x * 100)}%`);

/** '2026-06-29/2026-07-05' -> '06-29'; other keys unchanged. */
export function shortPeriod(p: string): string {
  return p.includes("/") ? p.split("/")[0].slice(5) : p;
}

const base = () => ({
  aria: { enabled: true },
  animationDuration: 300,
  textStyle: { fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif", color: COLORS.text },
  grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
  tooltip: { confine: true, backgroundColor: "#fff", borderColor: COLORS.grid, textStyle: { color: COLORS.ink, fontSize: 12 } },
});
const valueAxis = (cur?: string | null) => ({
  type: "value", axisLabel: { formatter: (v: number) => fmtNum(v, null, true), color: COLORS.text },
  splitLine: { lineStyle: { color: COLORS.grid } },
});
const catAxis = (data: string[], extra: any = {}) => ({
  type: "category", data, axisLine: { lineStyle: { color: COLORS.grid } }, axisTick: { show: false },
  axisLabel: { color: COLORS.text, formatter: shortPeriod, hideOverlap: true }, ...extra,
});

export function lineOption(d: any, o: any) {
  const n = d.x.length, cur = o.currency;
  const done: boolean[] = d.complete;
  const solid = d.y.map((v: number | null, i: number) => (done[i] ? v : null));
  const partial = d.y.map((v: number | null, i: number) =>
    !done[i] || (i + 1 < n && !done[i + 1]) || (i > 0 && !done[i - 1]) ? v : null);
  const marks = (o.annotations ?? []).map((a: any) => {
    const i = d.x.indexOf(a.period);
    return i < 0 ? null : { coord: [d.x[i], d.y[i]], value: a.label, label: { formatter: a.label, position: "top", color: COLORS.ink, fontSize: 11 } };
  }).filter(Boolean);
  const series: any[] = [{
    name: "Complete", type: "line", data: solid, symbol: "circle", symbolSize: 5, connectNulls: false,
    lineStyle: { width: 2, color: COLORS.accent }, itemStyle: { color: COLORS.accent },
    areaStyle: { color: COLORS.accent, opacity: 0.08 },
    markPoint: marks.length ? { symbol: "circle", symbolSize: 9, itemStyle: { color: COLORS.ink }, data: marks } : undefined,
  }];
  if (done.some((x) => !x)) {
    series.push({
      name: "Incomplete period", type: "line", data: partial, symbol: "circle", symbolSize: 5,
      lineStyle: { width: 2, type: "dashed", color: COLORS.muted }, itemStyle: { color: "#fff", borderColor: COLORS.muted, borderWidth: 1.5 },
    });
  }
  return {
    ...base(),
    tooltip: {
      ...base().tooltip, trigger: "axis",
      formatter: (ps: any) => {
        const i = ps[0].dataIndex;
        return `${esc(d.x[i])}<br/><b>${esc(fmtNum(d.y[i], cur))}</b>${d.rows ? ` · ${d.rows[i]} rows` : ""}` +
          (done[i] ? "" : "<br/><i>incomplete period, not compared</i>");
      },
    },
    xAxis: catAxis(d.x, { boundaryGap: false }), yAxis: valueAxis(cur), series,
  };
}

export function hbarOption(d: any, o: any) {
  const g: any[] = d.groups, cur = o.currency;
  return {
    ...base(), grid: { left: 8, right: 84, top: 8, bottom: 8, containLabel: true },
    tooltip: {
      ...base().tooltip, trigger: "item",
      formatter: (p: any) => {
        const x = g[p.dataIndex];
        return `${esc(x.label)}<br/><b>${esc(fmtNum(x.value, cur))}</b>${x.share != null ? ` · ${pct(x.share)}` : ""}${x.rows != null ? ` · ${x.rows} rows` : ""}`;
      },
    },
    xAxis: { ...valueAxis(cur), splitLine: { show: false }, axisLabel: { show: false } },
    yAxis: { type: "category", inverse: true, data: g.map((x) => x.label), axisTick: { show: false }, axisLine: { show: false },
             axisLabel: { color: COLORS.ink, width: 130, overflow: "truncate" } },
    series: [{
      type: "bar", barMaxWidth: 20,
      data: g.map((x) => ({ value: x.value, itemStyle: { color: x.muted ? COLORS.muted : COLORS.accent, borderRadius: [0, 3, 3, 0] } })),
      label: { show: true, position: "right", color: COLORS.text, fontSize: 11,
               formatter: (p: any) => `${fmtNum(p.value, null, true)}${g[p.dataIndex].share != null ? `  ${pct(g[p.dataIndex].share)}` : ""}` },
    }],
  };
}

export function donutOption(d: any, o: any) {
  const g: any[] = d.groups, cur = o.currency;
  return {
    ...base(), tooltip: { ...base().tooltip, trigger: "item",
      formatter: (p: any) => `${esc(p.name)}<br/><b>${esc(fmtNum(p.value, cur))}</b> · ${pct(g[p.dataIndex].share)}` },
    legend: { bottom: 0, textStyle: { color: COLORS.text } },
    series: [{
      type: "pie", radius: ["52%", "76%"], center: ["50%", "46%"], avoidLabelOverlap: true,
      label: { formatter: (p: any) => pct(g[p.dataIndex].share), color: COLORS.ink },
      data: g.map((x, i) => ({ name: x.label, value: x.value, itemStyle: { color: x.muted ? COLORS.muted : PALETTE[i % PALETTE.length] } })),
    }],
  };
}

export function stackedOption(d: any, o: any, lines = false) {
  const cur = o.currency;
  return {
    ...base(), legend: { top: 0, textStyle: { color: COLORS.text } }, grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
    tooltip: { ...base().tooltip, trigger: "axis",
      formatter: (ps: any) => `${esc(ps[0].axisValue)}<br/>` + ps.map((p: any) => `${p.marker}${esc(p.seriesName)}: <b>${esc(fmtNum(p.value, cur))}</b>`).join("<br/>") },
    xAxis: catAxis(d.x, lines ? { boundaryGap: false } : {}), yAxis: valueAxis(cur),
    series: d.series.map((s: any, i: number) => {
      const color = s.label === "Other" ? "#D4D4D8" : PALETTE[i % PALETTE.length];
      return lines
        ? { name: s.label, type: "line", data: s.values, symbol: "none", lineStyle: { width: 2, color }, itemStyle: { color } }
        : { name: s.label, type: "bar", stack: "total", data: s.values, itemStyle: { color }, barMaxWidth: 36 };
    }),
  };
}

export function targetOption(d: any, o: any) {
  const cur = o.currency;
  return {
    ...base(), legend: { top: 0, textStyle: { color: COLORS.text } }, grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
    tooltip: { ...base().tooltip, trigger: "axis",
      formatter: (ps: any) => {
        const i = ps[0].dataIndex, a = d.actual[i], t = d.target[i];
        return `${esc(d.x[i])}<br/>Actual: <b>${esc(fmtNum(a, cur))}</b><br/>Target: ${esc(fmtNum(t, cur))}<br/>Reached: ${t ? pct(a / t) : "–"}`;
      } },
    xAxis: catAxis(d.x), yAxis: valueAxis(cur),
    series: [
      { name: "Actual", type: "bar", data: d.actual, itemStyle: { color: COLORS.accent, borderRadius: [3, 3, 0, 0] }, barMaxWidth: 36 },
      { name: o.target_column ?? "Target", type: "line", data: d.target, symbol: "diamond", symbolSize: 7,
        lineStyle: { width: 2, type: "dashed", color: COLORS.ink }, itemStyle: { color: COLORS.ink } },
    ],
  };
}

export function scatterOption(d: any, o: any) {
  return {
    ...base(), grid: { left: 8, right: 16, top: 16, bottom: 28, containLabel: true },
    tooltip: { ...base().tooltip, trigger: "item",
      formatter: (p: any) => `Excel row ${esc(p.data[2])}<br/>${esc(o.x)}: <b>${esc(fmtNum(p.data[0]))}</b><br/>${esc(o.y)}: <b>${esc(fmtNum(p.data[1]))}</b>` },
    xAxis: { ...valueAxis(), name: o.x, nameLocation: "middle", nameGap: 26, scale: true },
    yAxis: { ...valueAxis(), name: o.y, scale: true },
    series: [{ type: "scatter", data: d.points, symbolSize: 6, itemStyle: { color: COLORS.accent, opacity: 0.55 } }],
  };
}

export function histogramOption(d: any, o: any) {
  const labels = d.counts.map((_: number, i: number) => `${fmtNum(d.edges[i], null, true)}–${fmtNum(d.edges[i + 1], null, true)}`);
  return {
    ...base(), tooltip: { ...base().tooltip, trigger: "axis",
      formatter: (ps: any) => `${esc(labels[ps[0].dataIndex])}<br/><b>${ps[0].value}</b> rows` },
    xAxis: catAxis(labels, { axisLabel: { color: COLORS.text, hideOverlap: true } }), yAxis: valueAxis(),
    series: [{ type: "bar", data: d.counts, barCategoryGap: "10%", itemStyle: { color: COLORS.accent, borderRadius: [3, 3, 0, 0] } }],
  };
}

/** `view` lets the user switch a ranking between bars and a donut when the spec offers it. */
export function chartOption(kind: string, data: any, options: any, view?: string): any {
  const k = view ?? kind;
  switch (k) {
    case "line": return lineOption(data, options);
    case "hbar": return hbarOption(data, options);
    case "donut": return donutOption(data, options);
    case "stacked_bar": return stackedOption(data, options);
    case "multi_line": return stackedOption(data, options, true);
    case "target": return targetOption(data, options);
    case "scatter": return scatterOption(data, options);
    case "histogram": return histogramOption(data, options);
    default: throw new Error(`No renderer for chart kind "${kind}"`);
  }
}
