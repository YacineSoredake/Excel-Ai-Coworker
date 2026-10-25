"use client";

import { jsPDF } from "jspdf";
import type { ChartRow, ContextRow, FactRow, GuideRow, InsightRow } from "@/lib/types";

type Pdf = InstanceType<typeof jsPDF>;
type Color = readonly [number, number, number];

const C: { ink: Color; muted: Color; accent: Color; pale: Color; line: Color; green: Color; amber: Color } = {
  ink: [24, 24, 27], muted: [82, 82, 91], accent: [76, 87, 190], pale: [241, 242, 253],
  line: [226, 228, 235], green: [22, 115, 73], amber: [143, 88, 0],
};
const PAGE = { width: 210, height: 297, margin: 16, bottom: 278 };

function text(pdf: Pdf, value: string, x: number, y: number, size = 9, color: Color = C.muted) {
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(size);
  pdf.setTextColor(...color);
  pdf.text(value, x, y);
}

function bold(pdf: Pdf, value: string, x: number, y: number, size = 11, color: Color = C.ink) {
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(size);
  pdf.setTextColor(...color);
  pdf.text(value, x, y);
  pdf.setFont("helvetica", "normal");
}

function wrap(pdf: Pdf, value: string, x: number, y: number, width: number, size = 9, color: Color = C.muted) {
  pdf.setFontSize(size);
  pdf.setTextColor(...color);
  const lines = pdf.splitTextToSize(value, width) as string[];
  pdf.text(lines, x, y);
  return y + lines.length * (size * 0.45);
}

function formatNumber(value: unknown, currency?: string | null, percent = false): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  if (percent) return `${Math.round(value * 100)}%`;
  const abs = Math.abs(value);
  const number = abs >= 1_000_000 ? `${(value / 1_000_000).toFixed(1)}M` : abs >= 1_000 ? `${(value / 1_000).toFixed(1)}K` : value.toLocaleString("en-US", { maximumFractionDigits: 1 });
  return currency ? `${number} ${currency}` : number;
}

function section(pdf: Pdf, heading: string, y: number, subtitle?: string) {
  bold(pdf, heading, PAGE.margin, y, 14);
  if (subtitle) text(pdf, subtitle, PAGE.margin, y + 6, 8);
  return y + (subtitle ? 15 : 9);
}

function header(pdf: Pdf, filename: string, page: number, pages: number) {
  pdf.setFillColor(...C.accent);
  pdf.rect(0, 0, PAGE.width, 5, "F");
  text(pdf, "AI EXCEL COPILOT", PAGE.margin, 12, 7, C.accent);
  text(pdf, `${filename}  ·  page ${page} of ${pages}`, 131, 12, 7);
  pdf.setDrawColor(...C.line);
  pdf.line(PAGE.margin, 16, PAGE.width - PAGE.margin, 16);
}

function footer(pdf: Pdf) {
  pdf.setDrawColor(...C.line);
  pdf.line(PAGE.margin, 285, PAGE.width - PAGE.margin, 285);
  text(pdf, "Generated from verified workbook analysis. Patterns are signals to investigate, not causal conclusions.", PAGE.margin, 291, 6.5);
}

function chartType(chart: ChartRow): "line" | "bar" | "target" | null {
  if (chart.kind === "line" || chart.kind === "multi_line") return "line";
  if (chart.kind === "target") return "target";
  if (chart.kind === "hbar" || chart.kind === "donut") return "bar";
  return null;
}

