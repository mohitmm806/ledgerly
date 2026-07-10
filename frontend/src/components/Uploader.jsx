import { useRef, useState } from "react";

export default function Uploader({ onUpload }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      await onUpload(file);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      // A rejected file (wrong type, unreadable) is normal user input, not a
      // crash. Explain it inline and let them try again.
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <label>
        <strong>Upload invoice</strong>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,image/*"
          onChange={handleChange}
          disabled={busy}
        />
      </label>
      <div className="hint">
        {busy ? "Reading document…" : "PDF or image. Scanned files are OCR'd."}
      </div>
      {error && <div className="error">{error}</div>}
    </div>
  );
}
