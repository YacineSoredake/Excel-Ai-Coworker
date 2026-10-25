// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const save = vi.fn();
vi.mock("jspdf", () => ({
  jsPDF: class {
    addPage() {}
    setFillColor() {}
    setFont() {}
    setFontSize() {}
    setTextColor() {}
    text() {}
    rect() {}
    roundedRect() {}
    line() {}
    circle() {}
    setDrawColor() {}
    setLineWidth() {}
    splitTextToSize(text: string) { return [text]; }
    save = save;
  },
}));

import ExportReport from "../src/components/ExportReport";

describe("export report", () => {
  it("downloads a compact PDF report instead of opening print", () => {
    render(
      <ExportReport filename="sales.xlsx" context={null} charts={[]} facts={[]} insights={[]} guide={null} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));
    expect(save).toHaveBeenCalledWith("sales-report.pdf");
  });
});
