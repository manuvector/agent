// frontend/src/App.js
import React, { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Expose your GCP API key as REACT_APP_GOOGLE_DEVELOPER_KEY=XXXX
const DEVELOPER_KEY = process.env.REACT_APP_GOOGLE_DEVELOPER_KEY;

export default function App() {
  /* ───── State ───── */
  const [messages, setMessages]   = useState([]);
  const [input, setInput]         = useState("");
  const [chatLoading, setLoading] = useState(false);

  const [files, setFiles]   = useState([]);
  const [search, setSearch] = useState("");
  const fetchTimer          = useRef(null);

  // Google Picker boot state
  const [pickerReady, setPickerReady] = useState(false);

  /* ───── Google Picker bootstrap ───── */
  useEffect(() => {
    // Helper: runs after gapi is on the page
    const initPicker = () => {
      window.gapi.load("picker", { callback: () => setPickerReady(true) });
    };

    if (window.gapi) {
      // Script already present
      initPicker();
    } else {
      // Inject script, then init
      const s = document.createElement("script");
      s.src = "https://apis.google.com/js/api.js";
      s.onload = initPicker;
      document.body.appendChild(s);
    }
  }, []);

  const openDrivePicker = useCallback(async () => {
    if (!pickerReady) return;

    // 1️⃣ Get a short‑lived token from your backend
    const res = await fetch("/api/drive/token");
    if (res.status === 400) {
      window.location.href = "/connect/drive/"; // start OAuth
      return;
    }
    if (!res.ok) {
      alert("Could not obtain Google Drive token");
      return;
    }
    const { token } = await res.json();

    // 2️⃣ Build Picker
    const view = new window.google.picker.DocsView()
      .setIncludeFolders(true)
      .setSelectFolderEnabled(true);

    const picker = new window.google.picker.PickerBuilder()
      .addView(view)
      .enableFeature(window.google.picker.Feature.MULTISELECT_ENABLED)
      .setDeveloperKey(DEVELOPER_KEY)
      .setOAuthToken(token)
      .setOrigin(window.location.origin)
      .setCallback(async data => {
        if (data.action === window.google.picker.Action.PICKED) {
          const picked = data.docs.map(d => ({ id: d.id, name: d.name }));
          await fetch("/api/drive/files", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ files: picked }),
          });
          // Optimistic UI update
          setFiles(prev => [
            ...prev,
            ...picked.map(p => ({ file_name: p.name, chunks: "Drive" })),
          ]);
        }
      })
      .build();
    picker.setVisible(true);
  }, [pickerReady]);

  /* ───── Chat helpers ───── */
  const handleSend = async e => {
    e.preventDefault();
    if (!input.trim()) return;

    setMessages(prev => [...prev, { from: "user", text: input }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setMessages(prev => [
        ...prev,
        { from: "bot", text: data.response || "(no response)" },
      ]);
    } catch {
      setMessages(prev => [
        ...prev,
        { from: "bot", text: "Sorry, there was an error contacting the server." },
      ]);
    } finally {
      setLoading(false);
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
    if (fetchTimer.current) clearTimeout(fetchTimer.current);
    fetchTimer.current = setTimeout(async () => {
      const url = search.trim()
        ? `/api/files?q=${encodeURIComponent(search)}`
        : "/api/files";
      const res = await fetch(url);
      if (res.ok) setFiles(await res.json());
    }, 300);
    return () => clearTimeout(fetchTimer.current);
  }, [search]);

  /* ───── UI ───── */
  return (
    <div style={styles.layout}>
      {/* ───── Sidebar ───── */}
      <aside style={styles.sidebar}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Semantic search…"
          style={styles.searchInput}
        />

        <h4 style={{ marginTop: 16 }}>Knowledge files</h4>
        <ul style={styles.list}>
          {files.map(f => (
            <li key={f.file_name}>
              {f.file_name} <small>{f.chunks && `(${f.chunks})`}</small>
              {f.distance !== undefined && (
                <small style={{ color: "#888" }}> – {f.distance.toFixed(2)}</small>
              )}
            </li>
          ))}
        </ul>

        <h4 style={{ marginTop: 24 }}>Add knowledge</h4>
        {pickerReady ? (
          <button style={{ ...styles.btn, width: "100%" }} onClick={openDrivePicker}>
            Connect Google Drive
          </button>
        ) : (
          <span style={{ fontSize: 12 }}>Loading Google Picker…</span>
        )}
      </aside>

      {/* ───── Main column ───── */}
      <div style={styles.wrapper}>
        <h2>Chat with your docs</h2>

        <div style={styles.chatBox}>
          {messages.map((m, i) => (
            <div key={i} style={{ textAlign: m.from === "user" ? "right" : "left" }}>
              {m.from === "bot" ? (
                <div
                  style={{
                    ...styles.bubble,
                    background: "#e2e2e2",
                    maxWidth: "80%",
                  }}
                >
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                </div>
              ) : (
                <span style={{ ...styles.bubble, background: "#daf1fc" }}>{m.text}</span>
              )}
            </div>
          ))}
          {chatLoading && (
            <div style={{ textAlign: "left" }}>
              <span style={styles.bubble}>…</span>
            </div>
          )}
        </div>

        <form onSubmit={handleSend} style={styles.chatForm}>
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Type your message…"
            style={styles.input}
            disabled={chatLoading}
          />
          <button type="submit" style={styles.btn} disabled={chatLoading}>
            Send
          </button>
        </form>
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
    width: "auto",
  },
  searchInput: {
    width: "100%",
    padding: 6,
    borderRadius: 8,
    border: "1px solid #ccc",
  },
  list: { listStyle: "none", padding: 0, margin: 0, fontSize: 14 },
};

