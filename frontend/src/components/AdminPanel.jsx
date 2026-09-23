import React, { useState, useEffect } from 'react';
import './Login.css';

const API_BASE = import.meta.env.MODE === 'production' ? 'https://cow-monitoring01.onrender.com' : '';

export default function AdminPanel({ onRefreshCows }) {
  const [tags, setTags] = useState([]);
  
  // Dynamic Tag Form matching Image 1
  const [tagDeviceId, setTagDeviceId] = useState('');
  const [tagName, setTagName] = useState('');
  const [tagBreed, setTagBreed] = useState('');
  const [tagLocation, setTagLocation] = useState('');
  const [tagWeight, setTagWeight] = useState('');
  const [tagNotes, setTagNotes] = useState('');
  const [isEditing, setIsEditing] = useState(false);

  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  const fetchTags = async () => {
    try {
      const resTags = await fetch(`${API_BASE}/api/tags`);
      const dataTags = await resTags.json();
      if (dataTags.success) setTags(dataTags.tags || []);
    } catch (e) {
      console.error("Error fetching tags", e);
    }
  };

  useEffect(() => {
    fetchTags();
  }, []);

  const handleSaveDynamicTag = async (e) => {
    e.preventDefault();
    if (!tagDeviceId || !tagName) {
      setMessage({ type: 'error', text: 'Device ID and Subject Name are required.' });
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/tags`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device_id: String(tagDeviceId).trim(),
          name: tagName.trim(),
          breed: tagBreed.trim(),
          location: tagLocation.trim(),
          weight: tagWeight.trim(),
          notes: tagNotes.trim()
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setMessage({ type: 'success', text: `Node #${tagDeviceId} (${tagName}) successfully saved to Cow Tag Registry!` });
        setTagDeviceId('');
        setTagName('');
        setTagBreed('');
        setTagLocation('');
        setTagWeight('');
        setTagNotes('');
        setIsEditing(false);
        fetchTags();
        if (onRefreshCows) onRefreshCows();
      } else {
        setMessage({ type: 'error', text: data.detail || 'Failed to register cow tag' });
      }
    } catch (e) {
      setMessage({ type: 'error', text: 'Network error registering cow tag' });
    } finally {
      setLoading(false);
    }
  };

  const handleEditTagClick = (tag) => {
    setTagDeviceId(tag.device_id || '');
    setTagName(tag.name || '');
    setTagBreed(tag.breed || '');
    setTagLocation(tag.location || '');
    setTagWeight(tag.weight || '');
    setTagNotes(tag.notes || '');
    setIsEditing(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleCancelEdit = () => {
    setTagDeviceId('');
    setTagName('');
    setTagBreed('');
    setTagLocation('');
    setTagWeight('');
    setTagNotes('');
    setIsEditing(false);
  };

  const handleDeleteTag = async (identifier) => {
    if (!window.confirm(`Are you sure you want to delete registry tag for Node #${identifier}?`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/tags/${identifier}`, { method: 'DELETE' });
      if (res.ok) {
        setMessage({ type: 'success', text: `Node #${identifier} tag removed from registry.` });
        fetchTags();
        if (onRefreshCows) onRefreshCows();
      }
    } catch (e) {
      console.error("Failed to delete tag", e);
    }
  };

  return (
    <div style={{ padding: '1.5rem 2rem', color: '#f8fafc', maxWidth: '1400px', margin: '0 auto' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', borderBottom: '1px solid #1e293b', paddingBottom: '1rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.85rem', fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: '0.75rem', fontFamily: 'var(--font-display)' }}>
            <i className="fa-solid fa-tags" style={{ color: 'var(--accent-emerald)' }}></i>
            Cow Tag Registry
          </h2>
          <div style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '0.25rem' }}>
            Configure and register cattle metadata for both Gatewayless and Aws telemetry nodes.
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', borderRadius: '6px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.3)', fontWeight: 700 }}>
            <i className="fa-solid fa-database" style={{ marginRight: '0.35rem' }}></i>
            PostgreSQL Sync
          </span>
          <span style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', borderRadius: '6px', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)', fontWeight: 700 }}>
            <i className="fa-solid fa-microchip" style={{ marginRight: '0.35rem' }}></i>
            {tags.length} Nodes Configured
          </span>
        </div>
      </div>

      {message && (
        <div style={{ 
          padding: '0.85rem 1.25rem', 
          marginBottom: '1.5rem', 
          borderRadius: '8px', 
          background: message.type === 'error' ? 'rgba(239, 68, 68, 0.12)' : 'rgba(16, 185, 129, 0.12)',
          color: message.type === 'error' ? '#ef4444' : '#10b981',
          border: `1px solid ${message.type === 'error' ? '#ef4444' : '#10b981'}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '0.9rem'
        }}>
          <span>
            <i className={`fa-solid ${message.type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-check'}`} style={{ marginRight: '0.5rem' }}></i>
            {message.text}
          </span>
          <button onClick={() => setMessage(null)} style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '1rem' }}>
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>
      )}

      {/* NEW NODE / EDIT NODE Form (Styled exactly as requested in Image 1) */}
      <div className="login-card" style={{ padding: '1.5rem 1.75rem', marginBottom: '2rem', maxWidth: '100%', margin: '0 0 2rem 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.15rem' }}>
          <h3 style={{ fontSize: '0.875rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#f8fafc', margin: 0, fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <i className={`fa-solid ${isEditing ? 'fa-pen-to-square' : 'fa-circle-plus'}`} style={{ color: isEditing ? '#38bdf8' : '#8b5cf6' }}></i>
            {isEditing ? `EDIT NODE #${tagDeviceId}` : 'NEW NODE'}
          </h3>
          {isEditing && (
            <button 
              type="button" 
              onClick={handleCancelEdit}
              style={{ background: 'transparent', border: '1px solid #475569', color: '#94a3b8', borderRadius: '6px', padding: '0.3rem 0.65rem', fontSize: '0.75rem', cursor: 'pointer', fontWeight: 600 }}
            >
              Cancel Edit
            </button>
          )}
        </div>

        <form onSubmit={handleSaveDynamicTag}>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr)) 120px', 
            gap: '0.85rem', 
            alignItems: 'flex-end' 
          }}>
            
            {/* DEVICE ID */}
            <div>
              <label style={{ display: 'block', fontSize: '0.7rem', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.4rem', fontFamily: 'var(--font-mono)' }}>
                DEVICE ID
              </label>
              <input
                type="text"
                required
                placeholder="100"
                value={tagDeviceId}
                onChange={e => setTagDeviceId(e.target.value)}
                disabled={isEditing}
                style={{ 
                  width: '100%', 
                  padding: '0.65rem 0.85rem', 
                  background: '#0b0f19', 
                  border: '1px solid #1e293b', 
                  borderRadius: '8px', 
                  color: '#f8fafc', 
                  fontSize: '0.875rem',
                  fontFamily: 'var(--font-main)'
                }}
              />
            </div>

            {/* SUBJECT NAME */}
            <div>
              <label style={{ display: 'block', fontSize: '0.7rem', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.4rem', fontFamily: 'var(--font-mono)' }}>
                SUBJECT NAME
              </label>
              <input
                type="text"
                required
                placeholder="Bovine #100"
                value={tagName}
                onChange={e => setTagName(e.target.value)}
                style={{ 
                  width: '100%', 
                  padding: '0.65rem 0.85rem', 
                  background: '#0b0f19', 
                  border: '1px solid #1e293b', 
                  borderRadius: '8px', 
                  color: '#f8fafc', 
                  fontSize: '0.875rem',
                  fontFamily: 'var(--font-main)'
                }}
              />
            </div>

            {/* BREED / TYPE */}
            <div>
              <label style={{ display: 'block', fontSize: '0.7rem', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.4rem', fontFamily: 'var(--font-mono)' }}>
                BREED / TYPE
              </label>
              <input
                type="text"
                placeholder="Holstein"
                value={tagBreed}
                onChange={e => setTagBreed(e.target.value)}
                style={{ 
                  width: '100%', 
                  padding: '0.65rem 0.85rem', 
                  background: '#0b0f19', 
                  border: '1px solid #1e293b', 
                  borderRadius: '8px', 
                  color: '#f8fafc', 
                  fontSize: '0.875rem',
                  fontFamily: 'var(--font-main)'
                }}
              />
            </div>

            {/* BARN LOCATION */}
            <div>
              <label style={{ display: 'block', fontSize: '0.7rem', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.4rem', fontFamily: 'var(--font-mono)' }}>
                BARN LOCATION
              </label>
              <input
                type="text"
                placeholder="Sector A"
                value={tagLocation}
                onChange={e => setTagLocation(e.target.value)}
                style={{ 
                  width: '100%', 
                  padding: '0.65rem 0.85rem', 
                  background: '#0b0f19', 
                  border: '1px solid #1e293b', 
                  borderRadius: '8px', 
                  color: '#f8fafc', 
                  fontSize: '0.875rem',
                  fontFamily: 'var(--font-main)'
                }}
              />
            </div>

            {/* WEIGHT */}
            <div>
              <label style={{ display: 'block', fontSize: '0.7rem', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.4rem', fontFamily: 'var(--font-mono)' }}>
                WEIGHT
              </label>
              <input
                type="text"
                placeholder="500 kg"
                value={tagWeight}
                onChange={e => setTagWeight(e.target.value)}
                style={{ 
                  width: '100%', 
                  padding: '0.65rem 0.85rem', 
                  background: '#0b0f19', 
                  border: '1px solid #1e293b', 
                  borderRadius: '8px', 
                  color: '#f8fafc', 
                  fontSize: '0.875rem',
                  fontFamily: 'var(--font-main)'
                }}
              />
            </div>

            {/* RESEARCH NOTES */}
            <div>
              <label style={{ display: 'block', fontSize: '0.7rem', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.4rem', fontFamily: 'var(--font-mono)' }}>
                RESEARCH NOTES
              </label>
              <input
                type="text"
                placeholder="Grazing"
                value={tagNotes}
                onChange={e => setTagNotes(e.target.value)}
                style={{ 
                  width: '100%', 
                  padding: '0.65rem 0.85rem', 
                  background: '#0b0f19', 
                  border: '1px solid #1e293b', 
                  borderRadius: '8px', 
                  color: '#f8fafc', 
                  fontSize: '0.875rem',
                  fontFamily: 'var(--font-main)'
                }}
              />
            </div>

            {/* ACTION BUTTON */}
            <div>
              <button
                type="submit"
                disabled={loading}
                style={{
                  width: '100%',
                  height: '38px',
                  padding: '0 0.85rem',
                  borderRadius: '8px',
                  background: isEditing 
                    ? 'linear-gradient(135deg, #059669 0%, #10b981 100%)' 
                    : 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                  color: '#ffffff',
                  border: 'none',
                  fontWeight: 800,
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.45rem',
                  transition: 'all 0.2s',
                  boxShadow: isEditing 
                    ? '0 4px 12px rgba(16, 185, 129, 0.3)' 
                    : '0 4px 12px rgba(124, 58, 237, 0.35)',
                  whiteSpace: 'nowrap'
                }}
              >
                {loading ? (
                  <i className="fa-solid fa-spinner fa-spin"></i>
                ) : isEditing ? (
                  <>Update Node</>
                ) : (
                  <>Add Node</>
                )}
              </button>
            </div>

          </div>
        </form>
      </div>

      {/* Active Registered Cattle Nodes Table */}
      <div className="login-card" style={{ padding: '1.75rem', margin: 0, maxWidth: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <h3 className="login-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.1rem' }}>
            <i className="fa-solid fa-list-check" style={{ color: '#10b981' }}></i>
            Registered Cattle Nodes
          </h3>
          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
            Click edit to load node details into form
          </span>
        </div>
        
        <div style={{ overflowX: 'auto', background: '#0b0f19', borderRadius: '8px', border: '1px solid #1e293b' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: '#1e293b', fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                <th style={{ padding: '0.75rem 1rem' }}>Device ID</th>
                <th style={{ padding: '0.75rem 1rem' }}>Subject Name</th>
                <th style={{ padding: '0.75rem 1rem' }}>Breed / Type</th>
                <th style={{ padding: '0.75rem 1rem' }}>Barn Location</th>
                <th style={{ padding: '0.75rem 1rem' }}>Weight</th>
                <th style={{ padding: '0.75rem 1rem' }}>Research Notes</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tags && tags.length > 0 ? (
                tags.map(t => (
                  <tr key={t.id || t.device_id} style={{ borderBottom: '1px solid #1e293b', fontSize: '0.85rem' }}>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: 800, color: '#10b981', fontFamily: 'var(--font-mono)' }}>
                      #{t.device_id}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: 700, color: '#f8fafc' }}>
                      {t.name}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: '#94a3b8' }}>
                      {t.breed || '—'}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: '#cbd5e1' }}>
                      {t.location || '—'}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
                      {t.weight ? `${t.weight} kg` : '—'}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: '#94a3b8', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {t.notes || '—'}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button 
                        onClick={() => handleEditTagClick(t)} 
                        title="Edit this node"
                        style={{ background: 'transparent', border: 'none', color: '#38bdf8', cursor: 'pointer', fontSize: '0.95rem', marginRight: '0.85rem' }}
                      >
                        <i className="fa-solid fa-pen"></i>
                      </button>
                      <button 
                        onClick={() => handleDeleteTag(t.device_id)} 
                        title="Delete node tag"
                        style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '0.95rem' }}
                      >
                        <i className="fa-solid fa-trash"></i>
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} style={{ padding: '2rem 1rem', textAlign: 'center', color: '#64748b' }}>
                    <i className="fa-solid fa-tags" style={{ fontSize: '1.5rem', marginBottom: '0.5rem', display: 'block', color: '#475569' }}></i>
                    No custom cow tags registered yet. Add a node above to customize livestock names and barn locations!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
