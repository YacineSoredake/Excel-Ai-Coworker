// @vitest-environment jsdom
/**
 * Renders the real dashboard with the real chart specs of the sales workbook, applies filters, drills down,
 * and checks the displayed numbers against what the Python worker computed. The canvas is replaced by buttons
 * that fire the same click payloads ECharts would.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { fmtNum } from "../src/lib/chartOption";
import { readTable } from "../src/lib/dataEngine";

/* eslint-disable @typescript-eslint/no-explicit-any */
const store = vi.hoisted(() => ({ rows: null as any }));

vi.mock("next/dynamic", async () => {
  const React = await import("react");
  return {
    default: () => (props: any) =>
      React.createElement("div", { "data-testid": "chart", "aria-label": props.label },
        props.onClick ? React.createElement("button", { type: "button", "aria-label": `click ${props.label}`,
          onClick: () => props.onClick({ dataIndex: 0, seriesName: props.option.series?.[0]?.name, name: "x", data: props.option.series?.[0]?.data?.[0] }) }, "click") : null),
  };
});
vi.mock("@/lib/useTableRows", async () => {
  const React = await import("react");
  return {
    useTableRows: () => {
      const [loaded, setLoaded] = React.useState(false);
      return { ensure: async () => { setLoaded(true); return store.rows; }, rowsOf: () => (loaded ? store.rows : null), state: {} };
    },
  };
});

const G = JSON.parse(readFileSync(join(__dirname, "golden/golden.json"), "utf8"));
const D = JSON.parse(readFileSync(join(__dirname, "golden/dashboard.json"), "utf8"));

beforeAll(async () => {
  const b = readFileSync(join(__dirname, "golden/sales.parquet"));
  // jsdom has its own ArrayBuffer class; build the buffer with it so the Parquet reader's instanceof check passes
  const ab = new ArrayBuffer(b.byteLength);
  new Uint8Array(ab).set(b);
  store.rows = await readTable(ab);
});
afterEach(cleanup);

async function mount(view: "overview" | "explore" = "overview") {
  const { default: Dashboard } = await import("../src/components/Dashboard");
  const onOpenDetails = vi.fn();
  render(<Dashboard view={view} tables={[D.table]} columns={D.columns} charts={D.charts} facts={D.facts}
    findings={D.findings} onOpenDetails={onOpenDetails} />);
  return { onOpenDetails };
}
const kase = (name: string) => G.sales.cases.find((c: any) => c.name === name);
const result = (c: any, op: string, extra: (q: any) => boolean = () => true) => c.results.find((r: any) => r.query.op === op && extra(r.query)).expect;
const totalCard = () => screen.getByText("Total total_dzd").closest("div")!.parentElement as HTMLElement;

describe("overview", () => {
  it("shows four KPI cards, one primary chart, and a small set of secondary charts", async () => {
    await mount();
    for (const label of ["Total total_dzd", "Records", "Total quantity"]) expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getByText(/Reached of target_dzd/)).toBeTruthy();
    expect(screen.getAllByTestId("chart").length).toBe(1 + D.charts.filter((c: any) => c.placement === "secondary").length);
    expect(screen.getByRole("region", { name: /How does total total_dzd change by month/ })).toBeTruthy();
  });
  it("KPI values and deltas are the verified numbers", async () => {
    await mount();
    const card = within(screen.getByText("Total total_dzd").parentElement as HTMLElement);
    expect(card.getByText(fmtNum(result(kase("no filters"), "agg", (q) => q.agg === "sum").value, "DZD"))).toBeTruthy();
    expect(card.getByText(/\+71%/)).toBeTruthy();
    expect(screen.getByText("53%")).toBeTruthy(); // target attainment
  });
  it("a chart explains why it exists and lists its caveats", async () => {
    await mount();
    const c = screen.getByRole("region", { name: /How does total total_dzd change by month/ });
    fireEvent.click(within(c).getByText("Why this chart"));
    expect(within(c).getByText(/incomplete|moves from one month to the next/)).toBeTruthy();
  });
  it("points to the Details tab from the quality summary", async () => {
    const { onOpenDetails } = await mount();
    fireEvent.click(screen.getByText("Review in Details"));
    expect(onOpenDetails).toHaveBeenCalled();
  });
});

