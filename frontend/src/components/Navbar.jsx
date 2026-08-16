import React, { useState, useRef, useEffect } from 'react';

export default function Navbar({ cows, currentCowId, onSelectCow, onTriggerDump, onToggleMenu }) {
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef(null);
  
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    }
    if (showDropdown) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showDropdown]);
  
  const alertingCows = cows.filter(c => c.health_risk_decision === 'HIGH_RISK' || c.healthStatus === 'ESTRUS_ALERT');
  const alertCount = alertingCows.length;

  return (
    <header className="navbar">
      <div className="brand-section" style={{ gap: '1rem' }}>
        <i className="fa-solid fa-bars" onClick={onToggleMenu} style={{ color: 'var(--primary-cyan)', fontSize: '1.25rem', cursor: 'pointer' }}></i>
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

        <div style={{ position: 'relative' }} ref={dropdownRef}>
          <button 
            className="status-pill" 
            style={{ 
              background: alertCount > 0 ? 'rgba(255,0,60,0.15)' : 'rgba(16,185,129,0.1)', 
              color: alertCount > 0 ? 'var(--danger-rose)' : 'var(--primary-emerald)', 
              border: `1px solid ${alertCount > 0 ? 'rgba(255,0,60,0.5)' : 'rgba(16,185,129,0.5)'}`, 
              padding: '0.4rem 1rem', 
              boxShadow: alertCount > 0 ? '0 0 10px rgba(255,0,60,0.3)' : 'none',
              cursor: alertCount > 0 ? 'pointer' : 'default',
              outline: 'none'
            }}
            onClick={() => { if(alertCount > 0) setShowDropdown(!showDropdown); }}
          >
            {alertCount} CRITICAL ALERT{alertCount !== 1 ? 'S' : ''}
          </button>
          
          {showDropdown && alertCount > 0 && (
            <div className="glass-panel" style={{ 
              position: 'absolute', 
              top: '130%', 
              right: 0, 
              width: '320px', 
              maxHeight: '60vh',
              overflowY: 'auto',
              zIndex: 200,
              padding: '1.25rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
              border: '1px solid var(--danger-rose)',
              boxShadow: '0 0 25px rgba(255,0,60,0.4)',
              background: 'rgba(10, 5, 5, 0.95)'
            }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: 'var(--danger-rose)', borderBottom: '1px solid rgba(255,0,60,0.3)', paddingBottom: '0.5rem', marginBottom: '0.25rem', fontFamily: 'Orbitron', position: 'sticky', top: 0, background: 'rgba(10, 5, 5, 0.95)', zIndex: 1 }}>
                <i className="fa-solid fa-triangle-exclamation" style={{ marginRight: '0.5rem' }}></i> ACTIVE ALERTS LOG
              </div>
              {alertingCows.map(c => (
                <div key={c.id} style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', background: 'rgba(255,0,60,0.05)', padding: '0.75rem', borderLeft: '2px solid var(--danger-rose)' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff', fontFamily: 'Rajdhani', letterSpacing: '0.05em' }}>
                    NODE #{c.device_id} ({c.name})
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
                    <span style={{ color: 'var(--danger-rose)' }}>[DETECTED]</span> {(c.health_risk_decision || 'HIGH_RISK').replace('_', ' ')}
                  </div>
                  <button 
                    className="btn btn-secondary" 
                    style={{ padding: '0.35rem 0.5rem', fontSize: '0.7rem', marginTop: '0.25rem', width: '100%', justifyContent: 'center' }}
                    onClick={() => { onSelectCow(c.id); setShowDropdown(false); }}
                  >
                    <i className="fa-solid fa-crosshairs"></i> FOCUS ON NODE
                  </button>
                </div>
              ))}
            </div>
          )}
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
