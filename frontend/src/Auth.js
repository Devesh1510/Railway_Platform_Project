import React, { useState } from 'react';
import './Auth.css';

// ── Password validation ───────────────────────────────────────────────────────
function validatePassword(pw) {
  const errors = [];
  if (pw.length < 8)            errors.push('At least 8 characters');
  if (!/[a-z]/.test(pw))        errors.push('At least one lowercase letter');
  if (!/[A-Z]/.test(pw))        errors.push('At least one uppercase letter');
  if (!/[0-9]/.test(pw))        errors.push('At least one number');
  if (!/[^a-zA-Z0-9]/.test(pw)) errors.push('At least one symbol');
  return errors;
}

// ── localStorage helpers ──────────────────────────────────────────────────────
function getUsers() {
  try { return JSON.parse(localStorage.getItem('psc_users') || '{}'); }
  catch { return {}; }
}
function saveUsers(users) {
  localStorage.setItem('psc_users', JSON.stringify(users));
}
function setSession(userId) {
  localStorage.setItem('psc_session', userId);
}
export function getSession() {
  return localStorage.getItem('psc_session');
}
export function clearSession() {
  localStorage.removeItem('psc_session');
}

// ── Create Account ────────────────────────────────────────────────────────────
function CreateAccount({ onSwitch, onSuccess }) {
  const [userId, setUserId]     = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm]   = useState('');
  const [error, setError]       = useState('');

  const handlePasswordChange = (val) => {
    setPassword(val);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    if (!userId.trim()) { setError('User ID cannot be empty.'); return; }

    const errs = validatePassword(password);
    if (errs.length > 0) { setError('Password does not meet requirements.'); return; }
    if (password !== confirm) { setError('Passwords do not match.'); return; }

    const users = getUsers();
    if (users[userId.trim()]) { setError('User ID already exists. Please log in.'); return; }

    users[userId.trim()] = password;
    saveUsers(users);
    setSession(userId.trim());
    onSuccess(userId.trim());
  };

  return (
    <div className="auth-card">
      <div className="auth-logo">🚆</div>
      <h2 className="auth-title">Pune Division Controller</h2>
      <p className="auth-subtitle">Create Controller Account</p>

      <form onSubmit={handleSubmit} className="auth-form">
        <label className="auth-label">User ID</label>
        <input
          className="auth-input"
          type="text"
          placeholder="Choose a user ID"
          value={userId}
          onChange={e => setUserId(e.target.value)}
          autoComplete="username"
        />

        <label className="auth-label">Password</label>
        <input
          className="auth-input"
          type="password"
          placeholder="Create a password"
          value={password}
          onChange={e => handlePasswordChange(e.target.value)}
          autoComplete="new-password"
        />

        {/* Live password criteria */}
        {password.length > 0 && (
          <ul className="pw-criteria">
            {[
              { label: 'At least 8 characters',        ok: password.length >= 8 },
              { label: 'Lowercase letter',              ok: /[a-z]/.test(password) },
              { label: 'Uppercase letter',              ok: /[A-Z]/.test(password) },
              { label: 'Number',                        ok: /[0-9]/.test(password) },
              { label: 'Symbol (e.g. @, #, !)',         ok: /[^a-zA-Z0-9]/.test(password) },
            ].map(c => (
              <li key={c.label} className={c.ok ? 'pw-ok' : 'pw-fail'}>
                {c.ok ? '✓' : '✗'} {c.label}
              </li>
            ))}
          </ul>
        )}

        <label className="auth-label">Confirm Password</label>
        <input
          className="auth-input"
          type="password"
          placeholder="Re-enter password"
          value={confirm}
          onChange={e => setConfirm(e.target.value)}
          autoComplete="new-password"
        />

        {error && <p className="auth-error">{error}</p>}

        <button type="submit" className="auth-btn">Create Account</button>
      </form>

      <p className="auth-switch">
        Already have an account?{' '}
        <button className="auth-link" onClick={onSwitch}>Log in</button>
      </p>
    </div>
  );
}

// ── Login ─────────────────────────────────────────────────────────────────────
function Login({ onSwitch, onSuccess }) {
  const [userId, setUserId]     = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    const users = getUsers();
    if (!users[userId.trim()]) { setError('User ID not found.'); return; }
    if (users[userId.trim()] !== password) { setError('Incorrect password.'); return; }

    setSession(userId.trim());
    onSuccess(userId.trim());
  };

  return (
    <div className="auth-card">
      <div className="auth-logo">🚆</div>
      <h2 className="auth-title">Pune Division Controller</h2>
      <p className="auth-subtitle">Controller Login</p>

      <form onSubmit={handleSubmit} className="auth-form">
        <label className="auth-label">User ID</label>
        <input
          className="auth-input"
          type="text"
          placeholder="Enter your user ID"
          value={userId}
          onChange={e => setUserId(e.target.value)}
          autoComplete="username"
        />

        <label className="auth-label">Password</label>
        <input
          className="auth-input"
          type="password"
          placeholder="Enter your password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          autoComplete="current-password"
        />

        {error && <p className="auth-error">{error}</p>}

        <button type="submit" className="auth-btn">Log In</button>
      </form>

      <p className="auth-switch">
        New controller?{' '}
        <button className="auth-link" onClick={onSwitch}>Create account</button>
      </p>
    </div>
  );
}

// ── Auth wrapper (exported) ───────────────────────────────────────────────────
export default function AuthGate({ onLogin }) {
  const [screen, setScreen] = useState('login');

  return (
    <div className="auth-bg">
      {screen === 'login'
        ? <Login   onSwitch={() => setScreen('create')} onSuccess={onLogin} />
        : <CreateAccount onSwitch={() => setScreen('login')}  onSuccess={onLogin} />}
    </div>
  );
}
