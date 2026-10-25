// @vitest-environment jsdom
/** The guided tour, rendered with the real guide and charts the worker produced for the sales workbook. */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/* eslint-disable @typescript-eslint/no-explicit-any */
const db = vi.hoisted(() => ({ rows: [] as any[], inserted: [] as any[], insertError: null as any }));

vi.mock("next/dynamic", async () => {
  const React = await import("react");
  return { default: () => (props: any) => React.createElement("div", { "data-testid": "chart", "aria-label": props.label }) };
});
vi.mock("@/lib/supabase", () => ({
  supabase: {
    from: () => ({
      insert: (row: any) => ({
        select: () => ({
          single: async () => {
            if (db.insertError) return { data: null, error: db.insertError };
            const r = { id: `g${db.inserted.length + 1}`, ...row, status: "queued", answer: null, created_at: "2026-10-10T10:00:00Z" };
            db.inserted.push(row);
            db.rows.push(r);
            return { data: { id: r.id }, error: null };
          },
        }),
      }),
      select: () => ({ eq: (_c: string, id: string) => ({ single: async () => ({ data: db.rows.find((r) => r.id === id) ?? null, error: null }) }) }),
    }),
  },
}));

const AI = JSON.parse(readFileSync(join(__dirname, "golden/ai.json"), "utf8"));
const D = JSON.parse(readFileSync(join(__dirname, "golden/dashboard.json"), "utf8"));
beforeEach(() => { db.rows = []; db.inserted = []; db.insertError = null; });
afterEach(cleanup);

async function mount(over: Record<string, any> = {}) {
  const { default: GuidePanel } = await import("../src/components/GuidePanel");
  const h = { onDetails: vi.fn(), onAskTab: vi.fn(), onDone: vi.fn() };
  render(<GuidePanel guide={AI.guide} charts={D.charts} workbookId="w1" pollMs={5} {...h} {...over} />);
  return h;
}
const step = (id: string) => AI.guide.steps.find((s: any) => s.id === id);
const stepper = () => screen.getByRole("navigation", { name: "Guided steps" });

describe("the tour", () => {
  it("starts with the big picture, the report's flow listed in order, and the first step marked current", async () => {
    await mount();
    expect(screen.getByRole("heading", { name: "Let's understand the big picture" })).toBeTruthy();
    expect(screen.getByText(step("overview").narrative)).toBeTruthy();
    expect(step("overview").narrative).toContain("7,196,350 DZD");
    const items = within(stepper()).getAllByRole("button");
    expect(items.map((b) => b.textContent?.replace(/^[✓\d]+/, ""))).toEqual(AI.guide.steps.map((s: any) => s.title));
    expect(items[0].getAttribute("aria-current")).toBe("step");
    expect(screen.getByText(`Step 1 of ${AI.guide.steps.length}`)).toBeTruthy();
    expect(screen.getByText("Total total_dzd")).toBeTruthy(); // the KPI cards that step points to
  });

  it("moves forward and back, and the stepper marks what has been visited", async () => {
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "Start" }));
    expect(screen.getByRole("heading", { name: step("sources").title })).toBeTruthy();
    expect(screen.getByText(step("sources").narrative)).toBeTruthy();
    expect(screen.getAllByTestId("chart")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("heading", { name: step("overview").title })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Back" }) as HTMLButtonElement).disabled).toBe(true);
    expect(within(stepper()).getAllByRole("button")[1].textContent).toContain("✓");
  });

  it("any step can be skipped to directly", async () => {
    await mount();
    fireEvent.click(within(stepper()).getByText(step("target").title));
    expect(screen.getByRole("heading", { name: "Are you on track?" })).toBeTruthy();
    expect(screen.getByText(/53%/)).toBeTruthy();
    expect(screen.getByText(`Step ${AI.guide.steps.findIndex((s: any) => s.id === "target") + 1} of ${AI.guide.steps.length}`)).toBeTruthy();
  });

  it("the last step finishes the tour and offers where to go next", async () => {
    const h = await mount();
    fireEvent.click(within(stepper()).getByText("Where to go next"));
    expect(screen.getByText("Good places to continue")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ask your own question" }));
    expect(h.onAskTab).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Finish" }));
    expect(h.onDone).toHaveBeenCalled();
  });

  it("states what is unusual as a pattern to check, and shows caveats when there are some", async () => {
    await mount();
    fireEvent.click(within(stepper()).getByText("There's something unusual"));
    expect(screen.getByText(/not conclusions\./)).toBeTruthy();
    cleanup();
    const withNotes = { ...AI.guide, steps: AI.guide.steps.map((s: any) => (s.id === "overview" ? { ...s, notes: ["3 row(s) have no value in “total_dzd” and are left out."] } : s)) };
    await mount({ guide: withNotes });
    expect(screen.getByText(/3 row\(s\) have no value/)).toBeTruthy();
  });
});

