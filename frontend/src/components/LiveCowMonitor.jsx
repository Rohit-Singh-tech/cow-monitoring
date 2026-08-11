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

export default function LiveCowMonitor({ currentData, accelBuffer }) {
  if (!currentData) return <div class="glass-panel" style={{ padding: '2rem' }}>Loading live cow monitor data...</div>;

  const act = currentData.currentActivity || {};
  const health = currentData.healthStatus || {};
  const hw = currentData.deviceHardware || {};

  // Live Accelerometer Line Chart Config
  const accelChartData = {
    labels: accelBuffer.labels,
    datasets: [
      { label: 'X-Axis', data: accelBuffer.x, borderColor: '#f43f5e', borderWidth: 2, pointRadius: 0, tension: 0.3 },
      { label: 'Y-Axis', data: accelBuffer.y, borderColor: '#10b981', borderWidth: 2, pointRadius: 0, tension: 0.3 },
      { label: 'Z-Axis', data: accelBuffer.z, borderColor: '#06b6d4', borderWidth: 2, pointRadius: 0, tension: 0.3 },
      { label: 'Magnitude |a|', data: accelBuffer.mag, borderColor: '#f59e0b', borderWidth: 1.5, borderDash: [4, 4], pointRadius: 0, tension: 0.3 }
    ]
  };

  const accelChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      x: { display: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } } },
      y: { min: -1.5, max: 2.5, grid: { color: 'rgba(255,255,255,0.08)' }, ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } } }
    },
    plugins: { legend: { display: false } }
  };

  // Activity Donut Chart Config
  const pieData = {
    labels: ['Rumination (RUS)', 'Lying Rest (REL)', 'Feeding (FEP)', 'Moving (MOV)', 'Standing/Other'],
    datasets: [{
      data: [
        health.ruminationHoursToday || 0,
        health.lyingHoursToday || 0,
        health.feedingHoursToday || 0,
        health.movingHoursToday || 0,
        +Math.max(0, 24 - ((health.ruminationHoursToday || 0) + (health.lyingHoursToday || 0) + (health.feedingHoursToday || 0) + (health.movingHoursToday || 0))).toFixed(1)
      ],
      backgroundColor: ['#06b6d4', '#8b5cf6', '#10b981', '#f59e0b', '#64748b'],
      borderWidth: 2,
      borderColor: '#070a12'
    }]
  };

  const pieOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } }
    },
    cutout: '70%'
  };

  const latestT = currentData.liveTelemetry || { x: 0.05, y: 0.05, z: 1.02, magnitude: 1.022 };

  return (
    <div>
      {/* Alert Banner */}
      {health.isHeatDetected && (
        <div class="alert-banner danger">
          <div class="alert-icon"><i class="fa-solid fa-fire-flame-curved"></i></div>
          <div class="alert-content">
            <h4>⚡ ESTRUS HEAT DETECTED FOR COW #{currentData.device_id} ({currentData.cowName})</h4>
            <p>{health.healthRecommendation}</p> 
          </div>
        </div>
      )}

      {/* Top Grid: 6 Metric Cards */}
      <div class="grid-top-stats">
        
        {/* Card 1: Cow Activity (Active) */}
        <div class="metric-card">
          <div class="metric-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <i class="fa-solid fa-check" style={{ fontSize: '0.9rem', color: 'var(--text-main)' }}></i>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--primary-emerald)', fontWeight: 700 }}>Active</span>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            <div class="metric-value" style={{ fontSize: '1.4rem' }}>{act.code || 'RUS'}</div>
            <div class="metric-title" style={{ color: 'var(--text-main)', fontSize: '0.75rem', marginTop: '0.2rem' }}>Current Activity</div>
            <div class="metric-footer" style={{ marginTop: '0.2rem', fontSize: '0.65rem' }}>{act.name}</div>
          </div>
        </div>

        {/* Card 2: Rumination (Alert) */}
        <div class="metric-card">
          <div class="metric-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <i class="fa-solid fa-triangle-exclamation" style={{ fontSize: '0.9rem', color: 'var(--warning-amber)' }}></i>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--warning-amber)', fontWeight: 700 }}>Alert</span>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            <div class="metric-value" style={{ fontSize: '1.4rem' }}>{health.ruminationHoursToday || 0}</div>
            <div class="metric-title" style={{ color: 'var(--text-main)', fontSize: '0.75rem', marginTop: '0.2rem' }}>Rumination Hours</div>
            <div class="metric-footer" style={{ marginTop: '0.2rem', fontSize: '0.65rem' }}>Target: 8-10 hrs</div>
          </div>
        </div>

        {/* Card 3: Lying Rest (Risk) */}
        <div class="metric-card">
          <div class="metric-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <i class="fa-solid fa-bed" style={{ fontSize: '0.9rem', color: 'var(--danger-rose)' }}></i>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--danger-rose)', fontWeight: 700 }}>Risk</span>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            <div class="metric-value" style={{ fontSize: '1.4rem' }}>{health.lyingHoursToday || 0}</div>
            <div class="metric-title" style={{ color: 'var(--text-main)', fontSize: '0.75rem', marginTop: '0.2rem' }}>Lying Rest Hours</div>
            <div class="metric-footer" style={{ marginTop: '0.2rem', fontSize: '0.65rem' }}>Comfort Monitoring</div>
          </div>
        </div>

        {/* Card 4: Heat Stress (Thermal) */}
        <div class="metric-card">
          <div class="metric-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <i class="fa-solid fa-temperature-half" style={{ fontSize: '0.9rem', color: 'var(--accent-purple)' }}></i>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--accent-purple)', fontWeight: 700 }}>Thermal</span>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            <div class="metric-value" style={{ fontSize: '1.4rem' }}>{health.estrusProbabilityPercent || 0}%</div>
            <div class="metric-title" style={{ color: 'var(--text-main)', fontSize: '0.75rem', marginTop: '0.2rem' }}>Heat / Estrus Risk</div>
            <div class="metric-footer" style={{ marginTop: '0.2rem', fontSize: '0.65rem' }}>Environmental & Cycle</div>
          </div>
        </div>

        {/* Card 5: Telemetry */}
        <div class="metric-card">
          <div class="metric-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <i class="fa-solid fa-box" style={{ fontSize: '0.9rem', color: 'var(--primary-cyan)' }}></i>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--primary-cyan)', fontWeight: 700 }}>Telemetry</span>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            <div class="metric-value" style={{ fontSize: '1.4rem' }}>{accelBuffer?.labels?.length || 0}</div>
            <div class="metric-title" style={{ color: 'var(--text-main)', fontSize: '0.75rem', marginTop: '0.2rem' }}>Packets in Buffer</div>
            <div class="metric-footer" style={{ marginTop: '0.2rem', fontSize: '0.65rem' }}>Current window size</div>
          </div>
        </div>

        {/* Card 6: Isolation (Anomaly Score) */}
        <div class="metric-card">
          <div class="metric-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <i class="fa-solid fa-brain" style={{ fontSize: '0.9rem', color: 'var(--primary-emerald)' }}></i>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--primary-emerald)', fontWeight: 700 }}>Isolation</span>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            <div class="metric-value" style={{ fontSize: '1.4rem' }}>{((health.estrusProbabilityPercent || 0) / 100).toFixed(4)}</div>
            <div class="metric-title" style={{ color: 'var(--text-main)', fontSize: '0.75rem', marginTop: '0.2rem' }}>Calculated Anomaly Score</div>
            <div class="metric-footer" style={{ marginTop: '0.2rem', fontSize: '0.65rem' }}>Risk index</div>
          </div>
        </div>

      </div>

      {/* Telemetry Row */}
      <div class="grid-telemetry">
        
        {/* Live Chart */}
        <div class="glass-panel">
          <div class="card-header-box">
            <div class="card-title">
              <i class="fa-solid fa-chart-line"></i>
              Live 3-Axis Motion Telemetry (LIS3DH Accelerometer @ 10 Hz / 100ms)
            </div>
            <div class="status-pill online">
              <span class="pulse-dot"></span>
              Sampling 10 samples/sec
            </div>
          </div>
          <div class="card-body">
            <div class="accel-chart-container">
              <Line data={accelChartData} options={accelChartOptions} />
            </div>

            <div class="telemetry-meta-row">
              <div>
                <span class="axis-pill axis-x">X-Axis: {latestT.x.toFixed(3)}g</span>
                <span class="axis-pill axis-y">Y-Axis: {latestT.y.toFixed(3)}g</span>
                <span class="axis-pill axis-z">Z-Axis: {latestT.z.toFixed(3)}g</span>
                <span class="axis-pill axis-mag">|a|: {latestT.magnitude.toFixed(3)}g</span>
              </div>
              <div style={{ color: 'var(--text-muted)' }}>
                Packet Payload: 80 samples / 240 bytes XYZ • SPI Ring Buffer ACTIVE
              </div>
            </div>
          </div>
        </div>

        {/* Donut Share */}
        <div class="glass-panel" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div class="card-header-box">
            <div class="card-title">
              <i class="fa-solid fa-chart-pie"></i>
              Today's Activity Share
            </div>
          </div>
          <div class="card-body" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', height: '230px' }}>
            <Doughnut data={pieData} options={pieOptions} />
          </div>
          <div style={{ padding: '1rem 1.5rem', borderTop: '1px solid var(--border-glass)', background: 'rgba(15, 23, 42, 0.4)', textAlign: 'center' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>Behavioral Health Status: </span>
            <span style={{ fontWeight: 700, fontFamily: 'JetBrains Mono', color: 'var(--primary-emerald)', fontSize: '0.8rem' }}>24/7 Continuous Health Tracking</span>
          </div>
        </div>

      </div>

      {/* Activity Legend Grid */}
      <div class="glass-panel" style={{ padding: '1.25rem 1.5rem' }}>
        <div style={{ fontSize: '0.825rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          IIT Ropar 11 Key Monitored Activity Classes (Section 1.5):
        </div>
        <div class="activity-legend-grid">
          {Object.keys(ACTIVITY_CLASSES).map((key) => {
            const item = ACTIVITY_CLASSES[key];
            return (
              <div key={key} class="legend-item">
                <div class="legend-color-dot" style={{ background: item.color }}></div>
                <strong>{item.code}:</strong> {item.name}
              </div>
            );
          })}
        </div>
      </div>

    </div>
  );
}
