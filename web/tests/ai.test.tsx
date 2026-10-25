// @vitest-environment jsdom
/**
 * The AI-layer screens, rendered with real context, insights and answers produced by the Python worker.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/* eslint-disable @typescript-eslint/no-explicit-any */
const db = vi.hoisted(() => ({ questions: [] as any[], inserted: [] as any[], upserts: [] as any[], rpcs: [] as any[], insertError: null as any }));

vi.mock("next/dynamic", async () => {
  const React = await import("react");
  return { default: () => (props: any) => React.createElement("div", { "data-testid": "chart", "aria-label": props.label }) };
});
vi.mock("@/lib/supabase", () => {
  const chain = (rows: () => any[]) => {
    const q: any = { select: () => q, eq: () => q, order: () => q, limit: () => q, then: (res: any) => res({ data: rows(), error: null }) };
    return q;
  };
  return {
    supabase: {
      from: (t: string) => ({
        ...(t === "questions" ? chain(() => db.questions) : chain(() => [])),
        insert: async (row: any) => { if (db.insertError) return { error: db.insertError }; db.inserted.push(row); return { error: null }; },
        upsert: async (row: any) => { db.upserts.push(row); return { error: null }; },
      }),
      rpc: async (name: string, args: any) => { db.rpcs.push([name, args]); return { error: null }; },
    },
  };
});

const AI = JSON.parse(readFileSync(join(__dirname, "golden/ai.json"), "utf8"));
beforeEach(() => { db.questions = []; db.inserted = []; db.upserts = []; db.rpcs = []; db.insertError = null; });
afterEach(cleanup);

describe("About this workbook", () => {
  it("states what it looks like, on what evidence, and what was assumed", async () => {
    const { default: AboutCard } = await import("../src/components/AboutCard");
    const asked: string[] = [];
    render(<AboutCard context={AI.context} onAsk={(t) => asked.push(t)} />);
    expect(screen.getByText("sales and business performance")).toBeTruthy();
    expect(screen.getByText(/based on columns such as/)).toBeTruthy();
    expect(screen.getByText(/2026-01-04 to 2026-09-27/)).toBeTruthy();
    fireEvent.click(screen.getByText("Assumptions made"));
    expect(screen.getByText(/may be wrong/)).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button").find((b) => b.textContent?.startsWith("What is the total"))!);
    expect(asked[0]).toMatch(/total/);
  });
  it("says so when it is unsure", async () => {
    const { default: AboutCard } = await import("../src/components/AboutCard");
    const ctx = { ...AI.context, domain: { ...AI.context.domain, confidence: 0.3 }, uncertainty: "The workbook type is uncertain: no clear match." };
    render(<AboutCard context={ctx} onAsk={() => {}} />);
    expect(screen.getByText(/Possibly/)).toBeTruthy();
    expect(screen.getByText(/uncertain/)).toBeTruthy();
  });
});

describe("Insights", () => {
  it("shows the observation, keeps a hedged possibility visibly separate, and links the next check to a question", async () => {
    const { default: InsightsPanel } = await import("../src/components/InsightsPanel");
    const onAsk = vi.fn();
    const withPoss = AI.insights.map((i: any, k: number) => (k === 0 ? { ...i, interpretation: "This may be worth a closer look by month.", source: "ai" } : i));
    render(<InsightsPanel insights={withPoss} onAsk={onAsk} onDetails={() => {}} />);
    expect(screen.getByText(/Every number below was computed and checked/)).toBeTruthy();
    expect(screen.getByText("A possibility, not shown by the data:")).toBeTruthy();
    expect(screen.getByText("Worded by AI, numbers checked")).toBeTruthy();
    expect(screen.getAllByText("Built-in summary").length).toBeGreaterThan(0);
    const withPlan = AI.insights.find((i: any) => i.next_plan);
    fireEvent.click(screen.getAllByText(withPlan.next_check)[0]);
    expect(onAsk).toHaveBeenCalledWith(withPlan.next_check, withPlan.next_plan);
    const texts = AI.insights.map((i: any) => i.next_check).filter(Boolean);
    for (const t of new Set(texts)) expect(screen.getAllByText(t as string)).toHaveLength(1);  // a repeated suggestion appears once
  });
});

