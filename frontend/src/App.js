import React, {
  useState,
  useRef,
  useEffect,
  useCallback,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const DEVELOPER_KEY = process.env.REACT_APP_GOOGLE_DEVELOPER_KEY;

// ───────── helpers ─────────
const getCookie = (name) => {
  const m = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return m ? decodeURIComponent(m[2]) : null;
};

// ────────────────────────────────────────────────────────────────────────────────
export default function App() {
  /* ───── state ───── */
  const [messages, setMessages] = useState([]);
  const [input,    setInput]    = useState("");
  const [chatLoading, setLoading] = useState(false);

  const [files, setFiles]   = useState([]);
  const [search, setSearch] = useState("");
  const fetchTimer = useRef(null);

  const [pickerReady, setPickerReady] = useState(false);

  /* ───── ensure CSRF cookie exists ───── */
  useEffect(() => {
    fetch("/api/csrf", { credentials: "include" }).catch(() => {});
  }, []);

  /* ───── bootstrap Google Picker ───── */
  useEffect(() => {
    const initPicker = () =>
      window.gapi.load("picker", { callback: () => setPickerReady(true) });

    if (window.gapi) {
      initPicker();
    } else {
      const s = document.createElement("script");
      s.src   = "https://apis.google.com/js/api.js";
      s.onload = initPicker;
      document.body.appendChild(s);
    }
  }, []);

  /* ───────── core: fetch token + open picker ───────── */
  const fetchTokenAndOpenPicker = useCallback(async () => {
    let res;
    try {
      res = await fetch("/api/drive/token", {
        credentials: "include",
        headers:     { Accept: "application/json" },
      });
    } catch {
      alert("Network error contacting server");
      return;
    }

    if (!res.ok) {
      alert("Could not obtain Drive token.");
      return;
    }

    const { token } = await res.json();
    if (!token) {
      alert("No Drive token received");
      return;
    }

    const view = new window.google.picker.DocsView()
      .setIncludeFolders(true)
      .setSelectFolderEnabled(true);

    const picker = new window.google.picker.PickerBuilder()
      .addView(view)
      .enableFeature(window.google.picker.Feature.MULTISELECT_ENABLED)
      .setDeveloperKey(DEVELOPER_KEY)
      .setOAuthToken(token)
      .setOrigin(window.location.origin)
      .setCallback(async (data) => {
        if (data.action === window.google.picker.Action.PICKED) {
          const picked = data.docs.map((d) => ({ id: d.id, name: d.name }));
          await fetch("/api/drive/files", {
            method:      "POST",
            credentials: "include",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken":  getCookie("csrftoken"),
              Accept:         "application/json",
            },
            body: JSON.stringify({ files: picked }),
          });
          setFiles((prev) => [
            ...prev,
            ...picked.map((p) => ({ file_name: p.name, chunks: "Drive" })),
          ]);
        }
      })
      .build();

    picker.setVisible(true);
  }, []);

  /* ───────── button handler – starts full redirect round‑trip ───────── */
  const openDrivePicker = useCallback(() => {
    if (!pickerReady) return;
    // We want the OAuth round‑trip only once; afterwards we’ll land back on
    // /chat?picker=1 and auto‑launch the picker.
    const tgt = `/api/drive/token?${new URLSearchParams({
      next: encodeURIComponent("/chat?picker=1"),
    }).toString()}`;
    window.location.href = tgt;
  }, [pickerReady]);

  /* ───── auto‑launch after OAuth ───── */
  useEffect(() => {
    if (!pickerReady) return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("picker") === "1") {
      // remove the flag so we don't loop on every refresh
      params.delete("picker");
      const newQuery = params.toString();
      window.history.replaceState(
        {},
        "",
        window.location.pathname + (newQuery ? "?" + newQuery : "")
      );
      fetchTokenAndOpenPicker();
    }
  }, [pickerReady, fetchTokenAndOpenPicker]);

  /* ───── chat helpers ───── */
  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    setMessages((prev) => [...prev, { from: "user", text: input }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method:      "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken":  getCookie("csrftoken"),
          Accept:         "application/json",
        },
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
      setLoading(false);
    }
  };

  /* ───── Files list: initial & search ───── */
  useEffect(() => {
    (async () => {
      const res = await fetch("/api/files", { credentials: "include" });
      if (res.ok) setFiles(await res.json());
    })();
  }, []);

  useEffect(() => {
    if (fetchTimer.current) clearTimeout(fetchTimer.current);
    fetchTimer.current = setTimeout(async () => {
      const url = search.trim()
        ? `/api/files?q=${encodeURIComponent(search)}`
        : "/api/files";
      const res = await fetch(url, { credentials: "include" });
      if (res.ok) setFiles(await res.json());
    }, 300);
    return () => clearTimeout(fetchTimer.current);
  }, [search]);

  /* ───── render ───── */
  return (
    <div style={styles.layout}>
      <aside style={styles.sidebar}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Semantic search…"
          style={styles.searchInput}
        />

        <h4 style={{ marginTop: 16 }}>Knowledge files</h4>
        <ul style={styles.list}>
          {files.map((f) => (
            <li key={f.file_name}>
              {f.file_name}{" "}
              <small>{f.chunks && `(${f.chunks})`}</small>
              {f.distance !== undefined && (
                <small style={{ color: "#888" }}>
                  {" "}
                  – {f.distance.toFixed(2)}
                </small>
              )}
            </li>
          ))}
        </ul>

        <h4 style={{ marginTop: 24 }}>Add knowledge</h4>
        {pickerReady ? (
          <button
            style={{ ...styles.btn, width: "100%" }}
            onClick={openDrivePicker}
          >
            Connect Google Drive
          </button>
        ) : (
          <span style={{ fontSize: 12 }}>Loading Google Picker…</span>
        )}
      </aside>

      <div style={styles.wrapper}>
        <h2>Chat with your docs</h2>

        <div style={styles.chatBox}>
          {messages.map((m, i) => (
            <div
              key={i}
              style={{ textAlign: m.from === "user" ? "right" : "left" }}
            >
              {m.from === "bot" ? (
                <div
                  style={{
                    ...styles.bubble,
                    background: "#e2e2e2",
                    maxWidth: "80%",
                  }}
                >
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {m.text}
                  </ReactMarkdown>
                </div>
              ) : (
                <span style={{ ...styles.bubble, background: "#daf1fc" }}>
                  {m.text}
                </span>
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
            onChange={(e) => setInput(e.target.value)}
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

/* ───────── styles ───────── */
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

