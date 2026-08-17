import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  Filler
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
  ArcElement,
  Filler
);

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

export default function LiveCowMonitor({ currentData, accelBuffer, theme }) {
  if (!currentData) {
    return (
      <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center' }}>
        <i className="fa-solid fa-satellite-dish fa-spin" style={{ fontSize: '2.5rem', color: 'var(--accent-emerald)', marginBottom: '1rem' }}></i>
        <h3 style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)', fontWeight: 800 }}>INITIALIZING NEURAL LINK...</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.5rem' }}>Awaiting live 10 Hz Bluetooth Low Energy data packets from livestock collar node.</p>
      </div>
    );
  }

  const actData = currentData.currentActivity || {};
  const health = (typeof currentData.healthStatus === 'object' ? currentData.healthStatus : null) ||
                 (typeof currentData.health_metrics === 'object' ? currentData.health_metrics : {}) || {};
  const ml = currentData.ml_inference || currentData.ml_predictions || {};

  const healthDecision = health.health_risk_decision || 
                         (typeof currentData.healthStatus === 'string' ? currentData.healthStatus : 'HEALTHY');
  
  const riskClass = String(healthDecision || 'healthy').toLowerCase().replace('_', '-');

  // Detect current activity key
  let currentActKey = 'RUS';
  if (actData.code) {
    currentActKey = actData.code;
  } else if (ml.activity?.code) {
    currentActKey = ml.activity.code;
  } else if (ml.activity?.primary_activity) {
    currentActKey = ml.activity.primary_activity;
  } else if (typeof currentData.currentActivity === 'string') {
    currentActKey = currentData.currentActivity;
  }

  const act = ACTIVITY_CLASSES[currentActKey] || actData || ACTIVITY_CLASSES.RUS;

  const isHighRisk = healthDecision === 'HIGH_RISK' || 
                     healthDecision === 'ESTRUS_ALERT' || 
                     Boolean(health.isHeatDetected) ||
                     (typeof health.estrusProbabilityPercent === 'number' && health.estrusProbabilityPercent > 70);

  const gridLineColor = theme === 'light' ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.06)';
  const chartTickColor = theme === 'light' ? '#475569' : '#94A3B8';

  // Accelerometer Live 3-Axis Stream
  const accelDataObj = accelBuffer || currentData.accelBuffer || {};
  const accelChartData = {
    labels: accelDataObj.labels || [],
    datasets: [
      {
        label: 'X (Lateral Acceleration)',
        data: accelDataObj.x || [],
        borderColor: '#38BDF8',
        backgroundColor: 'rgba(56, 189, 248, 0.05)',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.35,
        fill: false
      },
      {
        label: 'Y (Longitudinal Acceleration)',
        data: accelDataObj.y || [],
        borderColor: '#34D399',
        backgroundColor: 'rgba(52, 211, 153, 0.05)',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.35,
        fill: false
      },
      {
        label: 'Z (Vertical Acceleration)',
        data: accelDataObj.z || [],
        borderColor: '#A78BFA',
        backgroundColor: 'rgba(167, 139, 250, 0.05)',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.35,
        fill: false
      },
      {
        label: 'Magnitude |a|',
        data: accelDataObj.magnitude || accelDataObj.mag || [],
        borderColor: '#FBBF24',
        borderDash: [4, 4],
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.35,
        fill: false
      }
    ]
  };

  const accelChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 0 },
    scales: {
      x: {
        grid: { color: gridLineColor, drawBorder: false },
        ticks: { color: chartTickColor, maxTicksLimit: 8, font: { family: 'JetBrains Mono', size: 10, weight: '600' } }
      },
      y: {
        grid: { color: gridLineColor, drawBorder: false },
        ticks: { color: chartTickColor, font: { family: 'JetBrains Mono', size: 10, weight: '600' } }
      }
    },
    plugins: {
      legend: {
        position: 'top',
        align: 'end',
        labels: {
          color: theme === 'light' ? '#1E293B' : '#E2E8F0',
          boxWidth: 10,
          boxHeight: 10,
          font: { family: 'Inter', size: 11, weight: '700' },
          padding: 12
        }
      },
      tooltip: {
        backgroundColor: theme === 'light' ? '#FFFFFF' : '#09140F',
        titleColor: theme === 'light' ? '#0F172A' : '#FFFFFF',
        bodyColor: theme === 'light' ? '#334155' : '#E2E8F0',
        borderColor: 'rgba(52, 211, 153, 0.4)',
        borderWidth: 1,
        titleFont: { family: 'Inter', size: 11, weight: '700' },
        bodyFont: { family: 'JetBrains Mono', size: 11 },
        padding: 8
      }
    }
  };

  // Activity Donut Chart Config (Calculates exact monitored breakdown)
  const rumHours = Number(health.ruminationHoursToday || 0);
  const lyingHours = Number(health.lyingHoursToday || 0);
  const feedHours = Number(health.feedingHoursToday || 0);
  const moveHours = Number(health.movingHoursToday || 0);
  const monitoredHours = Number(health.monitoredHoursToday || 0);
  const otherHours = +Math.max(0, monitoredHours - (rumHours + lyingHours + feedHours + moveHours)).toFixed(1);

  const pieData = {
    labels: ['Rumination', 'Lying Rest', 'Feeding', 'Moving', 'Standing/Other'],
    datasets: [{
      data: [
        rumHours,
        lyingHours,
        feedHours,
        moveHours,
        otherHours
      ],
      backgroundColor: ['#06B6D4', '#8B5CF6', '#10B981', '#F59E0B', '#64748B'],
      borderColor: theme === 'light' ? '#FFFFFF' : 'rgba(8, 18, 13, 0.95)',
      borderWidth: 2,
      hoverOffset: 6
    }]
  };

  const pieOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { 
        position: 'bottom', 
        labels: { 
          color: theme === 'light' ? '#0F172A' : '#38BDF8', 
          font: { family: 'Inter', size: 11, weight: '700' },
          padding: 10,
          boxWidth: 10,
          boxHeight: 10
        } 
      },
      tooltip: {
        backgroundColor: theme === 'light' ? '#FFFFFF' : '#09140F',
        titleColor: theme === 'light' ? '#0F172A' : '#FFFFFF',
        bodyColor: theme === 'light' ? '#334155' : '#E2E8F0',
        borderColor: 'rgba(52, 211, 153, 0.4)',
        borderWidth: 1,
        titleFont: { family: 'Inter', size: 11, weight: '700' },
        bodyFont: { family: 'Inter', size: 11 },
        padding: 8
      }
    },
    cutout: '72%'
  };

  const latestT = currentData.liveTelemetry || { x: 0, y: 0, z: 0, magnitude: 0 };
  const anomalyScore = ml.anomaly_detection?.score || 0;
  const confidence = ml.activity?.confidence ? ml.activity.confidence * 100 : (actData.confidence || 85.8);

  return (
    <div>
      {/* Hero Status Card (Active Cattle Profile) */}
      <div className={`hero-status-card health-${riskClass}`} style={{ marginBottom: '1.25rem' }}>
        <div className="cow-profile-header">
          <div className="cow-avatar">
            <img src="/cow-logo.png" alt="Cow Logo" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
          </div>
          <div className="cow-info-main">
            <h2>{currentData.cowName || `Device #${currentData.device_id}`} <span style={{ color: 'var(--text-muted)', fontSize: '0.95rem', fontWeight: 700 }}>({currentData.tagNumber || `TAG-${currentData.device_id}`})</span></h2>
            <div className="cow-meta-badges">
              <span className="meta-chip"><i className="fa-solid fa-microchip" style={{ marginRight: '0.35rem', color: 'var(--accent-sky)' }}></i>Node: {currentData.device_id}</span>
              <span className="meta-chip"><i className="fa-solid fa-dna" style={{ marginRight: '0.35rem', color: 'var(--accent-purple)' }}></i>{currentData.breed || 'Gir / Sahiwal Dairy'}</span>
              <span className={`health-badge ${healthDecision}`}>
                {String(healthDecision).replace('_', ' ')}
              </span>
            </div>
          </div>
        </div>
        <div className="current-activity-box">
          <div className="activity-label-sm">CURRENT BEHAVIOUR STATE</div>
          <div className="activity-badge-hero">
            <i className={`fa-solid ${act.icon || 'fa-arrows-spin'}`} style={{ color: act.color }}></i> {act.name || 'Ruminating in standing position'}
          </div>
          <div className="activity-duration-tag">
            <i className="fa-solid fa-brain" style={{ color: 'var(--accent-emerald)', marginRight: '0.25rem' }}></i>
            CONFIDENCE: <strong style={{ color: 'var(--text-primary)' }}>{Number(confidence).toFixed(1)}%</strong>
          </div>
        </div>
      </div>

      {/* Critical Health Warning Alert Banner */}
      {isHighRisk && (
        <div className="alert-banner danger">
          <div className="alert-icon"><i className="fa-solid fa-triangle-exclamation"></i></div>
          <div className="alert-content">
            <h4>CRITICAL HEALTH ATTENTION REQUIRED</h4>
            <p>
              {health.healthRecommendation || 
               'CRITICAL: Cow is showing signs of being in heat and unusual movement patterns and behavior that is very different from the rest of the herd. Action needed: Prepare for artificial insemination (breeding) in the next 12 hours and physically check the cow for injury or sickness.'}
            </p> 
          </div>
        </div>
      )}

      {!isHighRisk && healthDecision === 'MONITOR' && (
        <div className="alert-banner warning">
          <div className="alert-icon"><i className="fa-solid fa-triangle-exclamation"></i></div>
          <div className="alert-content">
            <h4>HEALTH MONITORING ADVISORY</h4>
            <p>{health.healthRecommendation || 'MONITOR: Cow is showing unusual activity. Keep a close eye on her.'}</p>
          </div>
        </div>
      )}

      {/* Top Grid: 6 KPI Metric Cards with Original Names & Dual-Theme High Contrast */}
      <div className="grid-top-stats">
        
        {/* Card 1: Inference / Current Activity */}
        <div className="metric-card card-gradient-1">
          <div className="metric-header">
            <div className="metric-icon-box" style={{ background: 'rgba(14, 165, 233, 0.25)', color: 'var(--accent-sky)' }}>
              <i className="fa-solid fa-satellite-dish"></i>
            </div>
            <span className="kpi-badge badge-inference">
              INFERENCE
            </span>
          </div>
          <div>
            <div className="metric-value">{act.code || 'RUS'}</div>
            <div className="metric-title">CURRENT ACTIVITY</div>
            <div className="metric-footer">ML Engine ACTIVE</div>
          </div>
        </div>

        {/* Card 2: Vital / Rumination Total */}
        <div className="metric-card card-gradient-2">
          <div className="metric-header">
            <div className="metric-icon-box" style={{ background: 'rgba(16, 185, 129, 0.25)', color: 'var(--accent-emerald)' }}>
              <i className="fa-solid fa-arrows-spin"></i>
            </div>
            <span className="kpi-badge badge-vital">
              VITAL
            </span>
          </div>
          <div>
            <div className="metric-value">
              {health.ruminationHoursToday || 0} <span className="metric-unit">hrs</span>
            </div>
            <div className="metric-title">RUMINATION TOTAL</div>
            <div className="metric-footer">Target: 8-10 hrs</div>
          </div>
        </div>

        {/* Card 3: Rest / Lying Rest Hours */}
        <div className="metric-card card-gradient-3">
          <div className="metric-header">
            <div className="metric-icon-box" style={{ background: 'rgba(139, 92, 246, 0.25)', color: 'var(--accent-purple)' }}>
              <i className="fa-solid fa-bed"></i>
            </div>
            <span className="kpi-badge badge-rest">
              REST
            </span>
          </div>
          <div>
            <div className="metric-value">
              {health.lyingHoursToday || 0} <span className="metric-unit">hrs</span>
            </div>
            <div className="metric-title">LYING REST HOURS</div>
            <div className="metric-footer">Comfort Index</div>
          </div>
        </div>

        {/* Card 4: Thermal / Estrus Probability */}
        <div className="metric-card card-gradient-4">
          <div className="metric-header">
            <div className="metric-icon-box" style={{ background: 'rgba(245, 158, 11, 0.25)', color: 'var(--accent-amber)' }}>
              <i className="fa-solid fa-temperature-arrow-up"></i>
            </div>
            <span className="kpi-badge badge-thermal">
              THERMAL
            </span>
          </div>
          <div>
            <div className="metric-value" style={{ color: isHighRisk ? 'var(--accent-rose)' : 'var(--text-primary)' }}>
              {health.estrusProbabilityPercent || 0}%
            </div>
            <div className="metric-title">ESTRUS PROBABILITY</div>
            <div className="metric-footer">{isHighRisk ? '🚨 Estrus Flagged (In Heat)' : 'Environmental & Cycle'}</div>
          </div>
        </div>

        {/* Card 5: Uplink / Packets Buffered */}
        <div className="metric-card card-gradient-5">
          <div className="metric-header">
            <div className="metric-icon-box" style={{ background: 'rgba(6, 182, 212, 0.25)', color: 'var(--accent-cyan)' }}>
              <i className="fa-solid fa-network-wired"></i>
            </div>
            <span className="kpi-badge badge-uplink">
              UPLINK
            </span>
          </div>
          <div>
            <div className="metric-value">{accelDataObj.labels?.length || 80}</div>
            <div className="metric-title">PACKETS BUFFERED</div>
            <div className="metric-footer">Rolling Window Size</div>
          </div>
        </div>

        {/* Card 6: Anomaly / Isolation Forest Score */}
        <div className="metric-card card-gradient-6">
          <div className="metric-header">
            <div className="metric-icon-box" style={{ background: 'rgba(20, 184, 166, 0.25)', color: 'var(--accent-teal)' }}>
              <i className="fa-solid fa-bug"></i>
            </div>
            <span className="kpi-badge badge-anomaly">
              ANOMALY
            </span>
          </div>
          <div>
            <div className="metric-value" style={{ color: anomalyScore > 0.5 ? 'var(--accent-rose)' : 'var(--text-primary)' }}>
              {typeof anomalyScore === 'number' ? anomalyScore.toFixed(3) : anomalyScore}
            </div>
            <div className="metric-title">ISOLATION FOREST SCORE</div>
            <div className="metric-footer">Threshold dependent</div>
          </div>
        </div>

      </div>

      {/* Telemetry Charts Bento Row */}
      <div className="grid-telemetry">
        
        {/* 10 Hz Real-Time Accelerometer Chart */}
        <div className="glass-panel">
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-wave-square" style={{ color: 'var(--accent-cyan)' }}></i>
              RAW XYZ MOTION TELEMETRY (10 HZ LIVE STREAM)
            </div>
            <div className="status-pill streaming">
              <span className="pulse-dot"></span>
              STREAMING
            </div>
          </div>
          <div className="card-body">
            <div style={{ height: '260px', position: 'relative' }}>
              <Line data={accelChartData} options={accelChartOptions} />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.85rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-subtle)', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <span className="code-badge" style={{ background: 'rgba(56, 189, 248, 0.2)', color: 'var(--accent-sky)', border: '1px solid var(--accent-sky)' }}>X: {Number(latestT.x || 0).toFixed(3)}g</span>
                <span className="code-badge" style={{ background: 'rgba(52, 211, 153, 0.2)', color: 'var(--accent-emerald)', border: '1px solid var(--accent-emerald)' }}>Y: {Number(latestT.y || 0).toFixed(3)}g</span>
                <span className="code-badge" style={{ background: 'rgba(167, 139, 250, 0.2)', color: 'var(--accent-purple)', border: '1px solid var(--accent-purple)' }}>Z: {Number(latestT.z || 0).toFixed(3)}g</span>
                <span className="code-badge" style={{ background: 'rgba(251, 191, 36, 0.2)', color: 'var(--accent-amber)', border: '1px solid var(--accent-amber)' }}>|a|: {Number(latestT.magnitude || 0).toFixed(3)}g</span>
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.725rem', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                PAYLOAD: 80 SAMPLES / 240 BYTES
              </div>
            </div>
          </div>
        </div>

        {/* Actual Behavior Matrix Donut Chart */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-chart-pie" style={{ color: 'var(--accent-amber)' }}></i>
              ACTUAL BEHAVIOR MATRIX (TODAY)
            </div>
          </div>
          <div className="card-body" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '210px' }}>
            <Doughnut data={pieData} options={pieOptions} />
          </div>
          <div style={{ padding: '0.75rem 1rem', borderTop: '1px solid var(--border-subtle)', background: 'var(--bg-elevated)', textAlign: 'center', borderRadius: '0 0 var(--radius-md) var(--radius-md)' }}>
            <span style={{ color: 'var(--accent-emerald)', fontWeight: 800, fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
              <i className="fa-solid fa-circle-check" style={{ marginRight: '0.35rem' }}></i>
              CONTINUOUS DIAGNOSTICS ACTIVE
            </span>
          </div>
        </div>

      </div>

      {/* Activity Classifications Legend */}
      <div className="glass-panel" style={{ padding: '1.15rem 1.4rem' }}>
        <div style={{ fontSize: '0.825rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.04em', fontFamily: 'var(--font-display)' }}>
          <i className="fa-solid fa-tags" style={{ color: 'var(--accent-cyan)' }}></i>
          NEURAL NETWORK CLASSIFICATION LABELS (11 CLASSES):
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.65rem' }}>
          {['RES', 'RUS', 'MOV', 'FEP', 'DRN', 'LCK', 'REL', 'URI', 'DEF', 'ATT', 'OTH'].map((key) => {
            const item = ACTIVITY_CLASSES[key] || ACTIVITY_CLASSES.UNKNOWN;
            const isCurrent = key === currentActKey;
            return (
              <div 
                key={key} 
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '0.6rem', 
                  padding: '0.45rem 0.65rem', 
                  borderRadius: 'var(--radius-sm)', 
                  background: isCurrent ? (theme === 'light' ? '#e2f2e6' : 'linear-gradient(90deg, rgba(16, 185, 129, 0.25) 0%, rgba(6, 182, 212, 0.15) 100%)') : 'var(--bg-elevated)', 
                  border: isCurrent ? '1px solid var(--accent-emerald)' : '1px solid var(--border-subtle)',
                  fontSize: '0.775rem',
                  transition: 'all 0.2s ease'
                }}
              >
                <div style={{ width: '24px', height: '24px', borderRadius: '4px', background: `${item.color}25`, color: item.color, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', flexShrink: 0 }}>
                  <i className={`fa-solid ${item.icon}`}></i>
                </div>
                <div>
                  <strong style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{item.code}:</strong>{' '}
                  <span style={{ color: isCurrent ? 'var(--accent-emerald)' : 'var(--text-secondary)', fontWeight: isCurrent ? 800 : 600 }}>{item.name}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

    </div>
  );
}
