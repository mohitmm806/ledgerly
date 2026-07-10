import { useEffect, useState } from "react";
import { listDocuments, getDocument, uploadDocument } from "./api.js";
import Uploader from "./components/Uploader.jsx";
import DocumentList from "./components/DocumentList.jsx";
import DocumentDetail from "./components/DocumentDetail.jsx";
import QueryBar from "./components/QueryBar.jsx";

export default function App() {
  const [docs, setDocs] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    setLoadingList(true);
    try {
      setDocs(await listDocuments());
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingList(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (selectedId == null) {
      setDetail(null);
      return;
    }
    setLoadingDetail(true);
    getDocument(selectedId)
      .then(setDetail)
      .catch((e) => setError(e.message))
      .finally(() => setLoadingDetail(false));
  }, [selectedId]);

  async function handleUpload(file) {
    // Optimistically select the new doc once it comes back extracted.
    const created = await uploadDocument(file);
    await refresh();
    setSelectedId(created.id);
  }

  return (
    <div className="app">
      <header>
        <h1>Ledgerly</h1>
        <p>
          Upload an invoice. It's read into text and positioned word blocks —
          the raw material that later lets every extracted value point back to
          where it came from.
        </p>
      </header>

      <div className="panel querypanel">
        <QueryBar onOpenDocument={(id) => setSelectedId(id)} />
      </div>

      <div className="layout">
        <div>
          <div className="panel uploader">
            <Uploader onUpload={handleUpload} />
          </div>
          <div className="panel">
            <DocumentList
              docs={docs}
              loading={loadingList}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </div>
        </div>

        <div className="panel detail">
          <DocumentDetail
            doc={detail}
            loading={loadingDetail}
            onExtracted={(extraction) => {
              // Merge the fresh extraction into the open detail without a refetch.
              setDetail((d) => (d ? { ...d, extraction } : d));
              refresh();
            }}
          />
        </div>
      </div>

      {error && <p className="error">{error}</p>}
    </div>
  );
}