describe("Ask", () => {
  async function mount(initial: any = null) {
    const { default: AskPanel } = await import("../src/components/AskPanel");
    render(<AskPanel workbookId="w1" context={AI.context} initial={initial} />);
  }
  const answer = (q: string) => AI.answers.find((a: any) => a.text === q);

  it("sends a typed question to the queue, with a length limit, and clears the box", async () => {
    await mount();
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "  What is the total sales?  " } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(db.inserted).toEqual([{ workbook_id: "w1", text: "What is the total sales?", plan: null }]));
    await waitFor(() => expect((screen.getByLabelText("Your question") as HTMLInputElement).value).toBe(""));
  });
  it("suggested questions are sent with their ready plan", async () => {
    await mount();
    const chip = AI.context.suggested_questions[1];
    fireEvent.click(screen.getByText(chip.text));
    await waitFor(() => expect(db.inserted[0]).toEqual({ workbook_id: "w1", text: chip.text, plan: chip.plan }));
  });
  it("a question that arrives from an insight is asked once", async () => {
    await mount({ text: "Which category contributed most?", plan: { op: "contribution" }, nonce: 7 });
    await waitFor(() => expect(db.inserted.length).toBe(1));
    expect(db.inserted[0].plan).toEqual({ op: "contribution" });
  });
  it("the rate limit is explained, not shown as an error code", async () => {
    db.insertError = { message: "rate_limited" };
    await mount();
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "total sales" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/asked a lot of questions/);
  });

  it("renders a number answer with the evidence behind it", async () => {
    db.questions = [answer("What is the total sales?")];
    await mount();
    expect(await screen.findByText("Total total_dzd: 7,196,350 DZD, over 339 rows.")).toBeTruthy();
    fireEvent.click(screen.getByText("How was this computed?"));
    expect(screen.getByText(/Computed from your data and then checked a second way/)).toBeTruthy();
    expect(screen.getByText(/Question understood by built-in logic/)).toBeTruthy();
    expect(screen.getByText(/Built-in wording/)).toBeTruthy();
  });
  it("renders a ranking as a chart, and offers follow-up questions that carry their plans", async () => {
    db.questions = [answer("Which wilaya has the highest sales for Electronics?")];
    await mount();
    expect(await screen.findAllByTestId("chart")).toHaveLength(1);
    const f = answer("Which wilaya has the highest sales for Electronics?").answer.followups[0];
    fireEvent.click(screen.getByText(f.text));
    await waitFor(() => expect(db.inserted[0]).toEqual({ workbook_id: "w1", text: f.text, plan: f.plan }));
  });
  it("renders rows with their Excel row numbers", async () => {
    db.questions = [answer("show the largest orders")];
    await mount();
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Excel row")).toBeTruthy();
    expect(within(table).getAllByRole("row")).toHaveLength(11);
  });
  it("says where a change happened, not why", async () => {
    db.questions = [answer("Why did sales increase in September?")];
    await mount();
    expect(await screen.findByText(/This shows where the change happened, not why/)).toBeTruthy();
  });
  it("asks which number is meant instead of guessing, and re-asks with the choice", async () => {
    db.questions = [answer("What is the total")];
    await mount();
    fireEvent.click(await screen.findByText("What is the total (use quantity)"));
    await waitFor(() => expect(db.inserted[0].text).toBe("What is the total (use quantity)"));
  });
  it("choosing a clarification applies it once, even when earlier choices are already in the text", async () => {
    const { baseQuestion } = await import("../src/components/AskPanel");
    expect(baseQuestion("What is the total (use quantity) (use total_dzd)")).toBe("What is the total");
    expect(baseQuestion("How was this computed (use Total sales amount) (use Monthly total sales)")).toBe("How was this computed");
    db.questions = [{ id: "c", workbook_id: "w1", text: "What is the total (use quantity)", status: "answered", created_at: "2026-10-10T10:00:00Z",
      answer: { status: "clarify", text: "Which number do you mean?", options: ["total_dzd", "quantity"], plan: null, result: null, chart: null,
        caveats: [], notes: [], sample_rows: [], followups: [], source: { plan: "rules", text: "template" } } }];
    await mount();
    fireEvent.click(await screen.findByText("What is the total (use total_dzd)"));
    await waitFor(() => expect(db.inserted[0].text).toBe("What is the total (use total_dzd)"));
  });
  it("an unanswerable question offers answerable ones rather than an invented answer", async () => {
    db.questions = [answer("what is the weather like?")];
    await mount();
    expect(await screen.findByText(/couldn't turn that into something I can compute/)).toBeTruthy();
    expect(screen.queryByText("How was this computed?")).toBeNull();
    const s = answer("what is the weather like?").answer.suggestions;
    expect(s.length).toBeGreaterThan(0);
    expect(screen.getByText(s[0].text)).toBeTruthy();
  });
  it("shows progress while a question is queued", async () => {
    db.questions = [{ id: "p", workbook_id: "w1", text: "total sales", status: "queued", answer: null, created_at: "2026-10-10T10:00:00Z" }];
    await mount();
    expect(await screen.findByRole("status")).toBeTruthy();
  });
});

