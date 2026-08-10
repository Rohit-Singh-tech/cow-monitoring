import React from 'react';

const ACTIVITY_CLASSES = {
  RES: { code: 'RES', name: 'Resting in standing position', color: '#64748b', icon: 'fa-shoe-prints' },
  RUS: { code: 'RUS', name: 'Ruminating in standing position', color: '#06b6d4', icon: 'fa-arrows-spin' },
  MOV: { code: 'MOV', name: 'Moving / Active', color: '#f59e0b', icon: 'fa-person-walking' },
  FEP: { code: 'FEP', name: 'Feeding in Pot', color: '#10b981', icon: 'fa-bowl-food' },
  DRN: { code: 'DRN', name: 'Drinking Water', color: '#3b82f6', icon: 'fa-glass-water' },
  LCK: { code: 'LCK', name: 'Licking', color: '#ec4899', icon: 'fa-hand-sparkles' },
  REL: { code: 'REL', name: 'Resting in lying position', color: '#8b5cf6', icon: 'fa-bed' },
  URI: { code: 'URI', name: 'Urinating', color: '#eab308', icon: 'fa-droplet' },
  DEF: { code: 'DEF', name: 'Defecating', color: '#a16207', icon: 'fa-circle-dot' },
  ATT: { code: 'ATT', name: 'Attacking / Aggressive', color: '#ef4444', icon: 'fa-triangle-exclamation' },
  OTH: { code: 'OTH', name: 'Others / Unclassified', color: '#94a3b8', icon: 'fa-question' }
};

export default function HerdOverview({ cows, onSelectCow }) {
  if (!cows || cows.length === 0) return <div className="glass-panel" style={{ padding: '2rem' }}>Loading herd overview...</div>;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800 }}>Farm Herd Overview</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            Real-time status and health observations across all collar-mounted sensor nodes.
          </p>
        </div>
        <div className="status-pill online">
          <i className="fa-solid fa-cow"></i>
          {cows.length} Cattle Monitored
        </div>
      </div>
      <div className="grid-herd">
        {cows.map(cow => {
          const act = ACTIVITY_CLASSES[cow.currentActivity] || ACTIVITY_CLASSES.OTH;
          const isHeat = cow.healthStatus === 'ESTRUS_ALERT';

          return (
            <div
              key={cow.id}
              className="glass-panel cow-card"
              style={isHeat ? { borderColor: 'rgba(245, 158, 11, 0.5)' } : {}}
            >
              <div>
                <div className="cow-card-top">
                  <div>
                    <div className="cow-card-name">{cow.name}</div>
                    <div className="cow-card-tag">{cow.tagNumber} • {cow.breed}</div>
                  </div>
                  <span className={`status-pill ${isHeat ? 'ble' : 'online'}`}>
                    {isHeat ? '⚡ HEAT ALERT' : '🟢 Healthy'}
                  </span>
                </div>

                <div style={{ margin: '0.75rem 0' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    Current Activity
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.2rem' }}>
                    <span className="code-badge" style={{ background: `${act.color}33`, color: act.color }}>
                      <i className={`fa-solid ${act.icon}`}></i> {act.name}
                    </span>
                  </div>
                </div>
                <div className="cow-card-vitals" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                  <div>
                    <div className="vital-item-lbl">Rumination:</div>
                    <div className="vital-item-val" style={{ color: 'var(--primary-cyan)' }}>{cow.ruminationHoursToday} hrs</div>
                  </div>
                  <div>
                    <div className="vital-item-lbl">Lying Rest:</div>
                    <div className="vital-item-val" style={{ color: 'var(--accent-purple)' }}>{cow.lyingHoursToday} hrs</div>
                  </div>
                  <div>
                    <div className="vital-item-lbl">Heat Index:</div>
                    <div className="vital-item-val" style={{ color: isHeat ? 'var(--warning-amber)' : 'var(--text-main)' }}>{cow.estrusProbability}%</div>
                  </div>
                </div>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => onSelectCow(cow.id)} style={{ width: '100%', marginTop: '0.5rem' }}>
                <i className="fa-solid fa-eye"></i> View Live Dashboard
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
