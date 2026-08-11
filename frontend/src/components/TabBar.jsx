import React from 'react';

export default function TabBar({ activeTab, onSelectTab, onLogout }) {
  const tabs = [
    { id: 'live', icon: 'fa-heart-pulse', label: 'Live Vitals' },
    { id: '7day', icon: 'fa-chart-line', label: '7-Day Activity' },
    { id: 'herd', icon: 'fa-list', label: 'Herd Overview' },
    { id: 'hardware', icon: 'fa-microchip', label: 'Hardware Specs' },
    { id: 'docs', icon: 'fa-file-lines', label: 'Project Docs' },
    { id: 'admin', icon: 'fa-user-shield', label: 'Admin Panel' }
  ];

  return (
    <nav class="tab-bar">
      {/* Brand Section in Sidebar */}
      <div class="brand-section" style={{ padding: '0.5rem 0 1.5rem 0', borderBottom: '1px solid var(--border-glass)', marginBottom: '0.5rem', gap: '0.8rem' }}>
        <div class="brand-logo" style={{ background: 'linear-gradient(135deg, var(--primary-emerald), var(--primary-cyan))', color: '#070a12', boxShadow: '0 0 15px rgba(16,185,129,0.4)', borderRadius: '8px' }}>
          <i class="fa-solid fa-cow"></i>
        </div>
        <div>
          <h1 class="brand-title" style={{ fontSize: '1.2rem', fontWeight: 800 }}>Cow Logger</h1>
          <div class="brand-subtitle" style={{ fontSize: '0.65rem' }}>Gatewayless cow monitoring system</div>
        </div>
      </div>

      {tabs.map((tab) => (
        <button
          key={tab.id}
          class={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onSelectTab(tab.id)}
        >
          <i class={`fa-solid ${tab.icon}`}></i>
          {tab.label}
        </button>
      ))}

      {/* Logout Button */}
      <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid var(--border-glass)' }}>
        <button 
          className="tab-btn" 
          onClick={onLogout}
          style={{ width: '100%', justifyContent: 'center', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)' }}
        >
          <i className="fa-solid fa-arrow-right-from-bracket" style={{ marginRight: '0.5rem' }}></i>
          Logout
        </button>
      </div>
    </nav>
  );
}
