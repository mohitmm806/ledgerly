function StatusBadge({ status }) {
  return <span className={`badge ${status}`}>{status}</span>;
}

export default function DocumentList({ docs, loading, selectedId, onSelect }) {
  if (loading) return <div className="loading">Loading documents…</div>;
  if (!docs.length)
    return <div className="empty">No documents yet. Upload one to start.</div>;

  return (
    <ul className="doc-list">
      {docs.map((d) => (
        <li
          key={d.id}
          className={d.id === selectedId ? "active" : ""}
          onClick={() => onSelect(d.id)}
        >
          <div className="name">{d.filename}</div>
          <div className="meta">
            <StatusBadge status={d.status} />{" "}
            {d.source_method && <span>· {d.source_method}</span>}{" "}
            {d.page_count > 0 && <span>· {d.page_count}p</span>}
          </div>
        </li>
      ))}
    </ul>
  );
}
