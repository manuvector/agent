// frontend/src/App.js
import React, { useState, useRef, useEffect } from "react";

export default function App() {
  /* ───── State ───── */
  const [messages, setMessages]   = useState([]);
  const [input, setInput]         = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  const [file, setFile]           = useState(null);
  const [uploadMsg, setUploadMsg] = useState(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const fileInputRef              = useRef(null);

  const [files, setFiles]         = useState([]);
  const [search, setSearch]       = useState("");
  const fetchTimer                = useRef(null);   // debounce timer

  /* ───── Chat helpers ───── */
  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    setMessages((prev) => [...prev, { from: "user", text: input }]);
    setInput("");
    setChatLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { from: "bot", text: data.response || "(no response)" },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { from: "bot", text: "Sorry, there was an error contacting the server." },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  /* ───── Upload helpers ───── */
  const handleFileChange = (e) => {
    setFile(e.target.files[0] || null);
    setUploadMsg(null);
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploadLoading(true);
    setUploadMsg(null);

    try {
      const formData = new FormData();
      formData.append("pdf_file", file);

      const res = await fetch("/api/ingest", { method: "POST", body: formData });
      if (!res.ok) throw new Error();

      await res.json();
      setUploadMsg("✓ Document uploaded & ingested");
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch {
      setUploadMsg("Error uploading document");
    } finally {
      setUploadLoading(false);
    }
  };

  /* ───── Files list: initial load ───── */
  useEffect(() => {
    (async () => {
      const res = await fetch("/api/files");
      if (res.ok) setFiles(await res.json());
    })();
  }, []);

  /* ───── Files list: live similarity search ───── */
  useEffect(() => {
    // clear previous timer
    if (fetchTimer.current) clearTimeout(fetchTimer.current);

    fetchTimer.current = setTimeout(async () => {
      const url = search.trim()
        ? `/api/files?q=${encodeURIComponent(search)}`
        : "/api/files";

      const res = await fetch(url);
      if (res.ok) setFiles(await res.json());
    }, 300);                                   // 300 ms debounce

    return () => clearTimeout(fetchTimer.current);
  }, [search]);

  /* ───── UI ───── */
  return (
    <div style={styles.layout}>
      {/* ───── Sidebar ───── */}
      <aside style={styles.sidebar}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Semantic search…"
          style={styles.searchInput}
        />

        <h4 style={{ marginTop: 16 }}>Uploaded files</h4>
        <ul style={styles.list}>
          {files.map((f) => (
            <li key={f.file_name}>
              {f.file_name} <small>({f.chunks})</small>
              {f.distance !== undefined && (
                <small style={{ color: "#888" }}> – {f.distance.toFixed(2)}</small>
              )}
            </li>
          ))}
        </ul>
      </aside>

      {/* ───── Main column ───── */}
      <div style={styles.wrapper}>
        <h2>Chat with your docs</h2>

        {/* Chat window */}
        <div style={styles.chatBox}>
          {messages.map((m, i) => (
            <div
              key={i}
              style={{ textAlign: m.from === "user" ? "right" : "left" }}
            >
              <span
                style={{
                  ...styles.bubble,
                  background: m.from === "user" ? "#daf1fc" : "#e2e2e2",
                }}
              >
                {m.text}
              </span>
            </div>
          ))}
          {chatLoading && (
            <div style={{ textAlign: "left" }}>
              <span style={styles.bubble}>…</span>
            </div>
          )}
        </div>

        {/* Chat input */}
        <form onSubmit={handleSend} style={styles.chatForm}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message…"
            style={styles.input}
            disabled={chatLoading}
          />
          <button type="submit" style={styles.btn} disabled={chatLoading}>
            Send
          </button>
        </form>

        <hr style={{ margin: "24px 0" }} />

        {/* Upload section */}
        <h3>Add knowledge</h3>
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.md,.json,.pdf"
          onChange={handleFileChange}
          disabled={uploadLoading}
        />
        <button
          style={{ ...styles.btn, marginLeft: 8 }}
          onClick={handleUpload}
          disabled={uploadLoading || !file}
        >
          {uploadLoading ? "Uploading…" : "Upload"}
        </button>
        {uploadMsg && <p>{uploadMsg}</p>}
      </div>
    </div>
  );
}

/* ───── Inline styles ───── */
const styles = {
  layout: { display: "flex", height: "100%" },

  sidebar: {
    width: 260,
    padding: 16,
    overflowY: "auto",
    borderRight: "1px solid #eee",
    background: "#fafafa",
    fontFamily: "Arial, sans-serif",
  },

  wrapper: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    padding: 16,
    boxSizing: "border-box",
    fontFamily: "Arial, sans-serif",
  },

  chatBox: {
    flex: 1,
    minHeight: 0,
    overflowY: "auto",
    marginBottom: 12,
    background: "#f9f9f9",
    padding: 8,
    borderRadius: 4,
    border: "1px solid #eee",
  },

  bubble: {
    display: "inline-block",
    padding: "6px 12px",
    borderRadius: 16,
    wordBreak: "break-word",
  },

  chatForm: { display: "flex", gap: 8 },

  input: {
    flex: 1,
    padding: 8,
    borderRadius: 16,
    border: "1px solid #ccc",
    outline: "none",
  },

  btn: {
    padding: "8px 16px",
    borderRadius: 16,
    border: "none",
    background: "#007bff",
    color: "#fff",
    cursor: "pointer",
  },

  searchInput: {
    width: "100%",
    padding: 6,
    borderRadius: 8,
    border: "1px solid #ccc",
  },

  list: { listStyle: "none", padding: 0, margin: 0, fontSize: 14 },
};

