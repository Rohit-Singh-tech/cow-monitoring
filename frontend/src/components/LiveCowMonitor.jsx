import React, { useEffect, useRef } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
} from 'chart.js';
import { Line, Doughnut } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

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

export default function LiveCowMonitor({ currentData, accelBuffer }) {
  if (!currentData) return <div className="glass-panel" style={{ padding: '2rem' }}>INITIALIZING NEURAL LINK...</div>;

  const act = currentData.currentActivity || {};
  const health = currentData.healthStatus || {};
  const ml = currentData.ml_inference || {};
  
  const riskClass = health.health_risk_decision 
    ? health.health_risk_decision.toLowerCase().replace('_', '-') 
    : 'healthy';

  // Live Accelerometer Line Chart Config
  const accelChartData = {
    labels: accelBuffer.labels,
    datasets: [
      { label: 'X-Axis', data: accelBuffer.x, borderColor: '#ff003c', borderWidth: 2, pointRadius: 0, tension: 0.3 },
      { label: 'Y-Axis', data: accelBuffer.y, borderColor: '#39ff14', borderWidth: 2, pointRadius: 0, tension: 0.3 },
      { label: 'Z-Axis', data: accelBuffer.z, borderColor: '#00f3ff', borderWidth: 2, pointRadius: 0, tension: 0.3 },
      { label: 'Magnitude |a|', data: accelBuffer.mag, borderColor: '#ffaa00', borderWidth: 1.5, borderDash: [4, 4], pointRadius: 0, tension: 0.3 }
    ]
  };

  const accelChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      x: { display: true, grid: { color: 'rgba(0, 243, 255, 0.1)' }, ticks: { color: '#00f3ff', font: { family: 'JetBrains Mono', size: 10 } } },
      y: { grid: { color: 'rgba(0, 243, 255, 0.15)' }, ticks: { color: '#00f3ff', font: { family: 'JetBrains Mono', size: 10 } } }
    },
    plugins: { legend: { display: false } }
  };

  // Activity Donut Chart Config
  const pieData = {
    labels: ['Rumination', 'Lying Rest', 'Feeding', 'Moving', 'Standing/Other'],
    datasets: [{
      data: [
        health.ruminationHoursToday || 0,
        health.lyingHoursToday || 0,
        health.feedingHoursToday || 0,
        health.movingHoursToday || 0,
        +Math.max(0, 24 - ((health.ruminationHoursToday || 0) + (health.lyingHoursToday || 0) + (health.feedingHoursToday || 0) + (health.movingHoursToday || 0))).toFixed(1)
      ],
      backgroundColor: ['#00f3ff', '#a78bfa', '#39ff14', '#ffaa00', '#64748b'],
      borderWidth: 2,
      borderColor: '#05050b'
    }]
  };

  const pieOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom', labels: { color: '#38bdf8', font: { family: 'Rajdhani', size: 12, weight: 700 } } }
    },
    cutout: '75%'
  };

  const latestT = currentData.liveTelemetry || { x: 0, y: 0, z: 0, magnitude: 0 };
  const anomalyScore = ml.anomaly_detection?.score || 0;
  const confidence = (ml.activity?.confidence * 100) || 0;

  return (
    <div>
      {/* Hero Status Card */}
      <div className={`hero-status-card health-${riskClass}`} style={{ marginBottom: '2rem' }}>
        <div className="cow-profile-header">
          <div className="cow-avatar" style={{ clipPath: 'none', background: 'transparent', border: 'none', boxShadow: 'none' }}>
            <img src="/cow-logo.png" alt="Cow Logo" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
          </div>
          <div className="cow-info-main">
            <h2>{currentData.cowName} ({currentData.tagNumber})</h2>
            <div className="cow-meta-badges">
              <span className="meta-chip"><i className="fa-solid fa-microchip"></i> Node: {currentData.device_id}</span>
              <span className="meta-chip">{currentData.breed}</span>
              <span className={`health-badge ${health.health_risk_decision || 'HEALTHY'}`}>
                {health.health_risk_decision?.replace('_', ' ') || 'HEALTHY'}
              </span>
            </div>
          </div>
        </div>
        <div className="current-activity-box">
          <div className="activity-label-sm">CURRENT BEHAVIOR STATE</div>
          <div className="activity-badge-hero">
            <i className={`fa-solid ${act.icon}`}></i> {act.name}
          </div>
          <div className="activity-duration-tag">
            <i className="fa-solid fa-brain"></i> CONFIDENCE: {confidence.toFixed(1)}%
          </div>
        </div>
      </div>

      {health.health_risk_decision === 'HIGH_RISK' && (
        <div className="alert-banner danger">
          <div className="alert-icon"><i className="fa-solid fa-triangle-exclamation"></i></div>
          <div className="alert-content">
            <h4 style={{ margin: 0, fontSize: '1.2rem' }}>CRITICAL RISK DETECTED</h4>
            <p style={{ margin: 0, marginTop: '0.2rem', fontFamily: 'JetBrains Mono', fontSize: '0.85rem' }}>{health.healthRecommendation || 'Immediate attention required for this animal.'}</p> 
          </div>
        </div>
      )}

      {/* Top Grid: 6 Metric Cards */}
      <div className="grid-top-stats">
        
        {/* Card 1: Cow Activity (Active) */}
        <div className="metric-card">
          <div className="metric-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <i className="fa-solid fa-satellite-dish" style={{ fontSize: '0.9rem', color: 'var(--text-main)' }}></i>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--primary-emerald)', fontWeight: 700 }}>SYNCED</span>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            <div className="metric-value" style={{ fontSize: '1.4rem' }}>{act.code || 'RUS'}</div>
            <div className="metric-title" style={{ color: 'var(--text-main)', fontSize: '0.75rem', marginTop: '0.4rem' }}>MODEL CLASSIFICATION</div>
            <div className="metric-footer" style={{ marginTop: '0.2rem', fontSize: '0.65rem' }}>ML Engine ACTIVE</div>
          </div>
        </div>

        {/* Card 2: Rumination (Alert) */}
        <div className="metric-card">
          <div className="metric-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <i className="fa-solid fa-arrows-spin" style={{ fontSize: '0.9rem', color: 'var(--primary-cyan)' }}></i>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--primary-cyan)', fontWeight: 700 }}>VITAL</span>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            <div className="metric-value" style={{ fontSize: '1.4rem' }}>{health.ruminationHoursToday || 0} <span className="metric-unit">hrs</span></div>
            <div className="metric-title" style={{ color: 'var(--text-main)', fontSize: '0.75rem', marginTop: '0.4rem' }}>RUMINATION TOTAL</div>
            <div className="metric-footer" style={{ marginTop: '0.2rem', fontSize: '0.65rem' }}>Target: 8-10 hrs</div>
          </div>
        </div>

        {/* Card 3: Lying Rest (Risk) */}
        <div className="metric-card">
          <div className="metric-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <i className="fa-solid fa-bed" style={{ fontSize: '0.9rem', color: 'var(--accent-magenta)' }}></i>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--accent-magenta)', fontWeight: 700 }}>REST</span>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            <div className="metric-value" style={{ fontSize: '1.4rem' }}>{health.lyingHoursToday || 0} <span className="metric-unit">hrs</span></div>
            <div className="metric-title" style={{ color: 'var(--text-main)', fontSize: '0.75rem', marginTop: '0.4rem' }}>LYING REST HOURS</div>
            <div className="metric-footer" style={{ marginTop: '0.2rem', fontSize: '0.65rem' }}>Comfort Index</div>
          </div>
        </div>

        {/* Card 4: Heat Stress (Thermal) */}
        <div className="metric-card">
          <div className="metric-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <i className="fa-solid fa-temperature-arrow-up" style={{ fontSize: '0.9rem', color: 'var(--warning-amber)' }}></i>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--warning-amber)', fontWeight: 700 }}>THERMAL</span>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            <div className="metric-value" style={{ fontSize: '1.4rem', color: health.isHeatDetected ? 'var(--danger-rose)' : 'var(--text-main)' }}>
              {health.estrusProbabilityPercent || 0}%
            </div>
            <div className="metric-title" style={{ color: 'var(--text-main)', fontSize: '0.75rem', marginTop: '0.4rem' }}>ESTRUS PROBABILITY</div>
            <div className="metric-footer" style={{ marginTop: '0.2rem', fontSize: '0.65rem' }}>Environmental & Cycle</div>
          </div>
        </div>

        {/* Card 5: Telemetry */}
        <div className="metric-card">
          <div className="metric-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <i className="fa-solid fa-network-wired" style={{ fontSize: '0.9rem', color: 'var(--primary-emerald)' }}></i>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--primary-emerald)', fontWeight: 700 }}>UPLINK</span>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            <div className="metric-value" style={{ fontSize: '1.4rem' }}>{accelBuffer?.labels?.length || 0}</div>
            <div className="metric-title" style={{ color: 'var(--text-main)', fontSize: '0.75rem', marginTop: '0.4rem' }}>PACKETS BUFFERED</div>
            <div className="metric-footer" style={{ marginTop: '0.2rem', fontSize: '0.65rem' }}>Rolling Window Size</div>
          </div>
        </div>

        {/* Card 6: Isolation (Anomaly Score) */}
        <div className="metric-card">
          <div className="metric-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <i className="fa-solid fa-bug" style={{ fontSize: '0.9rem', color: 'var(--danger-rose)' }}></i>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--danger-rose)', fontWeight: 700 }}>ANOMALY</span>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            <div className="metric-value" style={{ fontSize: '1.4rem' }}>{anomalyScore.toFixed(3)}</div>
            <div className="metric-title" style={{ color: 'var(--text-main)', fontSize: '0.75rem', marginTop: '0.4rem' }}>ISOLATION FOREST SCORE</div>
            <div className="metric-footer" style={{ marginTop: '0.2rem', fontSize: '0.65rem' }}>Threshold dependent</div>
          </div>
        </div>

      </div>

      {/* Telemetry Row */}
      <div className="grid-telemetry">
        
        {/* Live Chart */}
        <div className="glass-panel">
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-wave-square"></i>
              RAW XYZ MOTION TELEMETRY (10 HZ)
            </div>
            <div className="status-pill online">
              <span className="pulse-dot"></span>
              STREAMING
            </div>
          </div>
          <div className="card-body">
            <div className="accel-chart-container" style={{ height: '300px' }}>
              <Line data={accelChartData} options={accelChartOptions} />
            </div>

            <div className="telemetry-meta-row">
              <div>
                <span className="axis-pill axis-x">X: {latestT.x.toFixed(3)}g</span>
                <span className="axis-pill axis-y">Y: {latestT.y.toFixed(3)}g</span>
                <span className="axis-pill axis-z">Z: {latestT.z.toFixed(3)}g</span>
                <span className="axis-pill axis-mag">|a|: {latestT.magnitude.toFixed(3)}g</span>
              </div>
              <div style={{ color: 'var(--primary-cyan)', fontWeight: 700 }}>
                PAYLOAD: 80 SAMPLES / 240 BYTES
              </div>
            </div>
          </div>
        </div>

        {/* Donut Share */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-chart-pie"></i>
              24H BEHAVIOR MATRIX (PROJECTED)
            </div>
          </div>
          <div className="card-body" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', height: '260px' }}>
            <Doughnut data={pieData} options={pieOptions} />
          </div>
          <div style={{ padding: '1.25rem', borderTop: '1px solid var(--primary-cyan)', background: 'var(--bg-panel)', textAlign: 'center' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontFamily: 'JetBrains Mono' }}>SYS: </span>
            <span style={{ fontWeight: 700, fontFamily: 'JetBrains Mono', color: 'var(--primary-emerald)', fontSize: '0.85rem' }}>CONTINUOUS DIAGNOSTICS OK</span>
          </div>
        </div>

      </div>

      {/* Activity Legend Grid */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <div style={{ fontSize: '0.9rem', fontFamily: 'var(--title-font)', fontWeight: 700, textTransform: 'uppercase', color: 'var(--primary-cyan)', marginBottom: '1rem', letterSpacing: '0.1em' }}>
          NEURAL NETWORK CLASSIFICATION LABELS (11 CLASSES):
        </div>
        <div className="activity-legend-grid">
          {Object.keys(ACTIVITY_CLASSES).map((key) => {
            const item = ACTIVITY_CLASSES[key];
            return (
              <div key={key} className="legend-item">
                <div className="legend-color-dot" style={{ background: item.color }}></div>
                <strong>{item.code}:</strong> {item.name}
              </div>
            );
          })}
        </div>
      </div>

    </div>
  );
}