describe("buttons run inside the step", () => {
  it("sends the button's plan, shows progress, then the verified result in place", async () => {
    await mount();
    fireEvent.click(within(stepper()).getByText("There's something unusual"));
    const a = step("unusual").actions.find((x: any) => x.label.startsWith("Inspect transactions"));
    fireEvent.click(screen.getByRole("button", { name: a.label }));
    await waitFor(() => expect(db.inserted).toEqual([{ workbook_id: "w1", text: a.text, plan: a.plan }]));
    expect(await screen.findByRole("status")).toBeTruthy(); // "Working on it…"
    const real = AI.answers.find((x: any) => x.text === "show the largest orders");  // what the worker produces for this kind of plan
    db.rows[0] = { ...db.rows[0], status: "answered", answer: real.answer };
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Excel row")).toBeTruthy();
    expect(within(table).getAllByRole("row")).toHaveLength(11);
  });

  it("follow-ups inside a result run in the same step", async () => {
    await mount();
    fireEvent.click(within(stepper()).getByText(step("sources").title));
    fireEvent.click(screen.getByRole("button", { name: step("sources").actions[0].label }));
    await waitFor(() => expect(db.inserted).toHaveLength(1));
    const real = AI.answers.find((x: any) => x.text === "Which wilaya has the highest sales for Electronics?");
    db.rows[0] = { ...db.rows[0], status: "answered", answer: real.answer };
    const fu = real.answer.followups[0];
    fireEvent.click(await screen.findByText(fu.text));
    await waitFor(() => expect(db.inserted[1]).toEqual({ workbook_id: "w1", text: fu.text, plan: fu.plan }));
  });

  it("each step keeps its own result when you move around", async () => {
    await mount();
    fireEvent.click(within(stepper()).getByText(step("change").title));
    fireEvent.click(screen.getByRole("button", { name: step("change").actions[1].label }));
    await waitFor(() => expect(db.inserted).toHaveLength(1));
    fireEvent.click(within(stepper()).getByText(step("overview").title));
    expect(screen.queryByRole("status")).toBeNull();
    fireEvent.click(within(stepper()).getByText(step("change").title));
    expect(await screen.findByRole("status")).toBeTruthy();
  });

  it("rate limiting is explained, and a quality button just opens the Details tab", async () => {
    const h = await mount();
    db.insertError = { message: "rate_limited" };
    fireEvent.click(within(stepper()).getByText(step("change").title));
    fireEvent.click(screen.getByRole("button", { name: step("change").actions[0].label }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/asked a lot of questions/);
    cleanup();
    const guide = { ...AI.guide, steps: [...AI.guide.steps, { id: "quality", kind: "quality", title: "Check the data", narrative: "Before relying on the totals, check: x.", chart_keys: [], fact_keys: [], notes: [], value: 0.6, actions: [{ label: "Review the issues", kind: "details", text: null, plan: null }] }] };
    const h2 = await mount({ guide });
    fireEvent.click(within(stepper()).getByText("Check the data"));
    fireEvent.click(screen.getByRole("button", { name: "Review the issues" }));
    expect(h2.onDetails).toHaveBeenCalled();
    expect(db.inserted).toHaveLength(0);
    void h;
  });
});

describe("what should I pay attention to?", () => {
  it("renders the highlights as findings with runnable next steps, and no calculation box", async () => {
    const { AnswerView } = await import("../src/components/AskPanel");
    const a = AI.answers.find((x: any) => x.text === "What should I pay attention to?");
    const onAsk = vi.fn();
    render(<AnswerView q={{ id: "h", workbook_id: "w1", text: a.text, status: "answered", answer: a.answer, created_at: "" }} onAsk={onAsk} />);
    expect(screen.getByText(/These are patterns in the data, not explanations/)).toBeTruthy();
    const items = a.answer.result.data.items;
    expect(screen.getAllByRole("listitem")).toHaveLength(items.length);
    expect(screen.queryByText("How was this computed?")).toBeNull();
    const withPlan = items.find((i: any) => i.next_plan);
    fireEvent.click(screen.getByText(withPlan.next_check));
    expect(onAsk).toHaveBeenCalledWith(withPlan.next_check, withPlan.next_plan);
  });
});
