import React, { useState } from 'react';

function App() {
  const [messages, setMessages] = useState([
    { from: 'bot', text: 'Hello! How can I help you?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleInputChange = (e) => {
    setInput(e.target.value);
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (input.trim() === '') return;
    const userMessage = { from: 'user', text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      // Replace '/api/chat' with your actual backend endpoint
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ message: input })
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const data = await response.json();
      const botMessage = {
        from: 'bot',
        text: data.response || "Sorry, I didn't understand that."
      };
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        { from: 'bot', text: "Sorry, there was an error contacting the server." }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      maxWidth: 400,
      margin: '40px auto',
      border: '1px solid #ccc',
      borderRadius: 8,
      padding: 16,
      fontFamily: 'Arial, sans-serif'
    }}>
      <h2>Chatbot</h2>
      <div style={{
        minHeight: 200,
        maxHeight: 300,
        overflowY: 'auto',
        marginBottom: 12,
        background: '#f9f9f9',
        padding: 8,
        borderRadius: 4,
        border: '1px solid #eee'
      }}>
        {messages.map((msg, idx) => (
          <div key={idx} style={{
            textAlign: msg.from === 'user' ? 'right' : 'left',
            margin: '6px 0'
          }}>
            <span style={{
              display: 'inline-block',
              background: msg.from === 'user' ? '#daf1fc' : '#e2e2e2',
              color: '#222',
              padding: '6px 12px',
              borderRadius: 16,
              maxWidth: '80%',
              wordBreak: 'break-word'
            }}>
              {msg.text}
            </span>
          </div>
        ))}
        {loading && (
          <div style={{ textAlign: 'left', margin: '6px 0' }}>
            <span style={{
              display: 'inline-block',
              background: '#e2e2e2',
              color: '#222',
              padding: '6px 12px',
              borderRadius: 16,
              maxWidth: '80%',
              wordBreak: 'break-word'
            }}>
              ...
            </span>
          </div>
        )}
      </div>
      <form onSubmit={handleSend} style={{ display: 'flex', gap: 8 }}>
        <input
          type="text"
          value={input}
          onChange={handleInputChange}
          placeholder="Type your message..."
          style={{
            flex: 1,
            padding: 8,
            borderRadius: 16,
            border: '1px solid #ccc',
            outline: 'none'
          }}
          disabled={loading}
        />
        <button
          type="submit"
          style={{
            padding: '8px 16px',
            borderRadius: 16,
            border: 'none',
            background: '#007bff',
            color: '#fff',
            cursor: 'pointer'
          }}
          disabled={loading}
        >
          Send
        </button>
      </form>
    </div>
  );
}

export default App;