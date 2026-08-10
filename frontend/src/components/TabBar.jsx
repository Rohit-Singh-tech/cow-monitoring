import React from 'react';

export default function TabBar({ activeTab, onSelectTab }) {
  const tabs = [
    { id: 'live', label: 'Dashboard', icon: 'fa-chart-pie' },
    { id: '7day', label: 'Anomaly Log', icon: 'fa-triangle-exclamation' },
    { id: 'herd', label: 'Animals', icon: 'fa-border-all' },
    { id: 'hardware', label: 'BLE Node & Hardware Specs', icon: 'fa-microchip' },
    { id: 'docs', label: 'IIT Ropar Project Report', icon: 'fa-file-contract' }
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
    </nav>
  );
}
