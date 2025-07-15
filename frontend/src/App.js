import React, { useState } from "react";

/**
 * Very small all-in-one UI:  
 * – Chat panel (existing functionality)  
 * – "Upload document" panel → sends text to /api/ingest so the backend can embed & store it.  
 * The component stays self-contained with **no extra libraries** (just Fetch + FileReader).
 */
export default function App() {
  /* Chat state */
  const [messages, setMessages] = useState([
    { from: "bot", text: "Hello! How can I help you?" },
  ]);
  const [input, setInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  /* Upload state */
  const [file, setFile] = useState(null);
  const [uploadMsg, setUploadMsg] = useState(null); // success / error string
  const [uploadLoading, setUploadLoading] = useState(false);

  /* – – – Chat helpers – – – */
  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    // optimistic render
    setMessages((prev) => [...prev, { from: "user", text: input }]);
    setInput("");
    setChatLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input }),
      });
      if (!res.ok) throw new Error("network");
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { from: "bot", text: data.response || "(no response)" },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { from: "bot", text: "Sorry, there was an error contacting the server." },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  /* – – – Upload helpers – – – */
  const handleFileChange = (e) => {
    setFile(e.target.files[0] || null);
    setUploadMsg(null);
  };

  const handleUpload = () => {
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async () => {
      const text = reader.result;
      if (!text || typeof text !== "string") {
        setUploadMsg("Could not read file contents.");
        return;
      }

      setUploadLoading(true);
      try {
        const res = await fetch("/api/ingest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: text }),
        });
        if (!res.ok) throw new Error("ingest failed");
        await res.json();
        setUploadMsg("✓ Document uploaded & ingested");
        setFile(null);
        // optional: you might want to clear the input element here
      } catch (err) {
        setUploadMsg("Error uploading document");
      } finally {
        setUploadLoading(false);
      }
    };
    reader.readAsText(file);
  };

  /* – – – UI – – – */
  return (
    <div style={styles.wrapper}>
      <h2>Chatbot with RAG upload</h2>

      {/* Chat window */}
      <div style={styles.chatBox}>
        {messages.map((m, i) => (
          <div key={i} style={{ textAlign: m.from === "user" ? "right" : "left" }}>
            <span style={{ ...styles.bubble, background: m.from === "user" ? "#daf1fc" : "#e2e2e2" }}>{m.text}</span>
          </div>
        ))}
        {chatLoading && (
          <div style={{ textAlign: "left" }}>
            <span style={{ ...styles.bubble }}>...</span>
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
        <button type="submit" style={styles.btn} disabled={chatLoading}>Send</button>
      </form>

      <hr style={{ margin: "24px 0" }} />

      {/* Upload section */}
      <h3>Add knowledge</h3>
      <input type="file" accept=".txt,.md,.json" onChange={handleFileChange} disabled={uploadLoading} />
      <button style={{ ...styles.btn, marginLeft: 8 }} onClick={handleUpload} disabled={uploadLoading || !file}>
        {uploadLoading ? "Uploading…" : "Upload"}
      </button>
      {uploadMsg && <p>{uploadMsg}</p>}
    </div>
  );
}

/* – – – inline styles – – – */
const styles = {
  wrapper: {
    margin: "40px auto",
    border: "1px solid #ccc",
    borderRadius: 8,
    padding: 16,
    fontFamily: "Arial, sans-serif",
  },
  chatBox: {
    minHeight: 200,
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
};

