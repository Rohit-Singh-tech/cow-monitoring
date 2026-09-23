import React, { useState, useEffect } from 'react';

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
    <div className="tag-registry-container">
      
      {/* Header */}
      <div className="tag-registry-header">
        <div>
          <h2 className="tag-registry-title">
            <i className="fa-solid fa-tags" style={{ color: 'var(--accent-emerald)' }}></i>
            Cow Tag Registry
          </h2>
          <div className="tag-registry-subtitle">
            Configure and register cattle metadata for both Gatewayless and Aws telemetry nodes.
          </div>
        </div>
        <div className="tag-registry-badges">
          <span className="registry-pill pill-postgres">
            <i className="fa-solid fa-database"></i>
            PostgreSQL Sync
          </span>
          <span className="registry-pill pill-nodes">
            <i className="fa-solid fa-microchip"></i>
            {tags.length} Nodes Configured
          </span>
        </div>
      </div>

      {message && (
        <div className={`registry-alert ${message.type === 'error' ? 'alert-error' : 'alert-success'}`}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <i className={`fa-solid ${message.type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-check'}`}></i>
            <span>{message.text}</span>
          </div>
          <button onClick={() => setMessage(null)} className="alert-close-btn">
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>
      )}

      {/* NEW NODE / EDIT NODE Form */}
      <div className="glass-panel registry-form-card">
        <div className="registry-card-header">
          <h3 className="registry-form-title">
            <i className={`fa-solid ${isEditing ? 'fa-pen-to-square' : 'fa-circle-plus'}`} style={{ color: isEditing ? 'var(--accent-sky)' : 'var(--accent-purple)' }}></i>
            {isEditing ? `EDIT NODE #${tagDeviceId}` : 'NEW NODE'}
          </h3>
          {isEditing && (
            <button 
              type="button" 
              onClick={handleCancelEdit}
              className="btn-cancel-edit"
            >
              Cancel Edit
            </button>
          )}
        </div>

        <form onSubmit={handleSaveDynamicTag}>
          <div className="registry-form-grid">
            
            {/* DEVICE ID */}
            <div className="form-group-item">
              <label className="form-item-label">DEVICE ID</label>
              <input
                type="text"
                required
                placeholder="100"
                value={tagDeviceId}
                onChange={e => setTagDeviceId(e.target.value)}
                disabled={isEditing}
                className="form-item-input"
              />
            </div>

            {/* SUBJECT NAME */}
            <div className="form-group-item">
              <label className="form-item-label">SUBJECT NAME</label>
              <input
                type="text"
                required
                placeholder="Bovine #100"
                value={tagName}
                onChange={e => setTagName(e.target.value)}
                className="form-item-input"
              />
            </div>

            {/* BREED / TYPE */}
            <div className="form-group-item">
              <label className="form-item-label">BREED / TYPE</label>
              <input
                type="text"
                placeholder="Holstein"
                value={tagBreed}
                onChange={e => setTagBreed(e.target.value)}
                className="form-item-input"
              />
            </div>

            {/* BARN LOCATION */}
            <div className="form-group-item">
              <label className="form-item-label">BARN LOCATION</label>
              <input
                type="text"
                placeholder="Sector A"
                value={tagLocation}
                onChange={e => setTagLocation(e.target.value)}
                className="form-item-input"
              />
            </div>

            {/* WEIGHT */}
            <div className="form-group-item">
              <label className="form-item-label">WEIGHT</label>
              <input
                type="text"
                placeholder="500 kg"
                value={tagWeight}
                onChange={e => setTagWeight(e.target.value)}
                className="form-item-input"
              />
            </div>

            {/* RESEARCH NOTES */}
            <div className="form-group-item">
              <label className="form-item-label">RESEARCH NOTES</label>
              <input
                type="text"
                placeholder="Grazing"
                value={tagNotes}
                onChange={e => setTagNotes(e.target.value)}
                className="form-item-input"
              />
            </div>

          </div>

          {/* Attractive Modern Form Actions Footer */}
          <div className="registry-form-actions">
            {isEditing && (
              <button 
                type="button" 
                onClick={handleCancelEdit}
                className="btn-cancel-edit-action"
              >
                <i className="fa-solid fa-xmark"></i> Cancel Edit
              </button>
            )}
            <button
              type="submit"
              disabled={loading}
              className={`btn-save-node ${isEditing ? 'editing' : ''}`}
            >
              {loading ? (
                <>
                  <i className="fa-solid fa-circle-notch fa-spin"></i>
                  <span>Saving Node...</span>
                </>
              ) : isEditing ? (
                <>
                  <i className="fa-solid fa-check"></i>
                  <span>Update Cattle Node</span>
                </>
              ) : (
                <>
                  <i className="fa-solid fa-plus"></i>
                  <span>Add Cattle Node</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Active Registered Cattle Nodes Table / Cards */}
      <div className="glass-panel registry-table-card">
        <div className="registry-card-header">
          <h3 className="registry-table-title">
            <i className="fa-solid fa-list-check" style={{ color: 'var(--accent-emerald)' }}></i>
            Registered Cattle Nodes
          </h3>
          <span className="registry-table-hint">
            Click edit to load node details into form
          </span>
        </div>
        
        {/* Desktop View: Full Formatted Table */}
        <div className="registry-table-wrapper desktop-only">
          <table className="custom-table registry-table">
            <thead>
              <tr>
                <th>Device ID</th>
                <th>Subject Name</th>
                <th>Breed / Type</th>
                <th>Barn Location</th>
                <th>Weight</th>
                <th>Research Notes</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tags && tags.length > 0 ? (
                tags.map(t => (
                  <tr key={t.id || t.device_id}>
                    <td className="node-id-cell">
                      #{t.device_id}
                    </td>
                    <td className="node-name-cell">
                      {t.name}
                    </td>
                    <td className="node-muted-cell">
                      {t.breed || '—'}
                    </td>
                    <td className="node-location-cell">
                      {t.location || '—'}
                    </td>
                    <td className="node-weight-cell">
                      {t.weight ? (String(t.weight).includes('kg') ? t.weight : `${t.weight} kg`) : '—'}
                    </td>
                    <td className="node-notes-cell">
                      {t.notes || '—'}
                    </td>
                    <td className="node-actions-cell">
                      <button 
                        onClick={() => handleEditTagClick(t)} 
                        title="Edit this node"
                        className="action-btn edit-btn"
                      >
                        <i className="fa-solid fa-pen"></i>
                      </button>
                      <button 
                        onClick={() => handleDeleteTag(t.device_id)} 
                        title="Delete node tag"
                        className="action-btn delete-btn"
                      >
                        <i className="fa-solid fa-trash"></i>
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="registry-empty-cell">
                    <i className="fa-solid fa-tags"></i>
                    No custom cow tags registered yet. Add a node above to customize livestock names and barn locations!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile / Tablet Responsive Cards Grid (No horizontal scroll, 100% details visible) */}
        <div className="registry-cards-grid mobile-only">
          {tags && tags.length > 0 ? (
            tags.map(t => (
              <div key={t.id || t.device_id} className="node-mobile-card">
                <div className="node-mobile-card-top">
                  <div className="node-mobile-id-group">
                    <span className="node-mobile-id-badge">#{t.device_id}</span>
                    <strong className="node-mobile-name">{t.name}</strong>
                  </div>
                  <div className="node-mobile-actions">
                    <button 
                      onClick={() => handleEditTagClick(t)} 
                      title="Edit this node"
                      className="action-btn edit-btn"
                    >
                      <i className="fa-solid fa-pen"></i> Edit
                    </button>
                    <button 
                      onClick={() => handleDeleteTag(t.device_id)} 
                      title="Delete node tag"
                      className="action-btn delete-btn"
                    >
                      <i className="fa-solid fa-trash"></i>
                    </button>
                  </div>
                </div>

                <div className="node-mobile-details-grid">
                  <div className="detail-item">
                    <span className="detail-label">Breed:</span>
                    <span className="detail-val">{t.breed || '—'}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Location:</span>
                    <span className="detail-val">{t.location || '—'}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Weight:</span>
                    <span className="detail-val mono">{t.weight ? (String(t.weight).includes('kg') ? t.weight : `${t.weight} kg`) : '—'}</span>
                  </div>
                  <div className="detail-item full-width">
                    <span className="detail-label">Research Notes:</span>
                    <span className="detail-val notes">{t.notes || 'No notes specified.'}</span>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="registry-empty-card">
              <i className="fa-solid fa-tags"></i>
              <p>No custom cow tags registered yet. Add a node above to customize livestock names and barn locations!</p>
            </div>
          )}
        </div>

      </div>

    </div>
  );
}
