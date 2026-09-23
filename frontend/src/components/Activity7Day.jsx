import React, { useState } from 'react';
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
import { useConfig } from '../context/ConfigContext';
import { formatHours, formatDetailedDuration } from '../utils';

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

export default function Activity7Day({ data7Day, logs, cowId, theme, isLoading }) {
  const { activities } = useConfig();
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [dateScope, setDateScope] = useState('24H'); // '24H' (Today) or 'ALL'

  // Show loading state when fetching (especially for AWS devices which take longer)
  if (isLoading && !data7Day) {
    return (
      <div className="glass-panel" style={{ padding: '4rem 2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
        <div style={{ position: 'relative', width: '64px', height: '64px' }}>
          <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '3rem', color: 'var(--accent-emerald)', position: 'absolute', top: 0, left: 0 }}></i>
        </div>
        <div style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-primary)' }}>Fetching 7-Day Activity Data</div>
        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', maxWidth: '320px', lineHeight: 1.5 }}>
          Querying each day individually from the AWS API — this takes up to 30 seconds on first load, then is cached for 24 hours.
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
          {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map((d, i) => (
            <div key={d} style={{
              width: '32px', height: '48px', borderRadius: '6px',
              background: `rgba(16,185,129,${0.15 + i * 0.05})`,
              animation: `pulse 1.4s ease-in-out ${i * 0.1}s infinite`
            }} />
          ))}
        </div>
      </div>
    );
  }

  if (!data7Day) {
    return (
      <div className="glass-panel" style={{ padding: '3rem 2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
        <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '2rem', color: 'var(--accent-emerald)' }}></i>
        <div style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)' }}>Loading 7-day health trend data...</div>
      </div>
    );
  }

  let history = data7Day.history;

  // If backend returns parallel arrays instead of a history array, construct the history array
  if (!history && data7Day.days) {
    history = data7Day.days.map((day, idx) => ({
      day: day,
      date: data7Day.dates ? data7Day.dates[idx] : `2026-08-0${idx + 1}`,
      REL: data7Day.lyingRestHours?.[idx] || 0,
      RUS: data7Day.ruminationHours?.[idx] || 0,
      FEP: data7Day.feedingHours?.[idx] || 0,
      MOV: data7Day.activeHours?.[idx] || 0,
      RES: data7Day.standingRestHours?.[idx] || 0,
      DRN: data7Day.drinkingHours?.[idx] || 0,
      LCK: data7Day.lickingHours?.[idx] || 0,
      OTH: data7Day.otherHours?.[idx] || 0,
      healthScore: data7Day.healthScores?.[idx] || 0,
      estrusIndex: data7Day.estrusIndices?.[idx] || 0
    }));
  }

  if (!history || history.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '3rem 2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        <i className="fa-solid fa-folder-open" style={{ fontSize: '2rem', marginBottom: '0.5rem', display: 'block', color: 'var(--accent-emerald)' }}></i>
        <h3 style={{ color: 'var(--text-primary)', fontWeight: 800 }}>No historical trend data recorded for this node yet.</h3>
      </div>
    );
  }

  const labels = history.map(d => d.date ? `${d.day} (${d.date.slice(5)})` : d.day);

  // Stacked Bar Chart Data
  const barChartData = {
    labels: labels,
    datasets: [
      { label: `Rest (${activities?.REL?.name || 'Lying'} & RES)`, data: history.map(d => d.REL), backgroundColor: activities?.REL?.color || '#8B5CF6', borderRadius: 4 },
      { label: `RUS (${activities?.RUS?.name || 'Rumination'})`, data: history.map(d => d.RUS), backgroundColor: activities?.RUS?.color || '#06B6D4', borderRadius: 4 },
      { label: `FEP (${activities?.FEP?.name || 'Feeding'})`, data: history.map(d => d.FEP), backgroundColor: activities?.FEP?.color || '#10B981', borderRadius: 4 },
      { label: `MOV (${activities?.MOV?.name || 'Active'})`, data: history.map(d => d.MOV), backgroundColor: activities?.MOV?.color || '#F59E0B', borderRadius: 4 },
      { label: `RES (${activities?.RES?.name || 'Standing Rest'})`, data: history.map(d => d.RES), backgroundColor: activities?.RES?.color || '#64748B', borderRadius: 4 },
      { label: `DRN / Other`, data: history.map(d => +( (d.DRN || 0) + (d.LCK || 0) + (d.OTH || 0) ).toFixed(1)), backgroundColor: activities?.DRN?.color || '#3B82F6', borderRadius: 4 }
    ]
  };

  const gridColor = theme === 'light' ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.08)';
  const tickColor = theme === 'light' ? '#334155' : '#E2E8F0';
  const legendTextColor = theme === 'light' ? '#0F172A' : '#FFFFFF';

  const barChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        stacked: true,
        grid: { color: gridColor },
        ticks: { color: tickColor, font: { family: 'Inter', size: 11, weight: '700' } }
      },
      y: {
        stacked: true,
        max: 24,
        grid: { color: gridColor },
        ticks: { color: tickColor, font: { family: 'JetBrains Mono', size: 11, weight: '700' } },
        title: { display: true, text: 'Hours in Day', color: tickColor, font: { size: 11, family: 'Inter', weight: '700' } }
      }
    },
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: legendTextColor,
          font: { family: 'Inter', size: 11, weight: '700' },
          boxWidth: 12,
          boxHeight: 12,
          padding: 14
        }
      },
      tooltip: {
        backgroundColor: theme === 'light' ? '#FFFFFF' : '#09140F',
        titleColor: theme === 'light' ? '#0F172A' : '#FFFFFF',
        bodyColor: theme === 'light' ? '#334155' : '#E2E8F0',
        borderColor: 'rgba(52, 211, 153, 0.5)',
        borderWidth: 1,
        titleFont: { family: 'Inter', size: 12, weight: '800' },
        bodyFont: { family: 'JetBrains Mono', size: 11 },
        callbacks: {
          label: function(context) {
            const val = context.parsed.y !== undefined ? context.parsed.y : context.raw;
            if (val === 0 || val === null || val === undefined) return null;
            const totalMins = Math.round(val * 60);
            const hrs = Math.floor(totalMins / 60);
            const remMins = totalMins % 60;
            const durStr = hrs > 0 ? (remMins > 0 ? `${hrs}h ${remMins}m` : `${hrs}h`) : `${remMins}m`;
            return ` ${context.dataset.label}: ${val} hrs (${durStr})`;
          }
        }
      }
    }
  };

  const formatDateTime = (isoStr) => {
    if (!isoStr) return '—';
    try {
      const d = new Date(isoStr);
      const dateStr = d.toLocaleDateString([], { month: 'short', day: 'numeric' });
      const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      return `${dateStr}, ${timeStr}`;
    } catch (e) {
      return isoStr;
    }
  };

  const formatShortDateTime = (isoStr) => {
    if (!isoStr) return '—';
    try {
      const d = new Date(isoStr);
      const dateStr = d.toLocaleDateString([], { month: 'short', day: 'numeric' });
      const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      return `${dateStr}, ${timeStr}`;
    } catch (e) {
      return isoStr;
    }
  };

  // Health Score & Estrus Heat Index Line Chart Data (Data-driven, no fake fallbacks)
  const healthLineData = {
    labels: labels,
    datasets: [
      {
        label: 'Health Score %',
        data: history.map(d => {
          const hasData = (d.REL || 0) + (d.RUS || 0) + (d.FEP || 0) + (d.MOV || 0) + (d.RES || 0) + (d.DRN || 0) > 0 || (d.monitoredHours > 0);
          return hasData ? (d.healthScore !== undefined ? d.healthScore : null) : null;
        }),
        borderColor: '#10B981',
        backgroundColor: 'rgba(16, 185, 129, 0.15)',
        borderWidth: 3,
        tension: 0.35,
        fill: true,
        spanGaps: false,
        pointBackgroundColor: '#10B981',
        pointRadius: 4
      },
      {
        label: 'Estrus Heat Index %',
        data: history.map(d => {
          const hasData = (d.REL || 0) + (d.RUS || 0) + (d.FEP || 0) + (d.MOV || 0) + (d.RES || 0) + (d.DRN || 0) > 0 || (d.monitoredHours > 0);
          return hasData ? (d.estrusIndex !== undefined ? d.estrusIndex : null) : null;
        }),
        borderColor: '#F59E0B',
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
        borderWidth: 2,
        borderDash: [4, 4],
        tension: 0.35,
        fill: false,
        spanGaps: false,
        pointBackgroundColor: '#F59E0B',
        pointRadius: 3
      }
    ]
  };

  const healthLineOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        grid: { color: gridColor },
        ticks: { color: tickColor, font: { family: 'Inter', size: 11, weight: '700' } }
      },
      y: {
        min: 0,
        max: 100,
        grid: { color: gridColor },
        ticks: { color: tickColor, font: { family: 'JetBrains Mono', size: 11, weight: '700' } },
        title: { display: true, text: 'Index (%)', color: tickColor, font: { size: 11, family: 'Inter', weight: '700' } }
      }
    },
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: legendTextColor,
          font: { family: 'Inter', size: 11, weight: '700' },
          boxWidth: 12,
          boxHeight: 12,
          padding: 14
        }
      },
      tooltip: {
        backgroundColor: theme === 'light' ? '#FFFFFF' : '#09140F',
        titleColor: theme === 'light' ? '#0F172A' : '#FFFFFF',
        bodyColor: theme === 'light' ? '#334155' : '#E2E8F0',
        borderColor: 'rgba(52, 211, 153, 0.5)',
        borderWidth: 1,
        titleFont: { family: 'Inter', size: 12, weight: '800' },
        bodyFont: { family: 'JetBrains Mono', size: 11 }
      }
    }
  };

  // Compute Weekly Averages (use exact float values to preserve sub-hour minute and second precision)
  const avg = data7Day.weeklyAverageHours || (() => {
    if (!history || history.length === 0) return { REL: 0, RUS: 0, FEP: 0, MOV: 0, DRN: 0 };
    const sums = history.reduce((acc, curr) => ({
      REL: acc.REL + (curr.REL || 0),
      RUS: acc.RUS + (curr.RUS || 0),
      FEP: acc.FEP + (curr.FEP || 0),
      MOV: acc.MOV + (curr.MOV || 0),
      RES: acc.RES + (curr.RES || 0),
      DRN: acc.DRN + (curr.DRN || 0)
    }), { REL: 0, RUS: 0, FEP: 0, MOV: 0, RES: 0, DRN: 0 });
    return {
      REL: sums.REL / history.length,
      RUS: sums.RUS / history.length,
      FEP: sums.FEP / history.length,
      MOV: sums.MOV / history.length,
      RES: sums.RES / history.length,
      DRN: sums.DRN / history.length
    };
  })();

  // Filter Logs (now pre-grouped by backend)
  const activeLogs = logs || [];

  // Determine latest date in the log set to scope to Today (24 Hours)
  const latestDateStr = activeLogs.length > 0
    ? new Date(activeLogs[0].startTime).toISOString().slice(0, 10)
    : null;

  const scopeFilteredLogs = activeLogs.filter(log => {
    if (dateScope === '24H' && latestDateStr) {
      const logDate = new Date(log.startTime).toISOString().slice(0, 10);
      return logDate === latestDateStr;
    }
    return true;
  });

  const filteredLogs = scopeFilteredLogs.filter(log => {
    const matchesSearch =
      log.activityName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.activityCode?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.category?.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesCat = categoryFilter === 'ALL' || log.category === categoryFilter;
    return matchesSearch && matchesCat;
  });

  return (
    <div>
      {/* 7-Day Activity Stacked Chart */}
      <div className="glass-panel" style={{ marginBottom: '1.25rem' }}>
        <div className="card-header-box">
          <div className="card-title">
            <i className="fa-solid fa-chart-column" style={{ color: 'var(--accent-sky)' }}></i>
            7-DAY ACTIVITY TIME ALLOCATION BREAKDOWN (HOURS PER DAY)
          </div>
          <div className="meta-chip">7-Day Continuous Logging</div>
        </div>
        <div className="card-body">
          <div style={{ height: '300px', position: 'relative' }}>
            <Bar data={barChartData} options={barChartOptions} />
          </div>
        </div>
      </div>

      {/* Grid: Health Trend & Weekly Averages */}
      <div className="grid-2col" style={{ marginBottom: '1.25rem' }}>
        
        {/* Health Trend */}
        <div className="glass-panel">
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-heart-pulse" style={{ color: 'var(--accent-emerald)' }}></i>
              7-DAY HEALTH SCORE & ESTRUS HEAT PROBABILITY TREND
            </div>
          </div>
          <div className="card-body">
            <div style={{ height: '240px', position: 'relative' }}>
              <Line data={healthLineData} options={healthLineOptions} />
            </div>
          </div>
        </div>

        {/* Weekly Averages */}
        <div className="glass-panel">
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-list-check" style={{ color: 'var(--accent-amber)' }}></i>
              7-DAY AVERAGE ACTIVITY DISTRIBUTION
            </div>
            <div className="meta-chip" style={{ fontSize: '0.72rem' }}>7-Day Daily Average (Total / 7)</div>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.45rem 0.65rem', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
                  <i className="fa-solid fa-bed" style={{ color: '#8B5CF6' }}></i> Total Rest (REL+RES):
                </span>
                <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9rem', color: 'var(--accent-purple)' }}>{formatDetailedDuration(avg.REL)}/day</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.45rem 0.65rem', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
                  <i className="fa-solid fa-arrows-spin" style={{ color: '#06B6D4' }}></i> Standing Rumination (RUS):
                </span>
                <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9rem', color: 'var(--accent-sky)' }}>{formatDetailedDuration(avg.RUS)}/day</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.45rem 0.65rem', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
                  <i className="fa-solid fa-bowl-food" style={{ color: '#10B981' }}></i> Feeding (FEP):
                </span>
                <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9rem', color: 'var(--accent-emerald)' }}>{formatDetailedDuration(avg.FEP)}/day</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.45rem 0.65rem', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
                  <i className="fa-solid fa-person-walking" style={{ color: '#F59E0B' }}></i> Movement / Activity (MOV):
                </span>
                <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9rem', color: 'var(--accent-amber)' }}>{formatDetailedDuration(avg.MOV)}/day</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.45rem 0.65rem', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
                  <i className="fa-solid fa-glass-water" style={{ color: '#3B82F6' }}></i> Drinking (DRN):
                </span>
                <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9rem', color: 'var(--accent-cyan)' }}>{formatDetailedDuration(avg.DRN)}/day</strong>
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* Activity Transition Log Table & Responsive Cards */}
      <div className="glass-panel">
        <div className="card-header-box" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
          <div className="card-title">
            <i className="fa-solid fa-clock-rotate-left" style={{ color: 'var(--accent-amber)' }}></i>
            {dateScope === '24H' ? "TODAY'S 24-HOUR ACTIVITY TRANSITION LOGS" : "7-DAY ACTIVITY TRANSITION LOGS"}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
            <div className="tab-pill-group" style={{ display: 'inline-flex', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)', padding: '2px' }}>
              <button
                type="button"
                className={`tab-pill-btn ${dateScope === '24H' ? 'active' : ''}`}
                style={{
                  padding: '4px 10px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  background: dateScope === '24H' ? 'var(--accent-emerald)' : 'transparent',
                  color: dateScope === '24H' ? '#FFFFFF' : 'var(--text-muted)'
                }}
                onClick={() => setDateScope('24H')}
              >
                Today (24 Hours)
              </button>
              <button
                type="button"
                className={`tab-pill-btn ${dateScope === 'ALL' ? 'active' : ''}`}
                style={{
                  padding: '4px 10px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  background: dateScope === 'ALL' ? 'var(--accent-emerald)' : 'transparent',
                  color: dateScope === 'ALL' ? '#FFFFFF' : 'var(--text-muted)'
                }}
                onClick={() => setDateScope('ALL')}
              >
                All 7 Days
              </button>
            </div>

            <input
              type="text"
              placeholder="Search logs..."
              className="search-input-box"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ width: '130px' }}
            />
            <select
              className="search-input-box"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="ALL">All Categories</option>
              <option value="Rest">Rest</option>
              <option value="Digestion">Digestion</option>
              <option value="Nutrition">Nutrition</option>
              <option value="Locomotion">Locomotion</option>
            </select>
            <a href={`/api/export/csv?cowId=${cowId}`} className="btn btn-primary" target="_blank" rel="noreferrer" style={{ height: '34px', fontSize: '0.78rem' }}>
              <i className="fa-solid fa-file-arrow-down"></i> EXPORT CSV
            </a>
          </div>
        </div>

        <div className="card-body" style={{ padding: 0 }}>
          {/* Desktop Table View */}
          <div className="table-responsive logs-desktop-table">
            <table className="custom-table">
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
                {filteredLogs && filteredLogs.length > 0 ? (
                  filteredLogs.map(log => (
                    <tr key={log.logId}>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontWeight: 700 }}>#{log.logId}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 800 }}>
                        {data7Day?.device_id ? `Node-${data7Day.device_id}` : `Node-${cowId}`}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                        {formatDateTime(log.startTime)}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                        {formatDateTime(log.endTime)}
                      </td>
                      <td><strong style={{ color: 'var(--text-primary)' }}>{log.durationDisplay || `${log.durationMinutes} mins`}</strong></td>
                      <td>
                        <span className="code-badge" style={{ background: `${log.color || '#38bdf8'}25`, color: log.color || 'var(--accent-sky)', border: `1px solid ${log.color || 'var(--accent-sky)'}` }}>
                          {log.activityCode} - {log.activityName}
                        </span>
                      </td>
                      <td><span className="meta-chip">{log.category}</span></td>
                      <td><strong style={{ color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)', fontWeight: 800 }}>{log.confidencePercent}%</strong></td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                        {log.startPacketId} – {log.endPacketId}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="9" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                      No activity logs match your search or filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Mobile / Tablet Responsive Timeline View (100% visible, zero horizontal scroll) */}
          <div className="logs-mobile-timeline">
            {filteredLogs && filteredLogs.length > 0 ? (
              filteredLogs.map(log => (
                <div key={log.logId} className="activity-log-card">
                  <div className="log-card-header">
                    <div 
                      className="log-activity-badge" 
                      style={{ 
                        background: `${log.color || '#38bdf8'}20`, 
                        color: log.color || 'var(--accent-sky)', 
                        border: `1px solid ${log.color || 'var(--accent-sky)'}40` 
                      }}
                    >
                      <span className="dot" style={{ background: log.color || 'var(--accent-sky)' }}></span>
                      <strong>{log.activityCode}</strong> • {log.activityName}
                    </div>
                    <span className="log-duration-chip">
                      <i className="fa-solid fa-stopwatch"></i> {log.durationDisplay || `${log.durationMinutes} mins`}
                    </span>
                  </div>

                  <div className="log-card-body">
                    <div className="log-time-row">
                      <span className="log-time">
                        <i className="fa-regular fa-clock"></i> {formatShortDateTime(log.startTime)} → {formatShortDateTime(log.endTime)}
                      </span>
                      <span className="meta-chip">{log.category}</span>
                    </div>

                    <div className="log-meta-row">
                      <div className="log-confidence-bar-wrap">
                        <span className="confidence-label">ML Confidence: <strong>{log.confidencePercent}%</strong></span>
                        <div className="confidence-track">
                          <div 
                            className="confidence-fill" 
                            style={{ 
                              width: `${log.confidencePercent}%`, 
                              background: log.confidencePercent >= 80 ? 'var(--accent-emerald)' : 'var(--accent-amber)' 
                            }}
                          ></div>
                        </div>
                      </div>
                      <span className="log-packet-id">{log.startPacketId} – {log.endPacketId}</span>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)' }}>
                No activity logs match your search or filter.
              </div>
            )}
          </div>
        </div>
      </div>

    </div>
  );
}
