import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';
import { Bar, Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

export default function Activity7Day({ data7Day, logs, cowId, theme }) {
  if (!data7Day) return <div className="glass-panel" style={{ padding: '2rem' }}>Loading 7-day activity data...</div>;

  let history = data7Day.history;
  
  // If backend returns parallel arrays instead of a history array, construct the history array
  if (!history && data7Day.days) {
    history = data7Day.days.map((day, idx) => ({
      day: day,
      date: data7Day.dates ? data7Day.dates[idx] : `2026-08-0${idx+1}`, 
      REL: data7Day.lyingRestHours?.[idx] || 0,
      RUS: data7Day.ruminationHours?.[idx] || 0,
      FEP: data7Day.feedingHours?.[idx] || 0,
      MOV: data7Day.activeHours?.[idx] || 0,
      RES: 2.5, // Dummy values for missing fields to total ~24h
      DRN: 1.0,
      LCK: 0.5,
      OTH: 0.5,
      healthScore: 90 + Math.random() * 8, // Dummy health score
      estrusIndex: 10 + Math.random() * 5  // Dummy estrus index
    }));
  }

  if (!history || history.length === 0) return <div className="glass-panel" style={{ padding: '2rem' }}>No history data available.</div>;

  const labels = history.map(d => d.date ? `${d.day} (${d.date.slice(5)})` : d.day);

  // Stacked Bar Chart Data
  const barChartData = {
    labels: labels,
    datasets: [
      { label: 'REL (Lying Rest)', data: history.map(d => d.REL), backgroundColor: '#8b5cf6' },
      { label: 'RUS (Rumination)', data: history.map(d => d.RUS), backgroundColor: '#06b6d4' },
      { label: 'FEP (Feeding)', data: history.map(d => d.FEP), backgroundColor: '#10b981' },
      { label: 'MOV (Moving/Active)', data: history.map(d => d.MOV), backgroundColor: '#f59e0b' },
      { label: 'RES (Standing Rest)', data: history.map(d => d.RES), backgroundColor: '#64748b' },
      { label: 'DRN / Other', data: history.map(d => +(d.DRN + d.LCK + d.OTH).toFixed(1)), backgroundColor: '#3b82f6' }
    ]
  };

  const gridColor = theme === 'light' ? 'rgba(0, 0, 0, 0.05)' : 'rgba(255, 255, 255, 0.05)';
  const tickColor = theme === 'light' ? '#64748b' : '#94a3b8';

  const barChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { stacked: true, grid: { color: gridColor }, ticks: { color: tickColor } },
      y: { stacked: true, max: 24, grid: { color: gridColor }, ticks: { color: tickColor }, title: { display: true, text: 'Hours in Day', color: tickColor } }
    },
    plugins: {
      legend: { position: 'top', labels: { color: '#cbd5e1', font: { size: 11 } } }
    }
  };

  // Health Score Line Chart Data
  const healthLineData = {
    labels: history.map(d => d.day),
    datasets: [
      { label: 'Health Score %', data: history.map(d => d.healthScore), borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.1)', fill: true, tension: 0.3 },
      { label: 'Estrus Heat Index %', data: history.map(d => d.estrusIndex), borderColor: '#f59e0b', borderDash: [4, 4], tension: 0.3 }
    ]
  };

  const healthLineOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { grid: { color: gridColor }, ticks: { color: tickColor } },
      y: { min: 0, max: 100, grid: { color: gridColor }, ticks: { color: tickColor } }
    },
    plugins: { legend: { position: 'top', labels: { color: '#cbd5e1' } } }
  };

  const avg = data7Day.weeklyAverageHours || (() => {
    if (!history || history.length === 0) return { REL: 0, RUS: 0, FEP: 0, MOV: 0, DRN: 0 };
    const sums = history.reduce((acc, curr) => ({
      REL: acc.REL + (curr.REL || 0),
      RUS: acc.RUS + (curr.RUS || 0),
      FEP: acc.FEP + (curr.FEP || 0),
      MOV: acc.MOV + (curr.MOV || 0),
      DRN: acc.DRN + (curr.DRN || 0)
    }), { REL: 0, RUS: 0, FEP: 0, MOV: 0, DRN: 0 });
    return {
      REL: (sums.REL / history.length).toFixed(1),
      RUS: (sums.RUS / history.length).toFixed(1),
      FEP: (sums.FEP / history.length).toFixed(1),
      MOV: (sums.MOV / history.length).toFixed(1),
      DRN: (sums.DRN / history.length).toFixed(1)
    };
  })();

  // Group consecutive logs with the same activityCode
  const groupedLogs = [];
  if (logs && logs.length > 0) {
    let currentGroup = { ...logs[0] };
    for (let i = 1; i < logs.length; i++) {
      const log = logs[i];
      if (log.activityCode === currentGroup.activityCode) {
        currentGroup.startTime = log.startTime; // older start time
        currentGroup.durationMinutes += log.durationMinutes;
        currentGroup.startPacketId = log.startPacketId; // older packet
        currentGroup.confidencePercent = Math.round((currentGroup.confidencePercent + log.confidencePercent) / 2);
      } else {
        groupedLogs.push(currentGroup);
        currentGroup = { ...log };
      }
    }
    groupedLogs.push(currentGroup);
  }

  return (
    <div>
      {/* 7-Day Activity Stacked Chart */}
      <div class="glass-panel" style={{ marginBottom: '1.75rem' }}>
        <div class="card-header-box">
          <div class="card-title">
            <i class="fa-solid fa-chart-column"></i>
            7-Day Activity Time Allocation Breakdown (Hours per Day)
          </div>
          <div class="meta-chip">7-Day Continuous Logging</div>
        </div>
        <div class="card-body">
          <div style={{ height: '340px', position: 'relative' }}>
            <Bar data={barChartData} options={barChartOptions} />
          </div>
        </div>
      </div>

      {/* Grid: Health Trend & Weekly Averages */}
      <div class="grid-2col">
        
        {/* Health Trend */}
        <div class="glass-panel">
          <div class="card-header-box">
            <div class="card-title">
              <i class="fa-solid fa-heart-pulse"></i>
              7-Day Health Score & Estrus Heat Probability Trend
            </div>
          </div>
          <div class="card-body">
            <div style={{ height: '260px', position: 'relative' }}>
              <Line data={healthLineData} options={healthLineOptions} />
            </div>
          </div>
        </div>

        {/* Weekly Averages */}
        <div class="glass-panel">
          <div class="card-header-box">
            <div class="card-title">
              <i class="fa-solid fa-list-check"></i>
              7-Day Average Activity Distribution
            </div>
          </div>
          <div class="card-body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                <span><i class="fa-solid fa-bed" style={{ color: '#8b5cf6' }}></i> Lying Rest (REL):</span>
                <strong style={{ fontFamily: 'JetBrains Mono' }}>{avg.REL} hrs/day</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                <span><i class="fa-solid fa-arrows-spin" style={{ color: '#06b6d4' }}></i> Standing Rumination (RUS):</span>
                <strong style={{ fontFamily: 'JetBrains Mono' }}>{avg.RUS} hrs/day</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                <span><i class="fa-solid fa-bowl-food" style={{ color: '#10b981' }}></i> Feeding (FEP):</span>
                <strong style={{ fontFamily: 'JetBrains Mono' }}>{avg.FEP} hrs/day</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                <span><i class="fa-solid fa-person-walking" style={{ color: '#f59e0b' }}></i> Movement / Activity (MOV):</span>
                <strong style={{ fontFamily: 'JetBrains Mono' }}>{avg.MOV} hrs/day</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                <span><i class="fa-solid fa-glass-water" style={{ color: '#3b82f6' }}></i> Drinking (DRN):</span>
                <strong style={{ fontFamily: 'JetBrains Mono' }}>{avg.DRN} hrs/day</strong>
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* Activity Transition Log Table */}
      <div class="glass-panel">
        <div class="card-header-box">
          <div class="card-title">
            <i class="fa-solid fa-clock-rotate-left"></i>
            Recorded Activity Transition Logs (Last 24 Hours)
          </div>
          <a href={`/api/export/csv?cowId=${cowId}`} class="btn btn-secondary" target="_blank" rel="noreferrer">
            <i class="fa-solid fa-download"></i> Download CSV Log
          </a>
        </div>
        <div class="card-body">
          <div class="table-responsive">
            <table class="custom-table">
              <thead>
                <tr>
                  <th>Log ID</th>
                  <th>Cow ID</th>
                  <th>Start Time</th>
                  <th>End Time</th>
                  <th>Duration</th>
                  <th>Activity Class</th>
                  <th>Category</th>
                  <th>Confidence</th>
                  <th>SPI Packet IDs</th>
                </tr>
              </thead>
              <tbody>
                {groupedLogs && groupedLogs.length > 0 ? (
                  groupedLogs.map(log => (
                    <tr key={log.logId}>
                      <td style={{ fontFamily: 'JetBrains Mono', color: 'var(--text-main)' }}>#{log.logId}</td>
                      <td style={{ color: 'var(--text-main)', fontWeight: 600 }}>{data7Day?.device_id ? `Node-${data7Day.device_id}` : `Node-${cowId}`}</td>
                      <td style={{ color: 'var(--text-main)' }}>{new Date(log.startTime).toLocaleTimeString()}</td>
                      <td style={{ color: 'var(--text-main)' }}>{new Date(log.endTime).toLocaleTimeString()}</td>
                      <td style={{ color: 'var(--text-main)' }}><strong>{log.durationMinutes} mins</strong></td>
                      <td>
                        <span className="code-badge" style={{ background: `${log.color}33`, color: log.color, border: `1px solid ${log.color}` }}>
                          {log.activityCode} - {log.activityName}
                        </span>
                      </td>
                      <td style={{ color: 'var(--text-main)' }}>{log.category}</td>
                      <td><strong style={{ color: 'var(--primary-emerald)' }}>{log.confidencePercent}%</strong></td>
                      <td style={{ fontFamily: 'JetBrains Mono', fontSize: '0.775rem', color: 'var(--text-main)' }}>{log.startPacketId} - {log.endPacketId}</td>
                    </tr>
                  ))
                ) : (
                  <tr><td colSpan="9" style={{ textAlign: 'center', padding: '1rem', color: 'var(--text-main)' }}>No activity logs recorded yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

    </div>
  );
}