function drawChart(pdf: Pdf, chart: ChartRow, x: number, y: number, width: number, height: number) {
  const data = chart.data ?? {};
  pdf.setDrawColor(...C.line);
  pdf.setFillColor(255, 255, 255);
  pdf.roundedRect(x, y, width, height, 2, 2, "FD");
  bold(pdf, chart.title, x + 6, y + 9, 8.5);
  text(pdf, chart.kind === "target" ? "Actual compared with target" : chart.role === "comparison" ? "Largest groups shown first" : "Change over time", x + 6, y + 15, 6.5);
  const kind = chartType(chart);
  if (!kind) {
    text(pdf, "Chart not available in PDF format.", x + 6, y + 35, 7);
    return;
  }
  const left = x + 10, right = x + width - 7, top = y + 22, bottom = y + height - 14;
  const values: number[] = kind === "line" ? data.y ?? [] : kind === "target" ? [...(data.actual ?? []), ...(data.target ?? [])] : (data.groups ?? []).map((g: { value: number }) => g.value);
  const valid = values.filter((v) => Number.isFinite(v));
  if (!valid.length) return;
  const max = Math.max(...valid, 1), min = Math.min(0, ...valid), range = max - min || 1;
  const yFor = (value: number) => bottom - ((value - min) / range) * (bottom - top);
  pdf.setDrawColor(...C.line);
  pdf.line(left, bottom, right, bottom);
  pdf.line(left, top, left, bottom);

  if (kind === "line") {
    const xs: string[] = data.x ?? [], ys: number[] = data.y ?? [];
    pdf.setDrawColor(...C.accent);
    pdf.setLineWidth(1.1);
    ys.forEach((value, i) => {
      if (!Number.isFinite(value)) return;
      const px = left + (xs.length < 2 ? 0 : i * (right - left) / (xs.length - 1)), py = yFor(value);
      if (i > 0 && Number.isFinite(ys[i - 1])) {
        const oldX = left + (i - 1) * (right - left) / Math.max(1, xs.length - 1);
        pdf.line(oldX, yFor(ys[i - 1]), px, py);
      }
      pdf.setFillColor(...C.accent);
      pdf.circle(px, py, 1.2, "F");
      if (i === 0 || i === xs.length - 1 || xs.length <= 6) text(pdf, String(xs[i]).slice(0, 9), px - 5, bottom + 7, 5.5);
    });
  } else {
    const groups = (data.groups ?? []).slice(0, 6) as { label: string; value: number; share?: number }[];
    const actual: number[] = data.actual ?? [], target: number[] = data.target ?? [];
    const count = kind === "target" ? actual.length : groups.length;
    const gap = 3, barWidth = Math.max(3, (right - left - gap * Math.max(count - 1, 0)) / Math.max(count, 1));
    for (let i = 0; i < count; i++) {
      const value = kind === "target" ? actual[i] : groups[i].value;
      const px = left + i * (barWidth + gap), barHeight = Math.max(1, ((value - min) / range) * (bottom - top));
      pdf.setFillColor(...C.accent);
      pdf.roundedRect(px, bottom - barHeight, barWidth, barHeight, 0.8, 0.8, "F");
      text(pdf, (kind === "target" ? String(data.x?.[i] ?? "") : groups[i].label).slice(0, 9), px, bottom + 7, 5.5);
      const share = groups[i]?.share;
      if (kind === "bar" && share != null) text(pdf, `${Math.round(share * 100)}%`, px, bottom + 12, 5.5, C.accent);
      if (kind === "target" && target[i] != null) {
        const py = yFor(target[i]);
        pdf.setDrawColor(...C.ink);
        pdf.line(px - 2, py, px + barWidth + 2, py);
      }
    }
    if (kind === "target") text(pdf, "blue = actual   line = target", left, y + height - 3, 5.5);
  }
}

