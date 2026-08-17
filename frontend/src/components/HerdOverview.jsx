import React, { useState } from 'react';

const ACTIVITY_CLASSES = {
  RES: { code: 'RES', name: 'Resting in standing position', color: '#64748B', icon: 'fa-pause' },
  RUS: { code: 'RUS', name: 'Ruminating in standing position', color: '#06B6D4', icon: 'fa-arrows-spin' },
  MOV: { code: 'MOV', name: 'Moving / Active', color: '#F59E0B', icon: 'fa-person-walking' },
  FEP: { code: 'FEP', name: 'Feeding in Pot', color: '#10B981', icon: 'fa-bowl-food' },
  FED: { code: 'FED', name: 'Feeding', color: '#10B981', icon: 'fa-bowl-food' },
  GRZ: { code: 'GRZ', name: 'Grazing Field', color: '#10B981', icon: 'fa-wheat-awn' },
  DRN: { code: 'DRN', name: 'Drinking Water', color: '#0EA5E9', icon: 'fa-glass-water' },
  LCK: { code: 'LCK', name: 'Licking', color: '#EC4899', icon: 'fa-hand-sparkles' },
  REL: { code: 'REL', name: 'Resting in lying position', color: '#8B5CF6', icon: 'fa-bed' },
  URI: { code: 'URI', name: 'Urinating', color: '#FDE047', icon: 'fa-droplet' },
  DEF: { code: 'DEF', name: 'Defecating', color: '#FB923C', icon: 'fa-circle-dot' },
  ATT: { code: 'ATT', name: 'Attacking / Aggressive', color: '#EF4444', icon: 'fa-triangle-exclamation' },
  OTH: { code: 'OTH', name: 'Others / Unclassified', color: '#94A3B8', icon: 'fa-question' },
  UNKNOWN: { code: 'ACT', name: 'Active Normal', color: '#64748B', icon: 'fa-wave-square' }
};

export default function HerdOverview({ cows, onSelectCow }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [healthFilter, setHealthFilter] = useState('ALL');

  if (!cows || cows.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '3rem 2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '2rem', color: 'var(--accent-emerald)', marginBottom: '0.75rem', display: 'block' }}></i>
        <h3 style={{ color: 'var(--text-primary)', fontWeight: 800 }}>LOADING HERD REGISTRY...</h3>
      </div>
    );
  }

  const filteredCows = cows.filter(cow => {
    const matchesSearch = 
      cow.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      cow.tagNumber.toLowerCase().includes(searchTerm.toLowerCase()) ||
      String(cow.device_id).includes(searchTerm) ||
      (cow.breed && cow.breed.toLowerCase().includes(searchTerm.toLowerCase()));

    const status = cow.health_risk_decision || 'HEALTHY';
    const matchesHealth = healthFilter === 'ALL' || status === healthFilter;

    return matchesSearch && matchesHealth;
  });

  return (
    <div>
      {/* Header & Filter Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', fontFamily: 'var(--font-display)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <i className="fa-solid fa-cow" style={{ color: 'var(--accent-emerald)' }}></i>
            NODE DIRECTORY & CATTLE HERD REGISTRY
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.825rem', marginTop: '0.15rem' }}>
            Real-time status across all collar-mounted IoT BLE sensor nodes (AWaDH IIT Ropar).
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
          <input 
            type="text"
            placeholder="Search cow name, tag, node..."
            className="search-input-box"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ width: '220px' }}
          />

          <select
            className="search-input-box"
            value={healthFilter}
            onChange={(e) => setHealthFilter(e.target.value)}
          >
            <option value="ALL">All Health States</option>
            <option value="HEALTHY">🟢 Healthy</option>
            <option value="MONITOR">🟡 Monitor</option>
            <option value="HIGH_RISK">🔴 High Risk</option>
            <option value="ESTRUS_ALERT">🔥 Estrus Alert</option>
          </select>

          <div className="status-pill online">
            <i className="fa-solid fa-microchip"></i>
            {cows.length} ACTIVE NODES
          </div>
        </div>
      </div>

      {/* Grid of Cattle Node Cards */}
      <div className="grid-herd">
        {filteredCows && filteredCows.length > 0 ? (
          filteredCows.map(cow => {
            const act = ACTIVITY_CLASSES[cow.currentActivity] || ACTIVITY_CLASSES.OTH;
            const isCritical = cow.health_risk_decision === 'HIGH_RISK' || cow.health_risk_decision === 'ESTRUS_ALERT';

            return (
              <div
                key={cow.id}
                className="cow-card"
                style={{
                  border: isCritical ? '1px solid #EF4444' : '1px solid var(--border-subtle)'
                }}
              >
                <div>
                  <div className="cow-card-top">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(6, 182, 212, 0.2) 100%)', border: '1px solid rgba(52, 211, 153, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '3px', flexShrink: 0 }}>
                        <img src="/cow-logo.png" alt="Cow" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                      </div>
                      <div>
                        <div className="cow-card-name">
                          #{cow.device_id} - {cow.name}
                        </div>
                        <div className="cow-card-tag">TAG: <strong style={{ color: 'var(--text-primary)' }}>{cow.tagNumber}</strong> • {cow.breed || 'Gir / Sahiwal'}</div>
                      </div>
                    </div>

                    <span className={`health-badge ${cow.health_risk_decision || 'HEALTHY'}`}>
                      {(cow.health_risk_decision || 'HEALTHY').replace('_', ' ')}
                    </span>
                  </div>

                  <div style={{ margin: '0.9rem 0' }}>
                    <div style={{ fontSize: '0.675rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 800, letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>
                      CURRENT INFERRED STATE
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginTop: '0.35rem' }}>
                      <span className="code-badge" style={{ background: `${act.color}20`, color: act.color, border: `1px solid ${act.color}50`, display: 'inline-flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.75rem', fontWeight: 700 }}>
                        <i className={`fa-solid ${act.icon}`}></i> {act.name}
                      </span>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.45rem', padding: '0.75rem', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                    <div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Rumination</div>
                      <div style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--accent-sky)', marginTop: '0.1rem', fontFamily: 'var(--font-display)' }}>
                        {cow.ruminationHoursToday} <span style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-muted)' }}>hrs</span>
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Lying Rest</div>
                      <div style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--accent-purple)', marginTop: '0.1rem', fontFamily: 'var(--font-display)' }}>
                        {cow.lyingHoursToday} <span style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-muted)' }}>hrs</span>
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Estrus Prob</div>
                      <div style={{ fontSize: '1rem', fontWeight: 800, color: cow.estrusProbability > 50 ? 'var(--accent-rose)' : 'var(--accent-emerald)', marginTop: '0.1rem', fontFamily: 'var(--font-display)' }}>
                        {cow.estrusProbability}%
                      </div>
                    </div>
                  </div>
                </div>

                <button 
                  className="btn btn-primary" 
                  onClick={() => onSelectCow(cow.id)} 
                  style={{ width: '100%', justifyContent: 'center', height: '36px' }}
                >
                  <i className="fa-solid fa-crosshairs"></i> MONITOR NODE TELEMETRY
                </button>
              </div>
            );
          })
        ) : (
          <div className="glass-panel" style={{ gridColumn: '1 / -1', padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            No cattle nodes found matching the search criteria.
          </div>
        )}
      </div>
    </div>
  );
}