describe("filters recompute the numbers in the browser", () => {
  it("filtering to one category changes the KPIs to the pandas values, and clearing restores them", async () => {
    await mount();
    const exp = kase("one category");
    fireEvent.click(screen.getByRole("button", { name: /^category/ }));
    const box = await screen.findByLabelText(/Electronics/);
    fireEvent.click(box);
    const total = fmtNum(result(exp, "agg", (q) => q.agg === "sum" && q.measure === "total_dzd").value, "DZD");
    await waitFor(() => expect(within(screen.getByText("Total total_dzd").parentElement as HTMLElement).getByText(total)).toBeTruthy());
    expect(screen.getByText(`Showing ${exp.rows} of 339 rows`)).toBeTruthy();
    expect(within(screen.getByText("Records").parentElement as HTMLElement).getByText(fmtNum(exp.rows))).toBeTruthy();
    fireEvent.click(screen.getByText("Clear filters"));
    await waitFor(() => expect(screen.queryByText(/Showing/)).toBeNull());
    expect(within(screen.getByText("Total total_dzd").parentElement as HTMLElement)
      .getByText(fmtNum(result(kase("no filters"), "agg", (q) => q.agg === "sum").value, "DZD"))).toBeTruthy();
  });
  it("a date range changes the rows and marks target charts as not filtered", async () => {
    await mount();
    const exp = kase("date range cutting months");
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-03-10" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-06-20" } });
    await waitFor(() => expect(screen.getByText(`Showing ${exp.rows} of 339 rows`)).toBeTruthy());
    expect(screen.getAllByText(/Not affected by filters/).length).toBeGreaterThan(0);
  });
  it("a filter that matches nothing says so instead of drawing empty charts", async () => {
    await mount();
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2030-01-01" } });
    await waitFor(() => expect(screen.getByText("Showing 0 of 339 rows")).toBeTruthy());
    expect(screen.getAllByText("No rows match the current filters.").length).toBeGreaterThan(0);
  });
});

describe("drill-down", () => {
  it("clicking the top bar shows exactly the rows behind it, and can filter the dashboard to them", async () => {
    await mount();
    const bar = screen.getByRole("button", { name: /click Which channel brings in the most total_dzd/ });
    fireEvent.click(bar);
    const panel = await screen.findByRole("region", { name: /Rows behind/ });
    const label = /Rows behind “(.+)”/.exec(panel.textContent!)![1];
    expect(label).toBeTruthy();
    const expectedRows = store.rows.filter((r: any) => String(r.channel).trim() === label).length;
    expect(within(panel).getByText(new RegExp(`${expectedRows} rows`))).toBeTruthy();
    expect(within(panel).getAllByRole("row").length).toBe(Math.min(expectedRows, 100) + 1);
    fireEvent.click(within(panel).getByText("Filter the dashboard to this"));
    await waitFor(() => expect(screen.getByText(`Showing ${expectedRows} of 339 rows`)).toBeTruthy());
    expect(screen.queryByRole("region", { name: /Rows behind/ })).toBeNull();
  });
  it("clicking a month on the trend shows that month's rows", async () => {
    await mount();
    fireEvent.click(screen.getByRole("button", { name: /click How does total total_dzd change by month/ }));
    const panel = await screen.findByRole("region", { name: /Rows behind 2026-01/ });
    expect(within(panel).getByText(/rows/)).toBeTruthy();
    fireEvent.click(within(panel).getByText("Close"));
    expect(screen.queryByRole("region", { name: /Rows behind/ })).toBeNull();
  });
});

describe("explore", () => {
  it("groups the remaining charts by what they answer", async () => {
    await mount("explore");
    expect(screen.getByRole("region", { name: "Trends over time" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Against targets" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Regions" })).toBeTruthy(); // wilaya is a location
  });
});