export default function ExportReport({ filename, context, charts, facts, insights, guide }: {
  filename: string; context: ContextRow | null; charts: ChartRow[]; facts: FactRow[]; insights: InsightRow[]; guide: GuideRow | null;
}) {
  function download() {
    const pdf = new jsPDF({ unit: "mm", format: "a4" });
    const cleanName = filename.replace(/\.[^.]+$/, "");
    const kpis = charts.filter((c) => c.placement === "kpi").sort((a, b) => a.position - b.position).slice(0, 4);
    const visuals = charts.filter((c) => ["primary", "secondary"].includes(c.placement) && chartType(c)).sort((a, b) => (a.placement === "primary" ? -1 : 1) - (b.placement === "primary" ? -1 : 1) || a.position - b.position).slice(0, 4);
    const topInsights = [...insights].sort((a, b) => a.priority - b.priority).slice(0, 5);
    const topFacts = [...facts].sort((a, b) => b.score - a.score).slice(0, 8);
    const caveats = Array.from(new Set([...topFacts.flatMap((f) => f.caveats), ...visuals.flatMap((c) => c.caveats)])).slice(0, 5);
    const pages = 3;

    // Page 1: executive overview.
    header(pdf, filename, 1, pages);
    bold(pdf, "Executive overview", PAGE.margin, 32, 22);
    text(pdf, `${context?.domain.label ?? "Workbook analysis"}  ·  ${new Date().toLocaleDateString("en-US")}`, PAGE.margin, 40, 9, C.accent);
    if (context) {
      let cy = wrap(pdf, context.purpose, PAGE.margin, 51, 178, 10);
      text(pdf, `${context.rows.toLocaleString("en-US")} rows  ·  ${context.tables} table${context.tables === 1 ? "" : "s"}  ·  ${context.sheets} sheet${context.sheets === 1 ? "" : "s"}  ·  ${Math.round(context.domain.confidence * 100)}% domain confidence`, PAGE.margin, cy + 6, 8);
    }
    let y = 76;
    y = section(pdf, "Key figures", y, "The four most useful numbers from the analyzed workbook.");
    kpis.forEach((kpi, i) => {
      const x = PAGE.margin + (i % 2) * 91, cardY = y + Math.floor(i / 2) * 31;
      pdf.setFillColor(...C.pale);
      pdf.roundedRect(x, cardY, 86, 25, 2, 2, "F");
      const value = kpi.data?.format === "percent" ? formatNumber(kpi.data?.value, null, true) : formatNumber(kpi.data?.value, kpi.data?.currency);
      bold(pdf, value, x + 6, cardY + 11, 16, C.ink);
      text(pdf, String(kpi.data?.label ?? kpi.title).slice(0, 35), x + 6, cardY + 18, 7);
      const delta = kpi.data?.delta?.pct;
      if (typeof delta === "number") text(pdf, `${delta >= 0 ? "▲" : "▼"} ${Math.abs(Math.round(delta * 100))}% vs ${kpi.data.delta.previous}`, x + 6, cardY + 23, 6.5, delta >= 0 ? C.green : C.amber);
    });
    y += Math.ceil(kpis.length / 2) * 31 + 13;
    y = section(pdf, "What matters most", y, "Prioritized findings from verified facts.");
    topInsights.slice(0, 4).forEach((insight, i) => {
      const cy = y + i * 20;
      pdf.setFillColor(...C.accent);
      pdf.circle(PAGE.margin + 2, cy - 1.5, 1.2, "F");
      wrap(pdf, insight.statement, PAGE.margin + 8, cy, 165, 9, C.ink);
      if (insight.caveats.length) text(pdf, `Caveat: ${insight.caveats[0]}`, PAGE.margin + 8, cy + 10, 6.5, C.amber);
    });
    y += Math.min(topInsights.length, 4) * 20 + 5;
    if (context?.time) {
      y = section(pdf, "Coverage", y, `${context.time.column}: ${context.time.from} to ${context.time.to} · ${context.time.granularity ?? "time series"}`);
    }
    footer(pdf);

    // Page 2: visual analysis.
    pdf.addPage();
    header(pdf, filename, 2, pages);
    y = section(pdf, "Visual analysis", 29, "Charts selected to explain trend, performance, and targets.");
    visuals.forEach((chart, i) => {
      const x = i % 2 === 0 ? PAGE.margin : 108, cy = y + Math.floor(i / 2) * 83;
      drawChart(pdf, chart, x, cy, 86, 70);
    });
    footer(pdf);

    // Page 3: evidence and action.
    pdf.addPage();
    header(pdf, filename, 3, pages);
    y = section(pdf, "Evidence and next actions", 29, "The supporting facts and limitations behind the overview.");
    bold(pdf, "Verified findings", PAGE.margin, y, 12);
    y += 7;
    topFacts.slice(0, 6).forEach((fact) => {
      y = y > 260 ? 18 : y;
      if (y === 18) { pdf.addPage(); header(pdf, filename, 3, pages); }
      bold(pdf, fact.headline, PAGE.margin, y, 8.5);
      y = wrap(pdf, fact.definition, PAGE.margin, y + 5, 178, 7.5) + 5;
    });
    y += 3;
    if (caveats.length) {
      y = section(pdf, "Important caveats", y, "Read these before acting on a pattern.");
      caveats.forEach((caveat) => {
        pdf.setFillColor(...C.amber);
        pdf.circle(PAGE.margin + 2, y - 1.5, 1, "F");
        y = wrap(pdf, caveat, PAGE.margin + 7, y, 170, 8) + 4;
      });
    }
    if (guide?.steps.length) {
      y += 4;
      y = section(pdf, "Recommended next steps", y, "Continue the investigation inside the workbook.");
      guide.steps.slice(-3).forEach((step) => {
        bold(pdf, `• ${step.title}`, PAGE.margin, y, 8.5);
        y = wrap(pdf, step.narrative, PAGE.margin + 5, y + 5, 173, 7.5) + 6;
      });
    }
    footer(pdf);
    pdf.save(`${cleanName}-report.pdf`);
  }

  return <button type="button" onClick={download} className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">Download PDF</button>;
}
