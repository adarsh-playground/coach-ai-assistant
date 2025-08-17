// frontend/chat-frontend/src/App.js

import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import './App.css'; // Assuming you have an App.css for styling

function App() {
  const [messages, setMessages] = useState([]); // For backend responses (Results Panel)
  const [userMessages, setUserMessages] = useState([]); // NEW: For user's own sent messages (Input Panel)
  const [messageInput, setMessageInput] = useState('');
  const [connectionStatus, setConnectionStatus] = useState('Connecting...');
  const socket = useRef(null);
  const messagesEndRef = useRef(null); // Ref for auto-scrolling Results Panel
  const userMessagesEndRef = useRef(null); // NEW: Ref for auto-scrolling Input Panel

  // Scroll to the latest message in the Results Panel
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Scroll to the latest message in the Input Panel
  const scrollToUserMessagesBottom = () => {
    userMessagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };


  useEffect(() => {
    console.log("DEBUG: App.js useEffect loaded with latest code!");
    scrollToBottom(); // Scroll Results Panel on message change
  }, [messages]);

  useEffect(() => {
    scrollToUserMessagesBottom(); // NEW: Scroll Input Panel on user message change
  }, [userMessages]);


  useEffect(() => {
    socket.current = io('http://localhost:8000', {
      path: '/socket.io',
    });

    // --- Socket.IO Event Listeners ---

    socket.current.on('connect', () => {
      console.log('Socket.IO connected:', socket.current.id);
      setConnectionStatus('Connected to chat server.');
    });

    socket.current.on('message', (data) => {
      console.log('Generic message from server:', data);
      setMessages((prevMessages) => [...prevMessages, {
        type: 'chat',
        text: data.content || data.message || JSON.stringify(data),
        sender: 'AI'
      }]);
    });

    socket.current.on('status', (data) => {
      console.log('Status from server:', data);
      if (data.content.includes("AI SQL Genie") || data.content.includes("API Key") || data.content.includes("Database connection")) {
        setConnectionStatus(data.content);
      } else {
        setMessages((prevMessages) => [...prevMessages, { type: 'system', text: data.content }]);
      }
    });

    socket.current.on('sql_result', (data) => {
      console.log('SQL Result from server:', data);
      setMessages((prevMessages) => [...prevMessages, { type: 'gemini', sender: 'AI SQL Genie', text: data.content }]);
    });

    socket.current.on('chat', (data) => {
      console.log('Chat response from server:', data);
      setMessages((prevMessages) => [...prevMessages, { type: 'gemini', sender: 'AI', text: data.content }]);
    });

    socket.current.on('error', (data) => {
      console.error('Error from server:', data);
      setMessages((prevMessages) => [...prevMessages, { type: 'system', text: `Backend Error: ${data.content}` }]);
      setConnectionStatus(`Error: ${data.content}`);
    });

    socket.current.on('disconnect', () => {
      console.log('Socket.IO disconnected');
      setConnectionStatus('Disconnected from chat.');
      setMessages((prevMessages) => [...prevMessages, { type: 'system', text: 'Disconnected from chat.' }]);
    });

    socket.current.on('connect_error', (error) => {
      console.error('Socket.IO connection error:', error);
      setConnectionStatus(`Connection error: ${error.message}. Is backend running and accessible on http://localhost:8000?`);
      setMessages((prevMessages) => [...prevMessages, { type: 'system', text: `Connection error: ${error.message}. Is backend running and accessible on http://localhost:8000?` }]);
    });

    return () => {
      if (socket.current) {
        socket.current.disconnect();
      }
    };
  }, []);

  const sendMessage = async (event) => {
    event.preventDefault();
    if (socket.current && messageInput.trim() !== '') {
      let messageType = 'user-chat-input'; // Default type for user's general message in input panel
      if (messageInput.toLowerCase().startsWith('/sql')) {
        messageType = 'user-sql-input'; // Specific type for user's SQL message in input panel
      }

      socket.current.emit('client_message', messageInput);

      // ADDED: Add user's message to the userMessages state for display in input panel
      setUserMessages((prevMessages) => [
        ...prevMessages,
        { type: messageType, text: messageInput } // Sender is implicitly 'You'
      ]);

      setMessageInput('');
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>AI SQL Genie Chat</h1>
      </header>

      <div className="status-display">
        {connectionStatus}
      </div>

      <div className="split-container">
        {/* Left Panel: Input Window */}
        <div className="input-panel">
          <h2>Type Your Query</h2>
          {/* NEW: Display area for user's own sent messages */}
          <div className="user-message-history">
            {userMessages.map((msg, index) => (
              <div key={index} className={`message ${msg.type}`}>
                <strong className="sender-name">You:</strong> {msg.text}
              </div>
            ))}
            <div ref={userMessagesEndRef} /> {/* For auto-scrolling user messages */}
          </div>

          <form onSubmit={sendMessage} className="message-form">
            <input
              type="text"
              value={messageInput}
              onChange={(e) => setMessageInput(e.target.value)}
              placeholder="Type your message or /sql question..."
            />
            <button type="submit" className="send-button">Send</button>
          </form>
        </div>

        {/* Right Panel: Results Window */}
        <div className="results-panel">
          <h2>Results</h2>
          <div className="chat-window">
            {messages.map((msg, index) => (
              <div key={index} className={`message ${msg.type}`}>
                <strong className="sender-name">{msg.sender || 'System'}:</strong> {msg.text}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
