import React, { useState } from 'react';
import './Login.css';

const API_BASE = import.meta.env.MODE === 'production' ? 'https://cow-monitoring01.onrender.com' : '';

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username_or_email: username,
          password: password,
        }),
      });

      const data = await res.json();

      if (res.ok && data.success) {
        localStorage.setItem('auth_token', data.token);
        localStorage.setItem('username', data.username);
        onLogin();
      } else {
        setError(data.detail || 'Authentication failed. Please check your credentials.');
      }
    } catch (err) {
      setError('Network error. Failed to connect to server.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        
        {/* Logo Section */}
        <div className="login-logo-container">
          <div className="login-logo">
            <img src="/cow-logo.png" alt="Cow Logo" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
          </div>
          <h2 className="login-title">IIT Ropar AwaDH</h2>
          <div className="login-subtitle">Gatewayless Cow Health Monitoring Platform</div>
        </div>

        {/* Form Header */}
        <div className="login-header">
          <h3>SYSTEM AUTHENTICATION</h3>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="input-group">
            <label>OPERATOR CREDENTIALS (USERNAME / EMAIL)</label>
            <input 
              type="text" 
              placeholder="e.g. Admin"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          <div className="input-group">
            <label>ACCOUNT PASSWORD</label>
            <input 
              type="password" 
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          
          {error && <div className="login-error">{error}</div>}

          <button type="submit" className="login-button" disabled={loading}>
            {loading ? 'Authenticating...' : 'Authenticate & Connect'}
          </button>
        </form>

        {/* Footer Links */}
        <div className="login-footer">
          <a href="#">Register Operator</a>
          <a href="#">Recover Credentials</a>
        </div>
      </div>
    </div>
  );
}
