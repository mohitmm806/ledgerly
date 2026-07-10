import { useState, useEffect } from "react";
import ExtractionPanel from "./ExtractionPanel.jsx";
import SourceView from "./SourceView.jsx";

export default function DocumentDetail({ doc, loading, onExtracted }) {
  // Which field is currently located on the source. Shared between the field
  // list and the image overlay.
  const [selectedField, setSelectedField] = useState(null);

  // Reset the selection when switching documents.
  useEffect(() => {
    setSelectedField(null);
  }, [doc?.id]);

  if (loading) return <div className="loading">Loading…</div>;
  if (!doc)
    return (
      <div className="empty">
        Select a document to see the extracted data and source.
      </div>
    );

  if (doc.status === "failed") {
    return (
      <div>
        <h2>{doc.filename}</h2>
        <p className="error">Could not read this file: {doc.error}</p>
      </div>
    );
  }

  const provenance = doc.extraction?.provenance || [];

  return (
    <div>
      <h2>{doc.filename}</h2>
      <div className="sub">
        {doc.source_method === "ocr" ? "Read via OCR" : "Read from PDF text layer"}{" "}
        · {doc.page_count} page(s) · {doc.blocks.length} word blocks
      </div>

      <div className="review-layout">
        <div className="review-left">
          <ExtractionPanel
            doc={doc}
            onExtracted={onExtracted}
            selectedField={selectedField}
            onSelectField={setSelectedField}
          />
          <details className="raw">
            <summary>Raw extracted text</summary>
            <div className="text-block">{doc.raw_text || "(no text found)"}</div>
          </details>
        </div>

        <div className="review-right">
          <SourceView
            doc={doc}
            provenance={provenance}
            selectedField={selectedField}
          />
        </div>
      </div>
    </div>
  );
}
