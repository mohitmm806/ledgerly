import { describe, it, expect } from "vitest";
import { toPercentBox, confLevel, money } from "./grounding.js";

// The grounding-box math is the one piece of real geometry on the frontend: if
// it regresses, every highlight silently lands in the wrong place. So it gets
// real tests.
describe("toPercentBox", () => {
  it("converts page-space coordinates to percentages", () => {
    const box = toPercentBox({
      x0: 60,
      top: 80,
      x1: 180,
      bottom: 120,
      page_width: 600,
      page_height: 800,
    });
    expect(box.left).toBeCloseTo(10); // 60/600
    expect(box.top).toBeCloseTo(10); // 80/800
    expect(box.width).toBeCloseTo(20); // (180-60)/600
    expect(box.height).toBeCloseTo(5); // (120-80)/800
  });

  it("is resolution-independent (same percentages at any page scale)", () => {
    const small = toPercentBox({ x0: 30, top: 40, x1: 90, bottom: 60, page_width: 300, page_height: 400 });
    const large = toPercentBox({ x0: 60, top: 80, x1: 180, bottom: 120, page_width: 600, page_height: 800 });
    expect(small).toEqual(large);
  });

  it("returns null when page dimensions are missing (can't place it)", () => {
    expect(toPercentBox({ x0: 1, top: 1, x1: 2, bottom: 2, page_width: 0, page_height: 0 })).toBeNull();
    expect(toPercentBox(null)).toBeNull();
  });
});

describe("confLevel", () => {
  it("buckets confidence into colour levels at the right thresholds", () => {
    expect(confLevel(0.95)).toBe("high");
    expect(confLevel(0.85)).toBe("high"); // boundary
    expect(confLevel(0.84)).toBe("med");
    expect(confLevel(0.6)).toBe("med"); // boundary
    expect(confLevel(0.59)).toBe("low");
    expect(confLevel(0.4)).toBe("low"); // the "needs review" band
  });

  it("returns null for missing confidence so no badge is shown", () => {
    expect(confLevel(undefined)).toBeNull();
    expect(confLevel(null)).toBeNull();
  });
});

describe("money", () => {
  it("formats numbers to two decimals with optional currency", () => {
    expect(money(154)).toBe("154.00");
    expect(money(1240.5, "USD")).toBe("1240.50 USD");
  });

  it("shows an em dash for missing values", () => {
    expect(money(null)).toBe("—");
    expect(money(undefined)).toBe("—");
  });
});
