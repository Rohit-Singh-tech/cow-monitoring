import React from 'react';

export default function TabBar({ activeTab, onSelectTab, onLogout, isOpen, onClose }) {
  const tabs = [
    { id: 'live', icon: 'fa-satellite', label: 'SYS DIAGNOSTICS' },
    { id: '7day', icon: 'fa-chart-network', label: '7-DAY LOGS' },
    { id: 'herd', icon: 'fa-list-ul', label: 'NODE DIRECTORY' },
    { id: 'hardware', icon: 'fa-microchip', label: 'HARDWARE SPECS' },
    { id: 'docs', icon: 'fa-folder-open', label: 'ARCHIVES' }
  ];

  return (
    <>
      <div className={`sidebar-overlay ${isOpen ? 'open' : ''}`} onClick={onClose}></div>
      <nav className={`tab-bar ${isOpen ? 'open' : ''}`}>
      {/* Brand Section in Sidebar */}
      <div className="brand-section" style={{ padding: '0.5rem 0 1.5rem 0', borderBottom: '1px solid var(--border-glass)', marginBottom: '1.5rem', gap: '1rem', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
        <div className="brand-logo" style={{ 
          width: '80px',
          height: '80px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <img src="/cow-logo.png" alt="Cyber Cow Logo" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
        </div>
        <div>
          <h1 className="brand-title" style={{ fontSize: '1.2rem', fontWeight: 800, fontFamily: 'Rajdhani', letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--primary-cyan)', margin: '0', lineHeight: '1.2' }}>Cow Health<br/>Monitoring</h1>
          <div className="brand-subtitle" style={{ fontSize: '0.65rem', fontFamily: 'JetBrains Mono', color: 'var(--text-muted)', marginTop: '0.5rem', lineHeight: '1.2' }}>GATEWAYLESS<br/>MONITORING SYSTEM</div>
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
    </>
  );
}
