import React from 'react';

export default function TabBar({ activeTab, onSelectTab, onLogout }) {
  const tabs = [
    { id: 'live', icon: 'fa-satellite', label: 'SYS DIAGNOSTICS' },
    { id: '7day', icon: 'fa-chart-network', label: '7-DAY LOGS' },
    { id: 'herd', icon: 'fa-list-ul', label: 'NODE DIRECTORY' },
    { id: 'hardware', icon: 'fa-microchip', label: 'HARDWARE SPECS' },
    { id: 'docs', icon: 'fa-folder-open', label: 'ARCHIVES' },
    { id: 'admin', icon: 'fa-terminal', label: 'ROOT ACCESS' }
  ];

  return (
    <nav className="tab-bar">
      {/* Brand Section in Sidebar */}
      <div className="brand-section" style={{ padding: '0.5rem 0 1.5rem 0', borderBottom: '1px solid var(--border-glass)', marginBottom: '1.5rem', gap: '1rem', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
        <div className="brand-logo" style={{ 
          background: 'linear-gradient(135deg, var(--primary-cyan), var(--accent-magenta))', 
          color: '#000', 
          boxShadow: '0 0 20px rgba(0, 243, 255, 0.5)', 
          borderRadius: '2px',
          width: '50px',
          height: '50px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '1.5rem'
        }}>
          <i className="fa-solid fa-cow"></i>
        </div>
        <div>
          <h1 className="brand-title" style={{ fontSize: '1.4rem', fontWeight: 800, fontFamily: 'Rajdhani', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--primary-cyan)', margin: '0' }}>NEURAL HERD</h1>
          <div className="brand-subtitle" style={{ fontSize: '0.65rem', fontFamily: 'JetBrains Mono', color: 'var(--text-muted)', marginTop: '0.2rem' }}>EDGE-COMPUTING PROTOCOL</div>
        </div>
      </div>

      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onSelectTab(tab.id)}
        >
          <i className={`fa-solid ${tab.icon}`}></i>
          {tab.label}
        </button>
      ))}

      {/* Logout Button */}
      <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid var(--border-glass)' }}>
        <button 
          className="tab-btn" 
          onClick={onLogout}
          style={{ width: '100%', justifyContent: 'center', background: 'rgba(255, 0, 60, 0.1)', color: 'var(--danger-rose)', border: '1px solid rgba(255, 0, 60, 0.3)' }}
        >
          <i className="fa-solid fa-power-off" style={{ marginRight: '0.5rem' }}></i>
          DISCONNECT
        </button>
      </div>
    </nav>
  );
}
