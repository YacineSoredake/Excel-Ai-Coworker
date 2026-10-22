import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { chartOption, esc, fmtNum, shortPeriod } from "../src/lib/chartOption";

/* eslint-disable @typescript-eslint/no-explicit-any */
const specs: Record<string, any[]> = JSON.parse(readFileSync(join(__dirname, "golden/charts.json"), "utf8"));

describe("formatting", () => {
  it("formats numbers", () => {
    expect(fmtNum(7196350, "DZD")).toBe("7,196,350 DZD");
    expect(fmtNum(1234567, null, true)).toBe("1.2M");
    expect(fmtNum(45000, null, true)).toBe("45K");
    expect(fmtNum(1.5)).toBe("1.5");
    expect(fmtNum(null)).toBe("–");
    expect(shortPeriod("2026-06-29/2026-07-05")).toBe("06-29");
    expect(shortPeriod("2026-07")).toBe("2026-07");
  });
  it("escapes spreadsheet text before it reaches tooltip HTML", () => {
    expect(esc('<img src=x onerror="alert(1)">')).toBe("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;");
  });
});

describe("renderers", () => {
  it("line: incomplete periods are a separate dashed series, and the tooltip says so", () => {
    const d = { x: ["2026-07", "2026-08", "2026-09"], y: [10, 20, 5], rows: [30, 31, 8], complete: [true, true, false] };
    const o = chartOption("line", d, { currency: "DZD", annotations: [{ period: "2026-08", label: "Largest change" }] });
    expect(o.series[0].data).toEqual([10, 20, null]);
    expect(o.series[1].data).toEqual([null, 20, 5]); // connects from the last complete point
    expect(o.series[1].lineStyle.type).toBe("dashed");
    expect(o.series[0].markPoint.data[0].coord).toEqual(["2026-08", 20]);
    expect(o.tooltip.formatter([{ dataIndex: 2 }])).toContain("incomplete");
    expect(o.tooltip.formatter([{ dataIndex: 1 }])).not.toContain("incomplete");
  });
  it("line with only complete periods has a single series", () => {
    const o = chartOption("line", { x: ["a", "b"], y: [1, 2], rows: [1, 1], complete: [true, true] }, {});
    expect(o.series).toHaveLength(1);
  });
  it("hbar: biggest on top, 'Other' muted, labels escaped in the tooltip", () => {
    const g = [{ label: "<b>Big</b>", value: 90, share: 0.9, rows: 9 }, { label: "Other (3)", value: 10, share: 0.1, rows: null, muted: true }];
    const o = chartOption("hbar", { groups: g }, { currency: null });
    expect(o.yAxis.inverse).toBe(true);
    expect(o.yAxis.data).toEqual(["<b>Big</b>", "Other (3)"]); // axis text is canvas, not HTML
    expect(o.series[0].data[1].itemStyle.color).not.toBe(o.series[0].data[0].itemStyle.color);
    const tip = o.tooltip.formatter({ dataIndex: 0 });
    expect(tip).toContain("&lt;b&gt;Big&lt;/b&gt;");
    expect(tip).not.toContain("<b>Big</b>");
    expect(tip).toContain("90%");
  });
  it("a ranking can be switched to a donut", () => {
    const d = { groups: [{ label: "A", value: 6, share: 0.6, rows: 6 }, { label: "B", value: 4, share: 0.4, rows: 4 }] };
    const o = chartOption("hbar", d, {}, "donut");
    expect(o.series[0].type).toBe("pie");
    expect(o.series[0].radius).toHaveLength(2);
  });
  it("stacked bars stack, and 'Other' is neutral grey", () => {
    const o = chartOption("stacked_bar", { x: ["m1", "m2"], series: [{ label: "A", values: [1, 2] }, { label: "Other", values: [1, 1] }] }, {});
    expect(o.series.every((s: any) => s.type === "bar" && s.stack === "total")).toBe(true);
    expect(o.series[1].itemStyle.color).toBe("#D4D4D8");
  });
  it("target: bars for actual, dashed line for target, reached % in the tooltip", () => {
    const o = chartOption("target", { x: ["2026-01", "2026-02"], actual: [50, 90], target: [100, 100] }, { target_column: "target_dzd" });
    expect(o.series.map((s: any) => s.type)).toEqual(["bar", "line"]);
    expect(o.series[1].name).toBe("target_dzd");
    expect(o.tooltip.formatter([{ dataIndex: 0 }])).toContain("50%");
  });
  it("scatter links dots to Excel rows; histogram labels match its bins", () => {
    const s = chartOption("scatter", { points: [[1, 2, 17]] }, { x: "a", y: "b" });
    expect(s.tooltip.formatter({ data: [1, 2, 17] })).toContain("Excel row 17");
    const h = chartOption("histogram", { edges: [0, 10, 20], counts: [5, 3] }, {});
    expect(h.xAxis.data).toHaveLength(2);
  });
  it("unknown chart kinds fail loudly instead of drawing something wrong", () => {
    expect(() => chartOption("kpi", {}, {})).toThrow();
  });
});

describe("every chart the worker produced can be rendered", () => {
  for (const [name, list] of Object.entries(specs)) {
    it(`${name}: ${list.length} specs`, () => {
      for (const c of list) {
        if (c.kind === "kpi") continue; // cards, not canvas charts
        const o = chartOption(c.kind, c.data, c.options);
        expect(o.series?.length, c.key).toBeGreaterThan(0);
        const s0 = o.series[0];
        if (c.kind === "line") expect(s0.data.length, c.key).toBe(c.data.x.length);
        if (c.kind === "hbar") expect(o.yAxis.data.length, c.key).toBe(c.data.groups.length);
        if (c.kind === "stacked_bar" || c.kind === "multi_line") expect(o.series.length, c.key).toBe(c.data.series.length);
        if (c.options.alt_kinds?.includes("donut")) expect(chartOption(c.kind, c.data, c.options, "donut").series[0].type).toBe("pie");
      }
    });
  }
});
