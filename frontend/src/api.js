// Single place that knows how to talk to the API. Base URL is injected at
// build time so the same code runs locally and in docker/deploy.
const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export async function listDocuments() {
  const res = await fetch(`${BASE}/documents`);
  if (!res.ok) throw new Error("Could not load documents");
  return res.json();
}

export async function getDocument(id) {
  const res = await fetch(`${BASE}/documents/${id}`);
  if (!res.ok) throw new Error("Could not load document");
  return res.json();
}

export function pageImageUrl(id, page = 1) {
  return `${BASE}/documents/${id}/page/${page}.png`;
}

export async function queryNatural(question) {
  const res = await fetch(`${BASE}/query/nl`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q: question }),
  });
  if (!res.ok) {
    let detail = "Query failed";
    try {
      detail = (await res.json()).detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

export async function extractDocument(id) {
  const res = await fetch(`${BASE}/documents/${id}/extract`, { method: "POST" });
  if (!res.ok) {
    let detail = "Extraction failed";
    try {
      detail = (await res.json()).detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

export async function uploadDocument(file) {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${BASE}/documents`, { method: "POST", body });
  if (!res.ok) {
    // Surface the backend's reason (e.g. "Unsupported content type") so the
    // user sees why their file was rejected instead of a generic failure.
    let detail = "Upload failed";
    try {
      detail = (await res.json()).detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}
