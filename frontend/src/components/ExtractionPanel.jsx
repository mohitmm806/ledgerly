import { useState } from "react";
import { extractDocument } from "../api.js";
import { confLevel, money } from "../lib/grounding.js";

// A field row: value, a colour-coded confidence badge, clickable to locate it
// on the source. Low-confidence rows get a coloured accent so the eye lands on
// exactly the fields worth double-checking.
function Field({ label, fieldKey, value, prov, selectedField, onSelectField }) {
  const p = prov[fieldKey];
  const conf = p?.confidence;
  const level = confLevel(conf);
  const active = fieldKey === selectedField;
  const locatable = p?.matched;
  const pct = conf === undefined || conf === null ? null : Math.round(conf * 100);

  const tip = locatable
    ? `Located on source · click to highlight · confidence ${pct}%`
    : pct !== null
    ? `Couldn't locate on the page · confidence ${pct}%`
    : "";

  return (
    <tr
      className={`field-row ${active ? "active" : ""} ${
        level ? "conf-" + level : ""
      } ${locatable ? "locatable" : ""}`}
      onClick={() => locatable && onSelectField(fieldKey)}
    >
      <th>{label}</th>
      <td>{value}</td>
      <td className="conf-cell">
        {pct !== null && (
          <span className={`conf-badge ${level}`} data-tip={tip}>
            <span className="conf-dot" />
            {pct}%
            {!locatable && <span className="conf-warn"> · not located</span>}
          </span>
        )}
      </td>
    </tr>
  );
}

export default function ExtractionPanel({
  doc,
  onExtracted,
  selectedField,
  onSelectField,
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const extraction = doc.extraction;

  // Index provenance by field_key for quick lookup.
  const prov = {};
  (extraction?.provenance || []).forEach((p) => {
    prov[p.field_key] = p;
  });

  const lowCount = (extraction?.provenance || []).filter(
    (p) => p.confidence < 0.6
  ).length;

  async function runExtract() {
    setBusy(true);
    setError("");
    try {
      const result = await extractDocument(doc.id);
      onExtracted?.(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="extraction">
      <div className="extract-header">
        <strong>Structured invoice</strong>
        <button onClick={runExtract} disabled={busy}>
          {busy ? "Extracting…" : extraction ? "Re-extract" : "Extract invoice"}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {!extraction && !busy && (
        <div className="empty">
          Not extracted yet. Runs the model, checks the numbers, retries itself
          if they don't reconcile, then grounds each value back to the page.
        </div>
      )}

      {extraction && (
        <>
          <div
            className={`extract-status ${
              extraction.validation_passed ? "ok" : "warn"
            }`}
          >
            {extraction.validation_passed
              ? "Validation passed"
              : "Returned with unresolved issues"}
            {" · "}
            {extraction.attempts} attempt{extraction.attempts === 1 ? "" : "s"}
            {extraction.attempts > 1 && extraction.validation_passed
              ? " (recovered by self-correction)"
              : ""}
            {lowCount > 0 && ` · ${lowCount} field(s) to review`}
          </div>

          <div className="conf-legend">
            Confidence:
            <span className="conf-badge high"><span className="conf-dot" />high</span>
            <span className="conf-badge med"><span className="conf-dot" />medium</span>
            <span className="conf-badge low"><span className="conf-dot" />low — review</span>
          </div>

          <table className="fields">
            <tbody>
              <Field label="Vendor" fieldKey="vendor" value={extraction.vendor || "—"}
                prov={prov} selectedField={selectedField} onSelectField={onSelectField} />
              <Field label="Invoice #" fieldKey="invoice_number" value={extraction.invoice_number || "—"}
                prov={prov} selectedField={selectedField} onSelectField={onSelectField} />
              <Field label="Date" fieldKey="invoice_date" value={extraction.invoice_date || "—"}
                prov={prov} selectedField={selectedField} onSelectField={onSelectField} />
              <Field label="Subtotal" fieldKey="subtotal" value={money(extraction.subtotal, extraction.currency)}
                prov={prov} selectedField={selectedField} onSelectField={onSelectField} />
              <Field label="Tax" fieldKey="tax" value={money(extraction.tax, extraction.currency)}
                prov={prov} selectedField={selectedField} onSelectField={onSelectField} />
              {extraction.discount != null && (
                <Field label="Discount" fieldKey="discount" value={money(extraction.discount, extraction.currency)}
                  prov={prov} selectedField={selectedField} onSelectField={onSelectField} />
              )}
              <Field label="Total" fieldKey="total" value={money(extraction.total, extraction.currency)}
                prov={prov} selectedField={selectedField} onSelectField={onSelectField} />
            </tbody>
          </table>

          {extraction.line_items.length > 0 && (
            <table className="blocks line-items">
              <thead>
                <tr><th>Description</th><th>Qty</th><th>Unit</th><th>Amount</th></tr>
              </thead>
              <tbody>
                {extraction.line_items.map((li, i) => {
                  const key = `line_items[${i}].amount`;
                  const p = prov[key];
                  const active = key === selectedField;
                  return (
                    <tr
                      key={i}
                      className={`${p?.matched ? "locatable" : ""} ${active ? "active" : ""}`}
                      onClick={() => p?.matched && onSelectField(key)}
                    >
                      <td>{li.description}</td>
                      <td>{li.quantity ?? "—"}</td>
                      <td>{money(li.unit_price)}</td>
                      <td>{money(li.amount)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          {extraction.issues.length > 0 && (
            <div className="issues">
              <strong>Unresolved issues</strong>
              <ul>
                {extraction.issues.map((iss, i) => (
                  <li key={i}>{iss.message}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
