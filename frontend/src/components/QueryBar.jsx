import { useState } from "react";
import { queryNatural } from "../api.js";

// Plain-English search over extracted invoices. Shows the parsed filter so the
// interpretation is visible, not hidden.
export default function QueryBar({ onOpenDocument }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [response, setResponse] = useState(null);

  async function run(e) {
    e.preventDefault();
    if (!q.trim()) return;
    setBusy(true);
    setError("");
    try {
      setResponse(await queryNatural(q));
    } catch (err) {
      setError(err.message);
      setResponse(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="querybar">
      <form onSubmit={run}>
        <input
          type="text"
          value={q}
          placeholder='Ask: "Acme invoices over $500 this year"'
          onChange={(e) => setQ(e.target.value)}
        />
        <button disabled={busy}>{busy ? "Searching…" : "Search"}</button>
      </form>

      {error && <div className="error">{error}</div>}

      {response && (
        <div className="query-results">
          <div className="parsed-filter">
            Interpreted as:{" "}
            {Object.keys(response.applied_filter).length === 0 ? (
              <em>everything (no filters)</em>
            ) : (
              Object.entries(response.applied_filter).map(([k, v]) => (
                <span className="chip" key={k}>
                  {k}: {String(v)}
                </span>
              ))
            )}
          </div>

          {response.count === 0 ? (
            <div className="empty">No invoices matched.</div>
          ) : (
            <table className="blocks">
              <thead>
                <tr><th>Vendor</th><th>Invoice #</th><th>Date</th><th>Total</th><th></th></tr>
              </thead>
              <tbody>
                {response.results.map((r) => (
                  <tr key={r.document_id}>
                    <td>{r.vendor || "—"}</td>
                    <td>{r.invoice_number || "—"}</td>
                    <td>{r.invoice_date || "—"}</td>
                    <td>
                      {r.total != null
                        ? `${r.total.toFixed(2)}${r.currency ? " " + r.currency : ""}`
                        : "—"}
                    </td>
                    <td>
                      <button className="link" onClick={() => onOpenDocument(r.document_id)}>
                        open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
