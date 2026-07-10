// Pure helpers shared by the review UI, extracted so they can be unit-tested
// independently of React. These are the bits of real logic on the frontend:
// the coordinate math that places grounding boxes, and the confidence bucketing
// that decides what the reviewer's eye is drawn to.

// Convert a provenance box (stored in page-space, same units as page_width/
// height) into CSS percentages so it overlays correctly at any display size or
// zoom. Returns null when the page dimensions are missing (can't place it).
export function toPercentBox(p) {
  if (!p || !p.page_width || !p.page_height) return null;
  return {
    left: (p.x0 / p.page_width) * 100,
    top: (p.top / p.page_height) * 100,
    width: ((p.x1 - p.x0) / p.page_width) * 100,
    height: ((p.bottom - p.top) / p.page_height) * 100,
  };
}

// Bucket a 0-1 confidence into a level that drives colour (green/amber/red).
// null/undefined -> null so the badge is simply not shown.
export function confLevel(c) {
  if (c === undefined || c === null) return null;
  if (c >= 0.85) return "high";
  if (c >= 0.6) return "med";
  return "low";
}

// Format a money value for display; null/undefined -> em dash.
export function money(v, currency) {
  if (v === null || v === undefined) return "—";
  const n = Number(v).toFixed(2);
  return currency ? `${n} ${currency}` : n;
}
