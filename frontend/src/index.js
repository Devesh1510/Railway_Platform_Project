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
      <App loggedInUser={loggedInUser} onLogout={handleLogout} />
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
