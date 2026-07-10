import { useState, useEffect } from "react";
import { pageImageUrl } from "../api.js";
import { toPercentBox } from "../lib/grounding.js";

const ZOOM_MIN = 1;
const ZOOM_MAX = 3;
const ZOOM_STEP = 0.25;

export default function SourceView({ doc, provenance, selectedField }) {
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [imgError, setImgError] = useState(false);

  // Reset when the document changes.
  useEffect(() => {
    setPage(1);
    setZoom(1);
    setImgError(false);
  }, [doc?.id]);

  const onThisPage = provenance.filter(
    (p) => p.matched && (p.page || 1) === page
  );

  const clamp = (z) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));

  return (
    <div className="source-view">
      <div className="source-toolbar">
        <span className="tag">Source · click a field to locate it</span>
        <span className="zoom-controls">
          <button onClick={() => setZoom((z) => clamp(z - ZOOM_STEP))} disabled={zoom <= ZOOM_MIN}>−</button>
          <span className="zoom-label">{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom((z) => clamp(z + ZOOM_STEP))} disabled={zoom >= ZOOM_MAX}>+</button>
        </span>
        {doc.page_count > 1 && (
          <span className="pager">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>‹</button>
            {page}/{doc.page_count}
            <button disabled={page >= doc.page_count} onClick={() => setPage((p) => p + 1)}>›</button>
          </span>
        )}
      </div>

      {imgError ? (
        <div className="empty">Could not render this page.</div>
      ) : (
        <div className="source-scroll">
          <div className="source-canvas" style={{ width: `${zoom * 100}%` }}>
            <img
              src={pageImageUrl(doc.id, page)}
              alt={`${doc.filename} page ${page}`}
              onError={() => setImgError(true)}
            />
            {onThisPage.map((p) => {
              const box = toPercentBox(p);
              if (!box) return null;
              const active = p.field_key === selectedField;
              return (
                <div
                  key={p.field_key}
                  className={`overlay-box ${active ? "active" : ""} ${
                    p.confidence < 0.6 ? "lowconf" : ""
                  }`}
                  style={{
                    left: `${box.left}%`,
                    top: `${box.top}%`,
                    width: `${box.width}%`,
                    height: `${box.height}%`,
                  }}
                  title={`${p.field_key} · confidence ${p.confidence}`}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
