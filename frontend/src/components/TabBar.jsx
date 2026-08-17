import React from 'react';

export default function TabBar({ activeTab, onSelectTab, onLogout, isOpen, onClose }) {
  const tabs = [
    { id: 'live', icon: 'fa-heart-pulse', label: 'SYS DIAGNOSTICS' },
    { id: '7day', icon: 'fa-calendar-week', label: '7-DAY LOGS' },
    { id: 'herd', icon: 'fa-cow', label: 'NODE DIRECTORY' },
    { id: 'hardware', icon: 'fa-microchip', label: 'HARDWARE SPECS' },
    { id: 'docs', icon: 'fa-book-open', label: 'ARCHIVES' }
  ];

  return (
    <>
      <div className={`sidebar-overlay ${isOpen ? 'open' : ''}`} onClick={onClose}></div>
      <nav className={`tab-bar ${isOpen ? 'open' : 'closed'}`}>
        {/* Brand Section */}
        <div className="brand-section">
          <div className="brand-logo">
            <img src="/cow-logo.png" alt="Cow Logo" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
          </div>
          <div className="brand-text-container">
            <div className="brand-title">Cow Health Monitoring</div>
            <div className="brand-subtitle">Gatewayless Monitoring System</div>
          </div>
        </div>

        {/* Navigation Items */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          <div style={{ fontSize: '0.675rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em', padding: '0.5rem 0.75rem 0.25rem', fontFamily: 'var(--font-mono)' }}>
            Farm Navigation
          </div>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => onSelectTab(tab.id)}
            >
              <i className={`fa-solid ${tab.icon}`}></i>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Bottom Disconnect */}
        <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)' }}>
          <button 
            className="tab-btn" 
            onClick={onLogout}
            style={{ width: '100%', color: 'var(--accent-rose)' }}
          >
            <i className="fa-solid fa-power-off" style={{ color: 'var(--accent-rose)' }}></i>
            <span>DISCONNECT</span>
          </button>
        </div>
      </nav>
    </>
  );
}