describe("AI consent", () => {
  async function mount(enabled: boolean, serverHasAi: boolean | null = true) {
    const { default: AiConsent } = await import("../src/components/AiConsent");
    const onChange = vi.fn();
    render(<AiConsent userId="u1" enabled={enabled} onChange={onChange} workbookId="w1" serverHasAi={serverHasAi} />);
    return onChange;
  }
  it("is off by default and states exactly what is and is not sent", async () => {
    await mount(false);
    expect((screen.getByRole("switch") as HTMLInputElement).checked).toBe(false);
    const never = screen.getByText((_, el) => el?.tagName === "LI" && /^Never sent:/.test(el.textContent ?? ""));
    expect(never.textContent).toMatch(/spreadsheet rows, people's names, free-text columns, or the file itself/);
    const sent = screen.getByText((_, el) => el?.tagName === "LI" && /^Sent:/.test(el.textContent ?? ""));
    expect(sent.textContent).toMatch(/column names.*names of categories.*figures already computed/);
    expect(screen.getByText(/may use inputs to improve their products/)).toBeTruthy();
    expect(screen.queryByText(/Rewrite this workbook/)).toBeNull();
  });
  it("turning it on records consent with a timestamp; turning it off clears it", async () => {
    const onChange = await mount(false);
    fireEvent.click(screen.getByRole("switch"));
    await waitFor(() => expect(db.upserts[0]).toMatchObject({ user_id: "u1", ai_enabled: true }));
    expect(db.upserts[0].ai_consent_at).toBeTruthy();
    expect(onChange).toHaveBeenCalledWith(true);
    cleanup();
    const off = await mount(true);
    fireEvent.click(screen.getByRole("switch"));
    await waitFor(() => expect(db.upserts[1]).toMatchObject({ ai_enabled: false, ai_consent_at: null }));
    expect(off).toHaveBeenCalledWith(false);
  });
  it("can rewrite insights, and is honest when the server has no provider", async () => {
    await mount(true, false);
    expect(screen.getByText(/No AI provider is configured on this server/)).toBeTruthy();
    fireEvent.click(screen.getByText(/Rewrite this workbook/));
    await waitFor(() => expect(db.rpcs).toEqual([["request_reanalysis", { p_workbook: "w1" }]]));
  });
});
