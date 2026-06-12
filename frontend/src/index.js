import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import AuthGate, { getSession, clearSession } from './Auth';
import reportWebVitals from './reportWebVitals';

function Root() {
  const [loggedInUser, setLoggedInUser] = useState(null);

  useEffect(() => {
    const session = getSession();
    if (session) setLoggedInUser(session);
  }, []);

  const handleLogin = (userId) => {
    setLoggedInUser(userId);
  };

  const handleLogout = () => {
    clearSession();
    setLoggedInUser(null);
  };

  if (!loggedInUser) {
    return <AuthGate onLogin={handleLogin} />;
  }

  return (
    <div>
      <div style={{
        position: 'absolute',
        top: '10px',
        right: '10px',
        background: '#2c2c2e',
        padding: '6px 14px',
        borderRadius: '6px',
        fontSize: '0.8rem',
        color: '#aaa',
        display: 'flex',
        gap: '10px',
        alignItems: 'center',
        zIndex: 1000,
      }}>
        <span>👤 {loggedInUser}</span>
        <button
          onClick={handleLogout}
          style={{
            background: '#ff4d4d',
            color: 'white',
            border: 'none',
            padding: '4px 10px',
            borderRadius: '4px',
            fontSize: '0.75rem',
            cursor: 'pointer',
            fontWeight: 600,
          }}
        >
          Logout
        </button>
      </div>
      <App />
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);

reportWebVitals();
