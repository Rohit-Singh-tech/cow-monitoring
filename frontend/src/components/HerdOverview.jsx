import React from 'react';

const ACTIVITY_CLASSES = {
  RES: { code: 'RES', name: 'Resting in standing position', color: '#64748b', icon: 'fa-shoe-prints' },
  RUS: { code: 'RUS', name: 'Ruminating in standing position', color: '#00f3ff', icon: 'fa-arrows-spin' },
  MOV: { code: 'MOV', name: 'Moving / Active', color: '#ffaa00', icon: 'fa-person-walking' },
  FEP: { code: 'FEP', name: 'Feeding in Pot', color: '#39ff14', icon: 'fa-bowl-food' },
  DRN: { code: 'DRN', name: 'Drinking Water', color: '#60a5fa', icon: 'fa-glass-water' },
  LCK: { code: 'LCK', name: 'Licking', color: '#ff00ff', icon: 'fa-hand-sparkles' },
  REL: { code: 'REL', name: 'Resting in lying position', color: '#a78bfa', icon: 'fa-bed' },
  URI: { code: 'URI', name: 'Urinating', color: '#fde047', icon: 'fa-droplet' },
  DEF: { code: 'DEF', name: 'Defecating', color: '#b45309', icon: 'fa-circle-dot' },
  ATT: { code: 'ATT', name: 'Attacking / Aggressive', color: '#ff003c', icon: 'fa-triangle-exclamation' },
  OTH: { code: 'OTH', name: 'Others / Unclassified', color: '#94a3b8', icon: 'fa-question' }
};

export default function HerdOverview({ cows, onSelectCow }) {
  if (!cows || cows.length === 0) return <div className="glass-panel" style={{ padding: '2rem' }}>Loading herd overview...</div>;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--primary-cyan)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>FARM HERD OVERVIEW</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', fontFamily: 'JetBrains Mono' }}>
            REAL-TIME STATUS AND HEALTH OBSERVATIONS ACROSS ALL COLLAR-MOUNTED SENSOR NODES.
          </p>
        </div>
        <div className="status-pill online">
          <i className="fa-solid fa-cow"></i>
          {cows.length} CATTLE MONITORED
        </div>
      </div>
      <div className="grid-herd">
        {cows.map(cow => {
          const act = ACTIVITY_CLASSES[cow.currentActivity] || ACTIVITY_CLASSES.OTH;
          const riskClass = cow.health_risk_decision 
            ? cow.health_risk_decision.toLowerCase().replace('_', '-') 
            : 'healthy';
          
          let borderStyle = {};
          if (riskClass === 'high-risk') borderStyle = { borderColor: 'var(--danger-rose)', boxShadow: '0 0 15px rgba(255,0,60,0.3)' };
          else if (riskClass === 'monitor') borderStyle = { borderColor: 'var(--warning-amber)', boxShadow: '0 0 15px rgba(255,170,0,0.2)' };

          return (
            <div
              key={cow.id}
              className={`glass-panel cow-card health-${riskClass}`}
              style={borderStyle}
            >
              <div>
                <div className="cow-card-top">
                  <div>
                    <div className="cow-card-name">{cow.name}</div>
                    <div className="cow-card-tag">{cow.tagNumber} • {cow.breed}</div>
                  </div>
                  <span className={`health-badge ${cow.health_risk_decision || 'HEALTHY'}`}>
                    {(cow.health_risk_decision || 'HEALTHY').replace('_', ' ')}
                  </span>
                </div>

                <div style={{ margin: '1rem 0' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'JetBrains Mono', letterSpacing: '0.05em' }}>
                    CURRENT ACTIVITY
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.4rem' }}>
                    <span className="code-badge" style={{ background: `${act.color}22`, color: act.color, border: `1px solid ${act.color}55` }}>
                      <i className={`fa-solid ${act.icon}`}></i> {act.name}
                    </span>
                  </div>
                </div>
                <div className="cow-card-vitals" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                  <div>
                    <div className="vital-item-lbl">RUMINATION</div>
                    <div className="vital-item-val" style={{ color: 'var(--primary-cyan)' }}>{cow.ruminationHoursToday} <span style={{fontSize: '0.7rem'}}>hrs</span></div>
                  </div>
                  <div>
                    <div className="vital-item-lbl">LYING REST</div>
                    <div className="vital-item-val" style={{ color: 'var(--accent-magenta)' }}>{cow.lyingHoursToday} <span style={{fontSize: '0.7rem'}}>hrs</span></div>
                  </div>
                  <div>
                    <div className="vital-item-lbl">HEAT INDEX</div>
                    <div className="vital-item-val" style={{ color: cow.estrusProbability > 50 ? 'var(--danger-rose)' : 'var(--text-main)' }}>{cow.estrusProbability}%</div>
                  </div>
                </div>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => onSelectCow(cow.id)} style={{ width: '100%', marginTop: '1rem' }}>
                <i className="fa-solid fa-eye"></i> VIEW LIVE DASHBOARD
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
