import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ExtractionPanel from "./ExtractionPanel.jsx";

function docWith(extraction) {
  return { id: 1, filename: "inv.pdf", extraction };
}

const baseExtraction = {
  vendor: "Acme Corp",
  invoice_number: "INV-1001",
  invoice_date: "2026-03-14",
  currency: "USD",
  subtotal: 140,
  tax: 14,
  discount: null,
  total: 154,
  attempts: 1,
  validation_passed: true,
  model_name: "test",
  line_items: [],
  issues: [],
  provenance: [
    { field_key: "vendor", matched: true, confidence: 0.9 },
    { field_key: "total", matched: true, confidence: 0.4 }, // low -> should flag
  ],
};

describe("ExtractionPanel", () => {
  it("renders the extracted fields", () => {
    render(
      <ExtractionPanel doc={docWith(baseExtraction)} selectedField={null} onSelectField={() => {}} />
    );
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("INV-1001")).toBeInTheDocument();
    expect(screen.getByText("154.00 USD")).toBeInTheDocument();
  });

  it("flags low-confidence fields for review", () => {
    render(
      <ExtractionPanel doc={docWith(baseExtraction)} selectedField={null} onSelectField={() => {}} />
    );
    // total has confidence 0.4, so exactly one field should be flagged.
    expect(screen.getByText(/1 field\(s\) to review/)).toBeInTheDocument();
  });

  it("prompts to extract when there's no extraction yet", () => {
    render(
      <ExtractionPanel doc={docWith(null)} selectedField={null} onSelectField={() => {}} />
    );
    expect(screen.getByRole("button", { name: /extract invoice/i })).toBeInTheDocument();
  });
});
