import React, { useState, useRef, useEffect } from 'react';
import { formatHours } from '../utils';

export default function Navbar({ cows, currentCowId, onSelectCow, onTriggerDump, onToggleMenu, isSidebarOpen, theme, onToggleTheme }) {
  const [showDropdown, setShowDropdown] = useState(false);

  // Close popup on Escape key
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        setShowDropdown(false);
      }
    }
    if (showDropdown) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showDropdown]);

  const alertingCows = cows.filter(c => c.health_risk_decision === 'HIGH_RISK' || c.healthStatus === 'ESTRUS_ALERT');
  const alertCount = alertingCows.length;

  return (
    <>
      <header className="navbar">
        <div className="navbar-brand-area">
          <button
            onClick={onToggleMenu}
            className="navbar-toggle-btn"
            title="Toggle Navigation Menu"
          >
            <i className="fa-solid fa-bars-staggered"></i>
          </button>
          <h2 className="navbar-title">
            SYSTEM OVERVIEW
          </h2>
        </div>

        <div className="header-controls">
          {/* Node Selector */}
          <div className="cow-select-wrapper">
            <i className="fa-solid fa-microchip" style={{ color: 'var(--accent-emerald)', fontSize: '0.8rem' }}></i>
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

          {/* Live Uplink Status */}
          <div className="status-pill online">
            <span className="pulse-dot"></span>
            CONNECTED
          </div>

          {/* Live Monospace Clock */}
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 700, fontFamily: 'var(--font-mono)', padding: '0 0.15rem' }}>
            {new Date().toLocaleTimeString('en-US', { hour12: false })}
          </div>

          {/* Theme Toggle */}
          <button
            onClick={onToggleTheme}
            className="navbar-icon-btn"
            title="Toggle Dark / Light Theme"
          >
            <i className={theme === 'light' ? "fa-solid fa-moon" : "fa-solid fa-sun"} style={{ color: theme === 'light' ? '#7C3AED' : '#FBBF24' }}></i>
          </button>

          {/* Alerts Trigger Button */}
          <button
            className={`status-pill ${alertCount > 0 ? 'critical' : 'online'}`}
            style={{ cursor: alertCount > 0 ? 'pointer' : 'default', outline: 'none' }}
            onClick={() => { if (alertCount > 0) setShowDropdown(!showDropdown); }}
            title={alertCount > 0 ? "Click to view active health alerts" : "All herd members healthy"}
          >
            <i className={alertCount > 0 ? "fa-solid fa-triangle-exclamation" : "fa-solid fa-circle-check"}></i>
            {alertCount > 0 ? `${alertCount} ALERT${alertCount !== 1 ? 'S' : ''}` : 'ALL HEALTHY'}
          </button>

          {/* DUMP LOGS CSV Button */}
          <a
            href={`/api/export/csv?cowId=${currentCowId}`}
            className="btn btn-secondary"
            target="_blank"
            rel="noreferrer"
          >
            <i className="fa-solid fa-file-arrow-down"></i>
            DUMP LOGS
          </a>
        </div>
      </header>

      {/* Floating Modal / Popover for Alerts (Rendered outside navbar overflow) */}
      {showDropdown && alertCount > 0 && (
        <div className="alerts-popover-backdrop" onClick={() => setShowDropdown(false)}>
          <div 
            className="alerts-popover-card" 
            onClick={(e) => e.stopPropagation()}
          >
            <div className="alerts-popover-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span className="pulse-dot" style={{ color: '#EF4444' }}></span>
                <i className="fa-solid fa-triangle-exclamation" style={{ color: '#EF4444', fontSize: '1rem' }}></i>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 800, margin: 0, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                  ACTIVE HERD HEALTH ALERTS ({alertCount})
                </h3>
              </div>
              <button 
                className="alerts-close-btn"
                onClick={() => setShowDropdown(false)}
                title="Close Alerts"
              >
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>

            <div className="alerts-popover-body">
              {alertingCows.map(c => {
                const isSelected = String(c.id) === String(currentCowId);
                return (
                  <div key={c.id} className={`alert-item-card ${isSelected ? 'selected' : ''}`}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                        <div className="alert-item-avatar">
                          <i className="fa-solid fa-cow" style={{ color: '#EF4444', fontSize: '1.1rem' }}></i>
                        </div>
                        <div>
                          <h4 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                            {c.name} <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 600 }}>({c.tagNumber || `TAG-${c.device_id}`})</span>
                          </h4>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginTop: '0.2rem' }}>
                            <span className="meta-chip" style={{ fontSize: '0.675rem', padding: '0.15rem 0.45rem' }}>
                              Node #{c.device_id}
                            </span>
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                              {c.breed || 'Gir / Sahiwal'}
                            </span>
                          </div>
                        </div>
                      </div>

                      <span className="health-badge HIGH_RISK" style={{ fontSize: '0.65rem', padding: '0.2rem 0.55rem' }}>
                        {(c.health_risk_decision || 'HIGH_RISK').replace('_', ' ')}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.65rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border-subtle)' }}>
                      <div style={{ fontSize: '0.725rem', color: '#FFA4A4', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                        <i className="fa-solid fa-temperature-arrow-up" style={{ marginRight: '0.3rem' }}></i>
                        Estrus: {c.estrusProbability || 91}% | Rum: {formatHours(c.ruminationHoursToday)}
                      </div>
                      <button
                        className="btn btn-primary"
                        style={{ height: '28px', padding: '0 0.75rem', fontSize: '0.725rem' }}
                        onClick={() => {
                          onSelectCow(c.id);
                          setShowDropdown(false);
                        }}
                      >
                        <i className="fa-solid fa-crosshairs"></i>
                        {isSelected ? 'CURRENTLY VIEWING' : 'FOCUS NODE'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
