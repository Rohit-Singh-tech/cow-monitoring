import React, { useState, useEffect } from 'react';
import './Login.css'; // Reuse styles from login for inputs and buttons

const API_BASE = import.meta.env.MODE === 'production' ? 'https://cow-monitoring01.onrender.com' : '';

export default function AdminPanel() {
  const [users, setUsers] = useState([]);
  const [cows, setCows] = useState([]);
  
  // User Form
  const [newUsername, setNewUsername] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  
  // Tag Form
  const [newMacAddress, setNewMacAddress] = useState('');
  const [newAnimalId, setNewAnimalId] = useState('');
  const [newDescription, setNewDescription] = useState('');

  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  const fetchUsers = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/users`);
      const data = await res.json();
      if (data.success) setUsers(data.users);
    } catch (e) {
      console.error("Error fetching users", e);
    }
  };

  const fetchCows = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/cows`);
      const data = await res.json();
      if (data.success) setCows(data.cows);
    } catch (e) {
      console.error("Error fetching cows", e);
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchCows();
  }, []);

  const handleAddUser = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: newUsername, email: newEmail, password: newPassword })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setMessage({ type: 'success', text: 'User successfully created!' });
        setNewUsername(''); setNewEmail(''); setNewPassword('');
        fetchUsers();
      } else {
        setMessage({ type: 'error', text: data.detail || 'Failed to create user' });
      }
    } catch (e) {
      setMessage({ type: 'error', text: 'Network error creating user' });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteUser = async (id) => {
    if (!window.confirm("Are you sure you want to delete this user?")) return;
    try {
      const res = await fetch(`${API_BASE}/api/admin/users/${id}`, { method: 'DELETE' });
      if (res.ok) fetchUsers();
    } catch (e) {
      console.error("Failed to delete user", e);
    }
  };

  const handleAddTag = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/tags`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mac_address: newMacAddress, animal_id: newAnimalId, description: newDescription })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setMessage({ type: 'success', text: 'Tag successfully registered!' });
        setNewMacAddress(''); setNewAnimalId(''); setNewDescription('');
        fetchCows();
      } else {
        setMessage({ type: 'error', text: data.detail || 'Failed to register tag' });
      }
    } catch (e) {
      setMessage({ type: 'error', text: 'Network error registering tag' });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTag = async (id) => {
    if (!window.confirm("Are you sure you want to delete this cow tag?")) return;
    try {
      const res = await fetch(`${API_BASE}/api/admin/tags/${id}`, { method: 'DELETE' });
      if (res.ok) fetchCows();
    } catch (e) {
      console.error("Failed to delete tag", e);
    }
  };

  return (
    <div style={{ padding: '2rem', color: '#f8fafc', maxWidth: '1200px', margin: '0 auto' }}>
      <h2 style={{ fontSize: '2rem', marginBottom: '2rem', borderBottom: '1px solid #1e293b', paddingBottom: '1rem' }}>
        <i className="fa-solid fa-user-shield" style={{ color: '#8b5cf6', marginRight: '1rem' }}></i>
        Administrator Dashboard
      </h2>

      {message && (
        <div style={{ 
          padding: '1rem', 
          marginBottom: '2rem', 
          borderRadius: '8px', 
          background: message.type === 'error' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
          color: message.type === 'error' ? '#ef4444' : '#10b981',
          border: `1px solid ${message.type === 'error' ? '#ef4444' : '#10b981'}`
        }}>
          {message.text}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(500px, 1fr))', gap: '2rem' }}>
        
        {/* User Management Section */}
        <div className="login-card" style={{ padding: '2rem', margin: 0, maxWidth: '100%' }}>
          <h3 className="login-title" style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center' }}>
            <i className="fa-solid fa-users" style={{ marginRight: '0.75rem', color: '#3b82f6' }}></i>
            Registered Users
          </h3>
          
          <div style={{ maxHeight: '200px', overflowY: 'auto', marginBottom: '2rem', background: '#0b0f19', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#1e293b', textAlign: 'left', fontSize: '0.8rem', color: '#94a3b8' }}>
                  <th style={{ padding: '0.75rem 1rem' }}>ID</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Username</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Email</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id} style={{ borderBottom: '1px solid #1e293b' }}>
                    <td style={{ padding: '0.75rem 1rem' }}>{u.id}</td>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: 'bold' }}>{u.username}</td>
                    <td style={{ padding: '0.75rem 1rem', color: '#94a3b8' }}>{u.email}</td>
                    <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                      <button onClick={() => handleDeleteUser(u.id)} style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '1rem' }}>
                        <i className="fa-solid fa-trash"></i>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <form onSubmit={handleAddUser} className="login-form">
            <h4 style={{ color: '#94a3b8', marginBottom: '0.5rem', fontSize: '0.9rem' }}>Add New User</h4>
            <div className="input-group">
              <input type="text" placeholder="Username" required value={newUsername} onChange={e => setNewUsername(e.target.value)} />
            </div>
            <div className="input-group">
              <input type="email" placeholder="Email Address" required value={newEmail} onChange={e => setNewEmail(e.target.value)} />
            </div>
            <div className="input-group">
              <input type="password" placeholder="Password" required value={newPassword} onChange={e => setNewPassword(e.target.value)} />
            </div>
            <button type="submit" className="login-button" disabled={loading} style={{ background: 'linear-gradient(to right, #3b82f6, #2563eb)' }}>
              {loading ? 'Adding...' : 'Register User'}
            </button>
          </form>
        </div>

        {/* Tag Management Section */}
        <div className="login-card" style={{ padding: '2rem', margin: 0, maxWidth: '100%' }}>
          <h3 className="login-title" style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center' }}>
            <i className="fa-solid fa-microchip" style={{ marginRight: '0.75rem', color: '#10b981' }}></i>
            Registered Hardware Tags
          </h3>
          
          <div style={{ maxHeight: '200px', overflowY: 'auto', marginBottom: '2rem', background: '#0b0f19', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#1e293b', textAlign: 'left', fontSize: '0.8rem', color: '#94a3b8' }}>
                  <th style={{ padding: '0.75rem 1rem' }}>Animal ID</th>
                  <th style={{ padding: '0.75rem 1rem' }}>MAC Address</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {cows.map(c => (
                  <tr key={c.id} style={{ borderBottom: '1px solid #1e293b' }}>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: 'bold' }}>Cow #{c.device_id}</td>
                    <td style={{ padding: '0.75rem 1rem', color: '#94a3b8', fontFamily: 'monospace' }}>{c.mac_address}</td>
                    <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                      <button onClick={() => handleDeleteTag(c.db_id || c.id)} style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '1rem' }}>
                        <i className="fa-solid fa-trash"></i>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <form onSubmit={handleAddTag} className="login-form">
            <h4 style={{ color: '#94a3b8', marginBottom: '0.5rem', fontSize: '0.9rem' }}>Add Hardware Tag</h4>
            <div className="input-group">
              <input type="text" placeholder="Animal ID (e.g. 102)" required value={newAnimalId} onChange={e => setNewAnimalId(e.target.value)} />
            </div>
            <div className="input-group">
              <input type="text" placeholder="MAC Address (e.g. AA:BB:CC:DD:EE:FF)" required value={newMacAddress} onChange={e => setNewMacAddress(e.target.value)} />
            </div>
            <div className="input-group">
              <input type="text" placeholder="Description (Optional)" value={newDescription} onChange={e => setNewDescription(e.target.value)} />
            </div>
            <button type="submit" className="login-button" disabled={loading} style={{ background: 'linear-gradient(to right, #10b981, #059669)' }}>
              {loading ? 'Adding...' : 'Register Tag'}
            </button>
          </form>
        </div>

      </div>
    </div>
  );
}
