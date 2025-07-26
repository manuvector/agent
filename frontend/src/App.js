// frontend/src/App.js
import React, { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const DEVELOPER_KEY = process.env.REACT_APP_GOOGLE_DEVELOPER_KEY;

/* ───────── helpers ───────── */
const getCookie = (name) => {
  const m = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return m ? decodeURIComponent(m[2]) : null;
};

export default function App() {
  /* state */
  const [messages, setMessages] = useState([]);
  const [input, setInput]       = useState("");
  const [chatLoading, setLoading] = useState(false);

  const [files,  setFiles]  = useState([]);
  const [search, setSearch] = useState("");
  const fetchTimer          = useRef(null);

  const [pickerReady, setPickerReady] = useState(false);

  /* --- Notion modal state --- */
  const [nOpen, setNOpen]       = useState(false);
  const [nSearch, setNSearch]   = useState("");
  const [nResults, setNResults] = useState([]);
  const [nChosen, setNChosen]   = useState(new Set());

  /* ensure CSRF cookie */
  useEffect(() => { fetch("/api/csrf",{credentials:"include"}).catch(()=>{}); }, []);

  /* load Google Picker */
  useEffect(() => {
    const init = () => window.gapi.load("picker", { callback: () => setPickerReady(true) });
    if (window.gapi) init();
    else {
      const s = document.createElement("script");
      s.src   = "https://apis.google.com/js/api.js";
      s.onload = init;
      document.body.appendChild(s);
    }
  }, []);

  /* Drive picker helpers */
  const fetchTokenAndOpenPicker = useCallback(async () => {
    const res = await fetch("/api/drive/token", { credentials:"include", headers:{Accept:"application/json"} });
    if (!res.ok) { alert("Could not obtain Drive token"); return; }
    const { token } = await res.json();
    if (!token) { alert("No Drive token received"); return; }

    const view = new window.google.picker.DocsView().setIncludeFolders(true).setSelectFolderEnabled(true);
    const picker = new window.google.picker.PickerBuilder()
      .addView(view)
      .enableFeature(window.google.picker.Feature.MULTISELECT_ENABLED)
      .setDeveloperKey(DEVELOPER_KEY)
      .setOAuthToken(token)
      .setOrigin(window.location.origin)
      .setCallback(async (data) => {
        if (data.action === window.google.picker.Action.PICKED) {
          const picked = data.docs.map((d) => ({ id:d.id, name:d.name }));
          await fetch("/api/drive/files", {
            method:"POST", credentials:"include",
            headers:{
              "Content-Type":"application/json",
              "X-CSRFToken":getCookie("csrftoken"),
              Accept:"application/json",
            },
            body: JSON.stringify({ files: picked }),
          });
          setFiles((prev) => [...prev, ...picked.map(p=>({file_name:p.name, chunks:"Drive"}))]);
        }
      }).build();
    picker.setVisible(true);
  }, []);

  const openDrivePicker = useCallback(() => {
    if (!pickerReady) return;
    window.location.href = "/api/drive/token?"+new URLSearchParams({next:"/chat?picker=1"});
  }, [pickerReady]);

  /* auto-launch Drive picker */
  useEffect(() => {
    if (!pickerReady) return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("picker") === "1") {
      params.delete("picker");
      window.history.replaceState({}, "", window.location.pathname);
      fetchTokenAndOpenPicker();
    }
  }, [pickerReady, fetchTokenAndOpenPicker]);

  /* --- Notion picker helpers --- */
  const openNotionOAuth = () => {
    window.location.href = "/api/notion/token?"+new URLSearchParams({next:"/chat?npicker=1"});
  };

  /* kick modal after OAuth */
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("npicker") === "1") {
      params.delete("npicker");
      window.history.replaceState({}, "", window.location.pathname);
      setNOpen(true);
    }
  }, []);

  const searchNotion = useCallback(async (q) => {
    const res = await fetch("/api/notion/pages?q="+encodeURIComponent(q), { credentials:"include" });
    if (res.ok) setNResults(await res.json());
  }, []);

  /* chat helpers */
  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    setMessages(prev=>[...prev, {from:"user", text:input}]);
    setInput(""); setLoading(true);
    try {
      const res = await fetch("/api/chat", {
        method:"POST", credentials:"include",
        headers:{
          "Content-Type":"application/json",
          "X-CSRFToken":getCookie("csrftoken"),
          Accept:"application/json"
        },
        body: JSON.stringify({ message: input }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setMessages(prev=>[...prev, {from:"bot", text:data.response||"(no response)"}]);
    } catch {
      setMessages(prev=>[...prev, {from:"bot", text:"Server error."}]);
    } finally { setLoading(false); }
  };

  /* initial + search list */
  useEffect(() => {
    (async () => {
      const res = await fetch("/api/files", {credentials:"include"});
      if (res.ok) setFiles(await res.json());
    })();
  }, []);

  useEffect(() => {
    if (fetchTimer.current) clearTimeout(fetchTimer.current);
    fetchTimer.current = setTimeout(async () => {
      const url = search.trim()? `/api/files?q=${encodeURIComponent(search)}` : "/api/files";
      const res = await fetch(url, { credentials:"include" });
      if (res.ok) setFiles(await res.json());
    }, 300);
    return () => clearTimeout(fetchTimer.current);
  }, [search]);

  /* render */
  return (
    <div style={styles.layout}>
      {/* ───── sidebar ───── */}
      <aside style={styles.sidebar}>
        <input value={search} onChange={e=>setSearch(e.target.value)}
               placeholder="Semantic search…" style={styles.searchInput}/>
        <h4 style={{marginTop:16}}>Knowledge files</h4>
        <ul style={styles.list}>
          {files.map(f=>(
            <li key={f.file_name}>{f.file_name}
              <small>{f.chunks && ` (${f.chunks})`}</small>
              {f.distance!==undefined && <small style={{color:"#888"}}> – {f.distance.toFixed(2)}</small>}
            </li>
          ))}
        </ul>

        <h4 style={{marginTop:24}}>Add knowledge</h4>
        <button style={{...styles.btn,width:"100%"}} onClick={openDrivePicker}>
          Connect Google Drive
        </button>
        <button style={{...styles.btn,width:"100%",marginTop:8}} onClick={openNotionOAuth}>
          Connect Notion
        </button>
      </aside>

      {/* ───── chat area ───── */}
      <div style={styles.wrapper}>
        <h2>Chat with your docs</h2>
        <div style={styles.chatBox}>
          {messages.map((m,i)=>(
            <div key={i} style={{textAlign:m.from==="user"?"right":"left"}}>
              {m.from==="bot"?(
                <div style={{...styles.bubble,background:"#e2e2e2",maxWidth:"80%"}}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                </div>
              ):(
                <span style={{...styles.bubble,background:"#daf1fc"}}>{m.text}</span>
              )}
            </div>
          ))}
          {chatLoading && <div style={{textAlign:"left"}}><span style={styles.bubble}>…</span></div>}
        </div>
        <form onSubmit={handleSend} style={styles.chatForm}>
          <input type="text" value={input} onChange={e=>setInput(e.target.value)}
                 placeholder="Type your message…" style={styles.input} disabled={chatLoading}/>
          <button type="submit" style={styles.btn} disabled={chatLoading}>Send</button>
        </form>
      </div>

      {/* ───── Notion modal ───── */}
      {nOpen && (
        <div style={{
          position:"fixed",inset:0,background:"rgba(0,0,0,.5)",
          display:"flex",alignItems:"center",justifyContent:"center"
        }}>
          <div style={{background:"#fff",padding:20,borderRadius:8,width:420,maxHeight:"80%",overflowY:"auto"}}>
            <h3>Select Notion pages</h3>
            <input value={nSearch} onChange={e=>{ setNSearch(e.target.value); searchNotion(e.target.value);} }
                   placeholder="Search…" style={{width:"100%",marginBottom:8}}/>
            <ul style={{maxHeight:220,overflowY:"auto"}}>
              {nResults.map(p=>(
                <li key={p.id}>
                  <label>
                    <input type="checkbox"
                      checked={nChosen.has(p.id)}
                      onChange={e=>{
                        setNChosen(prev=>{
                          const s=new Set(prev);
                          e.target.checked? s.add(p.id):s.delete(p.id);
                          return s;
                        });
                      }}/> {p.title}
                  </label>
                </li>
              ))}
            </ul>
            <button style={styles.btn} onClick={async ()=>{
              const chosenPages = nResults.filter(p=>nChosen.has(p.id));
              if (!chosenPages.length) { setNOpen(false); return; }
              await fetch("/api/notion/files",{
                method:"POST",credentials:"include",
                headers:{
                  "Content-Type":"application/json",
                  "X-CSRFToken":getCookie("csrftoken")
                },
                body: JSON.stringify({ pages: chosenPages })
              });
              setFiles(prev=>[
                ...prev,
                ...chosenPages.map(p=>({file_name:p.title,chunks:"Notion"}))
              ]);
              setNOpen(false); setNSearch(""); setNResults([]); setNChosen(new Set());
            }}>Add</button>{" "}
            <button style={{...styles.btn,background:"#666"}} onClick={()=>setNOpen(false)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* styles (unchanged except extra btn margin) */
const styles = {
  layout:{display:"flex",height:"100%"},
  sidebar:{width:260,padding:16,overflowY:"auto",borderRight:"1px solid #eee",background:"#fafafa",fontFamily:"Arial, sans-serif"},
  wrapper:{flex:1,display:"flex",flexDirection:"column",padding:16,boxSizing:"border-box",fontFamily:"Arial, sans-serif"},
  chatBox:{flex:1,minHeight:0,overflowY:"auto",marginBottom:12,background:"#f9f9f9",padding:8,borderRadius:4,border:"1px solid #eee"},
  bubble:{display:"inline-block",padding:"6px 12px",borderRadius:16,wordBreak:"break-word"},
  chatForm:{display:"flex",gap:8},
  input:{flex:1,padding:8,borderRadius:16,border:"1px solid #ccc",outline:"none"},
  btn:{padding:"8px 16px",borderRadius:16,border:"none",background:"#007bff",color:"#fff",cursor:"pointer"},
  searchInput:{width:"100%",padding:6,borderRadius:8,border:"1px solid #ccc"},
  list:{listStyle:"none",padding:0,margin:0,fontSize:14},
};

