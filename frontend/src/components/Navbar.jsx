import React from 'react';

export default function Navbar({ cows, currentCowId, onSelectCow, onTriggerDump }) {
  const alertCount = cows.filter(c => c.healthStatus !== 'HEALTHY').length;

  return (
    <header class="navbar">
      <div class="brand-section" style={{ gap: '1rem' }}>
        <i class="fa-solid fa-bars" style={{ color: 'var(--text-muted)', fontSize: '1.25rem', cursor: 'pointer' }}></i>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>Dashboard Overview</h2>
      </div>

      <div class="header-controls">
        <div class="cow-select-wrapper">
          <i class="fa-solid fa-cow" style={{ color: 'var(--primary-emerald)' }}></i>
          <span class="cow-select-label">Select Cow:</span>
          <select
            class="cow-select"
            value={currentCowId}
            onChange={(e) => onSelectCow(e.target.value)}
          >
            {cows.map((c) => (
              <option key={c.id} value={c.id}>
                Cow #{c.id} - {c.name} ({c.healthStatus === 'ESTRUS_ALERT' ? 'HEAT ALERT ⚡' : 'Healthy 🟢'})
              </option>
            ))}
          </select>
        </div>

        <div class="status-pill online" style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.2)', padding: '0.4rem 1rem' }}>
          <span class="pulse-dot"></span>
          BLE LIVE
        </div>

        <div style={{ color: 'var(--text-muted)', fontFamily: 'JetBrains Mono', fontSize: '0.85rem' }}>
          {new Date().toLocaleTimeString('en-US', { hour12: false })}
        </div>

        <div class="status-pill" style={{ background: alertCount > 0 ? 'rgba(244,63,94,0.1)' : 'rgba(16,185,129,0.1)', color: alertCount > 0 ? 'var(--danger-rose)' : 'var(--primary-emerald)', border: `1px solid ${alertCount > 0 ? 'rgba(244,63,94,0.2)' : 'rgba(16,185,129,0.2)'}`, padding: '0.4rem 1rem' }}>
          {alertCount} Alert{alertCount !== 1 ? 's' : ''}
        </div>

        <a
          href={`/api/export/csv?cowId=${currentCowId}`}
          class="btn btn-secondary"
          target="_blank"
          rel="noreferrer"
        >
          <i class="fa-solid fa-file-csv"></i>
          Export CSV
        </a>
      </div>
    </header>
  );
}
