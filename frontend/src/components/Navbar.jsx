import React from 'react';

export default function Navbar({ cows, currentCowId, onSelectCow, onTriggerDump }) {
  const alertCount = cows.filter(c => c.health_risk_decision === 'HIGH_RISK' || c.healthStatus === 'ESTRUS_ALERT').length;

  return (
    <header className="navbar">
      <div className="brand-section" style={{ gap: '1rem' }}>
        <i className="fa-solid fa-bars" style={{ color: 'var(--primary-cyan)', fontSize: '1.25rem', cursor: 'pointer' }}></i>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 800, margin: 0, fontFamily: 'Rajdhani', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--primary-cyan)' }}>
          SYSTEM OVERVIEW
        </h2>
      </div>

      <div className="header-controls">
        <div className="cow-select-wrapper">
          <i className="fa-solid fa-satellite-dish" style={{ color: 'var(--primary-emerald)' }}></i>
          <span className="cow-select-label">TARGET NODE:</span>
          <select
            className="cow-select"
            value={currentCowId}
            onChange={(e) => onSelectCow(e.target.value)}
          >
            {cows.map((c) => (
              <option key={c.id} value={c.id}>
                NODE #{c.device_id} - {c.name} [{(c.health_risk_decision || 'HEALTHY').replace('_', ' ')}]
              </option>
            ))}
          </select>
        </div>

        <div className="status-pill online" style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.5)', padding: '0.4rem 1rem' }}>
          <span className="pulse-dot"></span>
          UPLINK ACTIVE
        </div>

        <div style={{ color: 'var(--primary-cyan)', fontFamily: 'JetBrains Mono', fontSize: '0.85rem', fontWeight: 700 }}>
          T-MINUS {new Date().toLocaleTimeString('en-US', { hour12: false })}
        </div>

        <div className="status-pill" style={{ background: alertCount > 0 ? 'rgba(255,0,60,0.15)' : 'rgba(16,185,129,0.1)', color: alertCount > 0 ? 'var(--danger-rose)' : 'var(--primary-emerald)', border: `1px solid ${alertCount > 0 ? 'rgba(255,0,60,0.5)' : 'rgba(16,185,129,0.5)'}`, padding: '0.4rem 1rem', boxShadow: alertCount > 0 ? '0 0 10px rgba(255,0,60,0.3)' : 'none' }}>
          {alertCount} CRITICAL ALERT{alertCount !== 1 ? 'S' : ''}
        </div>

        <a
          href={`/api/export/csv?cowId=${currentCowId}`}
          className="btn btn-secondary"
          target="_blank"
          rel="noreferrer"
        >
          <i className="fa-solid fa-download"></i>
          DUMP LOGS
        </a>
      </div>
    </header>
  );
}
