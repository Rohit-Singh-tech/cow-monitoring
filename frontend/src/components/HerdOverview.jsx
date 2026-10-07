import React, { useState } from 'react';
import { useConfig } from '../context/ConfigContext';
import { formatHours } from '../utils';

import { API_BASE } from '../config/api';

export default function HerdOverview({ cows, onSelectCow, onRefreshCows }) {
  const { activities } = useConfig();
  const [searchTerm, setSearchTerm] = useState('');
  const [healthFilter, setHealthFilter] = useState('ALL');
  const [sourceFilter, setSourceFilter] = useState('ALL');

  // Tag Registry Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);
  const [tagForm, setTagForm] = useState({
    device_id: '',
    name: '',
    breed: '',
    location: '',
    weight: '',
    notes: '',
    source: 'aws_api'
  });

  const handleOpenEditModal = (cow = null) => {
    setStatusMsg(null);
    if (cow) {
      setTagForm({
        device_id: String(cow.device_id || cow.id || '').replace(/^aws-/, ''),
        name: cow.name || '',
        breed: cow.breed || '',
        location: cow.location || '',
        weight: cow.weight || '',
        notes: cow.notes || '',
        source: cow.source || (String(cow.id).startsWith('aws-') ? 'aws_api' : 'gatewayless')
      });
    } else {
      setTagForm({
        device_id: '',
        name: '',
        breed: 'Gir',
        location: 'Barn Alpha - Pasture 1',
        weight: '450',
        notes: '',
        source: 'aws_api'
      });
    }
    setIsModalOpen(true);
  };

  const handleSaveTag = async (e) => {
    e.preventDefault();
    if (!tagForm.device_id || !tagForm.name) {
      setStatusMsg({ type: 'error', text: 'Device ID and Cow Name are required.' });
      return;
    }
    setSubmitting(true);
    setStatusMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/tags`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device_id: String(tagForm.device_id).trim(),
          name: tagForm.name.trim(),
          breed: tagForm.breed ? tagForm.breed.trim() : null,
          location: tagForm.location ? tagForm.location.trim() : null,
          weight: tagForm.weight ? String(tagForm.weight).trim() : null,
          notes: tagForm.notes ? tagForm.notes.trim() : null
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setStatusMsg({ type: 'success', text: `Tag for Device #${tagForm.device_id} saved successfully!` });
        if (onRefreshCows) {
          await onRefreshCows();
        }
        setTimeout(() => {
          setIsModalOpen(false);
          setStatusMsg(null);
        }, 1200);
      } else {
        setStatusMsg({ type: 'error', text: data.detail || 'Failed to save tag registry entry.' });
      }
    } catch (err) {
      setStatusMsg({ type: 'error', text: 'Network error saving tag.' });
    } finally {
      setSubmitting(false);
    }
  };

  if (!cows || cows.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '3rem 2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '2rem', color: 'var(--accent-emerald)', marginBottom: '0.75rem', display: 'block' }}></i>
        <h3 style={{ color: 'var(--text-primary)', fontWeight: 800 }}>LOADING HERD REGISTRY...</h3>
      </div>
    );
  }

  const isAwsDevice = (c) => c.source === 'aws_api' || String(c.id).startsWith('aws-');

  const totalCount = cows.length;
  const awsCount = cows.filter(isAwsDevice).length;
  const gatewaylessCount = cows.filter(c => !isAwsDevice(c)).length;
  const alertCount = cows.filter(c => c.health_risk_decision === 'HIGH_RISK' || c.health_risk_decision === 'ESTRUS_ALERT').length;
  const liveStreamingCount = cows.filter(c => !c.isStale && ((c.monitoredHoursToday || 0) > 0 || (c.ruminationHoursToday || 0) > 0)).length;

  const filteredCows = cows.filter(cow => {
    const matchesSearch = 
      (cow.name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (cow.tagNumber || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      String(cow.device_id || '').includes(searchTerm) ||
      (cow.breed && cow.breed.toLowerCase().includes(searchTerm.toLowerCase()));

    const status = cow.health_risk_decision || 'HEALTHY';
    const matchesHealth = healthFilter === 'ALL'
      ? true
      : healthFilter === 'ALERTS'
        ? (status === 'HIGH_RISK' || status === 'ESTRUS_ALERT')
        : status === healthFilter;

    const isAws = isAwsDevice(cow);
    const cowSource = isAws ? 'aws_api' : 'gatewayless';
    const isLive = !cow.isStale && ((cow.monitoredHoursToday || 0) > 0 || (cow.ruminationHoursToday || 0) > 0);
    const matchesSource = sourceFilter === 'ALL' || (sourceFilter === 'LIVE' ? isLive : cowSource === sourceFilter);

    return matchesSearch && matchesHealth && matchesSource;
  });

  const hasActiveFilters = searchTerm !== '' || sourceFilter !== 'ALL' || healthFilter !== 'ALL';

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', fontFamily: 'var(--font-display)', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '32px', height: '32px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-emerald)' }}>
              <i className="fa-solid fa-cow"></i>
            </span>
            NODE DIRECTORY & CATTLE HERD REGISTRY
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.2rem' }}>
            Unified real-time telemetry across {awsCount} AWS Cloud IoT collars and {gatewaylessCount} Gatewayless nodes.
          </p>
        </div>

        {/* Global Live Pill */}
        <div className="status-pill online" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem', padding: '0.35rem 0.85rem' }}>
          <span className="pulse-dot" style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-emerald)', display: 'inline-block' }}></span>
          <span>{liveStreamingCount} LIVE STREAMING • {totalCount} ACTIVE NODES</span>
        </div>
      </div>

      {/* Interactive Quick KPI Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', marginBottom: '1.25rem' }}>
        {/* Total Herd */}
        <div 
          onClick={() => { setSourceFilter('ALL'); setHealthFilter('ALL'); }}
          className={`kpi-card kpi-all ${sourceFilter === 'ALL' && healthFilter === 'ALL' ? 'active' : ''}`}
          title="Click to view all cattle"
        >
          <div>
            <div style={{ fontSize: '0.68rem', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em', fontFamily: 'var(--font-mono)' }}>TOTAL CATTLE</div>
            <div style={{ fontSize: '1.45rem', fontWeight: 900, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', marginTop: '0.1rem' }}>{totalCount}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>All monitored nodes</div>
          </div>
          <div style={{ width: '38px', height: '38px', borderRadius: '10px', background: 'rgba(255, 255, 255, 0.05)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-primary)', fontSize: '1.1rem' }}>
            <i className="fa-solid fa-layer-group"></i>
          </div>
        </div>

        {/* AWS Cloud IoT */}
        <div 
          onClick={() => { setSourceFilter('aws_api'); setHealthFilter('ALL'); }}
          className={`kpi-card kpi-aws ${sourceFilter === 'aws_api' ? 'active' : ''}`}
          title="Click to filter only AWS Cloud IoT devices"
        >
          <div>
            <div className="kpi-label" style={{ fontSize: '0.68rem', fontWeight: 800, letterSpacing: '0.05em', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <span className="pulse-dot" style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#F59E0B' }}></span>
              AWS CLOUD IOT
            </div>
            <div className="kpi-val" style={{ fontSize: '1.45rem', fontWeight: 900, fontFamily: 'var(--font-display)', marginTop: '0.1rem' }}>{awsCount}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Live Cloud Collars</div>
          </div>
          <div style={{ width: '38px', height: '38px', borderRadius: '10px', background: 'rgba(245, 158, 11, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#F59E0B', fontSize: '1.1rem' }}>
            <i className="fa-solid fa-cloud"></i>
          </div>
        </div>

        {/* Gatewayless */}
        <div 
          onClick={() => { setSourceFilter('gatewayless'); setHealthFilter('ALL'); }}
          className={`kpi-card kpi-gw ${sourceFilter === 'gatewayless' ? 'active' : ''}`}
          title="Click to filter only Gatewayless collars"
        >
          <div>
            <div className="kpi-label" style={{ fontSize: '0.68rem', fontWeight: 800, letterSpacing: '0.05em', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#06B6D4', display: 'inline-block' }}></span>
              GATEWAYLESS
            </div>
            <div className="kpi-val" style={{ fontSize: '1.45rem', fontWeight: 900, fontFamily: 'var(--font-display)', marginTop: '0.1rem' }}>{gatewaylessCount}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Direct Nodes</div>
          </div>
          <div style={{ width: '38px', height: '38px', borderRadius: '10px', background: 'rgba(6, 182, 212, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#06B6D4', fontSize: '1.1rem' }}>
            <i className="fa-solid fa-database"></i>
          </div>
        </div>

        {/* Active Alerts */}
        <div 
          onClick={() => { setHealthFilter(healthFilter === 'ALERTS' ? 'ALL' : 'ALERTS'); }}
          className={`kpi-card kpi-alert ${healthFilter === 'ALERTS' ? 'active' : ''}`}
          title="Click to filter cows with High Risk or Estrus Alert"
        >
          <div>
            <div className="kpi-label" style={{ fontSize: '0.68rem', fontWeight: 800, letterSpacing: '0.05em', fontFamily: 'var(--font-mono)' }}>ACTIVE ALERTS</div>
            <div className="kpi-val" style={{ fontSize: '1.45rem', fontWeight: 900, fontFamily: 'var(--font-display)', marginTop: '0.1rem' }}>{alertCount}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>High Risk & Estrus</div>
          </div>
          <div style={{ width: '38px', height: '38px', borderRadius: '10px', background: 'rgba(239, 68, 68, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#EF4444', fontSize: '1.1rem' }}>
            <i className="fa-solid fa-triangle-exclamation"></i>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem', background: 'var(--bg-elevated)', padding: '0.75rem 1rem', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
        {/* Source Segmented Tabs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => setSourceFilter('ALL')}
            className={`source-tab-btn tab-all ${sourceFilter === 'ALL' ? 'active' : ''}`}
            title="Show all cattle nodes"
          >
            <i className="fa-solid fa-layer-group"></i>
            <span>All Sources ({totalCount})</span>
          </button>

          <button
            onClick={() => setSourceFilter('aws_api')}
            className={`source-tab-btn tab-aws ${sourceFilter === 'aws_api' ? 'active' : ''}`}
            title="Filter to AWS Cloud IoT devices"
          >
            <i className="fa-solid fa-cloud"></i>
            <span>AWS Cloud ({awsCount})</span>
          </button>

          <button
            onClick={() => setSourceFilter('gatewayless')}
            className={`source-tab-btn tab-gw ${sourceFilter === 'gatewayless' ? 'active' : ''}`}
            title="Filter to Gatewayless collar nodes"
          >
            <i className="fa-solid fa-database"></i>
            <span>Gatewayless ({gatewaylessCount})</span>
          </button>
        </div>

        {/* Search, Health Filter & Reset */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative' }}>
            <input 
              type="text"
              placeholder="Search cow name, tag, node..."
              className="search-input-box"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ width: '220px', paddingRight: searchTerm ? '2rem' : '0.75rem' }}
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                style={{
                  position: 'absolute',
                  right: '0.5rem',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  fontSize: '0.75rem'
                }}
              >
                <i className="fa-solid fa-xmark"></i>
              </button>
            )}
          </div>

          <select
            className="search-input-box"
            value={healthFilter}
            onChange={(e) => setHealthFilter(e.target.value)}
            style={{ width: '150px' }}
          >
            <option value="ALL">All Health States</option>
            <option value="ALERTS">🚨 Alerts Only</option>
            <option value="HEALTHY">🟢 Healthy</option>
            <option value="MONITOR">🟡 Monitor</option>
            <option value="HIGH_RISK">🔴 High Risk</option>
            <option value="ESTRUS_ALERT">🔥 Estrus Alert</option>
          </select>

          {hasActiveFilters && (
            <button
              onClick={() => { setSearchTerm(''); setSourceFilter('ALL'); setHealthFilter('ALL'); }}
              className="btn"
              style={{
                fontSize: '0.75rem',
                padding: '0.4rem 0.75rem',
                background: 'rgba(255, 255, 255, 0.05)',
                color: 'var(--text-muted)',
                border: '1px solid var(--border-medium)',
                borderRadius: '8px',
                cursor: 'pointer'
              }}
              title="Reset all filters"
            >
              <i className="fa-solid fa-rotate-left"></i> Reset
            </button>
          )}
        </div>
      </div>

      {/* Grid of Cattle Node Cards */}
      <div className="grid-herd">
        {filteredCows && filteredCows.length > 0 ? (
          filteredCows.map(cow => {
            let actKey = cow.currentActivity;
            if (!actKey && !cow.isStale && ((cow.monitoredHoursToday || 0) > 0)) {
              if ((cow.movingHoursToday || 0) > (cow.ruminationHoursToday || 0) && (cow.movingHoursToday || 0) > (cow.feedingHoursToday || 0)) actKey = 'MOV';
              else if ((cow.feedingHoursToday || 0) > (cow.ruminationHoursToday || 0)) actKey = 'FEP';
              else if ((cow.ruminationHoursToday || 0) > 0) actKey = 'RUS';
              else actKey = 'RES';
            }
            const act = activities[actKey] || (actKey ? { name: cow.activityName || actKey, color: '#F59E0B', icon: 'fa-person-walking' } : (activities['OTH'] || { name: 'Standing Rest', color: '#64748B', icon: 'fa-pause' }));
            const isCritical = cow.health_risk_decision === 'HIGH_RISK' || cow.health_risk_decision === 'ESTRUS_ALERT';
            const isAws = isAwsDevice(cow);

            return (
              <div
                key={cow.id}
                className="cow-card"
                style={{
                  border: isCritical 
                    ? '1px solid #EF4444' 
                    : isAws 
                      ? '1px solid rgba(245, 158, 11, 0.4)' 
                      : '1px solid var(--border-subtle)',
                  boxShadow: isAws 
                    ? '0 6px 20px rgba(245, 158, 11, 0.08)' 
                    : 'none',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  position: 'relative',
                  overflow: 'hidden'
                }}
              >
                {/* Top Subtle Brand Accent Line */}
                <div style={{
                  height: '3px',
                  width: '100%',
                  background: isAws 
                    ? 'linear-gradient(90deg, #F59E0B 0%, #06B6D4 100%)' 
                    : 'linear-gradient(90deg, #10B981 0%, #06B6D4 100%)',
                  position: 'absolute',
                  top: 0,
                  left: 0
                }}></div>

                <div>
                  <div className="cow-card-top" style={{ paddingTop: '0.35rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <div style={{
                        width: '42px',
                        height: '42px',
                        borderRadius: '10px',
                        background: isAws 
                          ? 'linear-gradient(135deg, rgba(245, 158, 11, 0.25) 0%, rgba(217, 119, 6, 0.25) 100%)' 
                          : 'linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(6, 182, 212, 0.2) 100%)',
                        border: isAws ? '1px solid rgba(251, 191, 36, 0.5)' : '1px solid rgba(52, 211, 153, 0.3)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '4px',
                        flexShrink: 0
                      }}>
                        <img src="/cow-logo.png" alt="Cow" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                      </div>
                      <div>
                        <div className="cow-card-name" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <span style={{ fontWeight: 800, color: 'var(--text-primary)' }}>
                            #{cow.device_id} - {cow.name}
                          </span>
                        </div>
                        <div className="cow-card-tag" style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.1rem' }}>
                          <strong style={{ color: isAws ? '#FBBF24' : 'var(--text-primary)' }}>
                            {isAws ? 'AWS COLLAR' : 'GATEWAYLESS'}
                          </strong>
                          {' • '}TAG: <span style={{ color: 'var(--text-primary)' }}>{cow.tagNumber}</span>
                          {cow.breed && cow.breed !== 'CowNeck Collar Cow' ? ` • ${cow.breed}` : ''}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.35rem' }}>
                      <span className={`health-badge ${(cow.isStale || (cow.monitoredHoursToday || 0) === 0 || cow.health_risk_decision === 'NO_DATA') ? 'NO_DATA' : (cow.health_risk_decision || 'HEALTHY')}`}>
                        {(cow.isStale || (cow.monitoredHoursToday || 0) === 0 || cow.health_risk_decision === 'NO_DATA') ? 'NO DATA' : (cow.health_risk_decision || 'HEALTHY').replace('_', ' ')}
                      </span>
                      {isAws ? (
                        <span className="badge-source aws">
                          <i className="fa-solid fa-cloud"></i> AWS Cloud
                        </span>
                      ) : (
                        <span className="badge-source db">
                          <i className="fa-solid fa-database"></i> Gatewayless
                        </span>
                      )}
                    </div>
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
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                        {(cow.ruminationHoursToday || 0) > 0 ? 'Rumination' : ((cow.movingHoursToday || 0) > 0 ? 'Active Walk' : ((cow.feedingHoursToday || 0) > 0 ? 'Feeding' : 'Rumination'))}
                      </div>
                      <div style={{ fontSize: '1rem', fontWeight: 800, color: (cow.ruminationHoursToday || 0) > 0 ? 'var(--accent-sky)' : 'var(--accent-amber)', marginTop: '0.1rem', fontFamily: 'var(--font-display)' }}>
                        {formatHours(cow.ruminationHoursToday || cow.movingHoursToday || cow.feedingHoursToday || 0)}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                        {(cow.lyingHoursToday || 0) > 0 ? 'Total Rest' : ((cow.monitoredHoursToday || 0) > 0 ? 'Monitored' : 'Total Rest')}
                      </div>
                      <div style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--accent-purple)', marginTop: '0.1rem', fontFamily: 'var(--font-display)' }}>
                        {formatHours(cow.lyingHoursToday || cow.monitoredHoursToday || 0)}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Estrus Prob</div>
                      <div style={{ fontSize: '1rem', fontWeight: 800, color: (cow.estrusProbability || 0) > 50 ? 'var(--accent-rose)' : 'var(--accent-emerald)', marginTop: '0.1rem', fontFamily: 'var(--font-display)' }}>
                        {cow.estrusProbability || 0}%
                      </div>
                    </div>
                  </div>
                </div>

                {/* Card Action Buttons */}
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
                  <button 
                    className="btn btn-primary" 
                    onClick={() => onSelectCow(cow.id)} 
                    style={{ 
                      flex: 1.2, 
                      justifyContent: 'center', 
                      height: '36px', 
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      background: isAws ? 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)' : undefined,
                      border: isAws ? 'none' : undefined,
                      color: isAws ? '#000' : undefined,
                      boxShadow: isAws ? '0 2px 8px rgba(245, 158, 11, 0.35)' : undefined
                    }}
                  >
                    <i className="fa-solid fa-crosshairs"></i> MONITOR {isAws ? `AWS #${cow.device_id}` : `NODE #${cow.device_id}`}
                  </button>
                  <button 
                    className="btn" 
                    onClick={() => handleOpenEditModal(cow)} 
                    title="Change or edit tag registry for this device"
                    style={{ 
                      flex: 0.9, 
                      justifyContent: 'center', 
                      height: '36px', 
                      fontSize: '0.75rem',
                      background: 'rgba(255, 255, 255, 0.05)',
                      border: isAws ? '1px solid rgba(245, 158, 11, 0.4)' : '1px solid rgba(16, 185, 129, 0.4)',
                      color: isAws ? '#FBBF24' : '#34D399',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer'
                    }}
                  >
                    <i className="fa-solid fa-pen-to-square"></i> EDIT TAG
                  </button>
                </div>
              </div>
            );
          })
        ) : (
          /* Redesigned Glassmorphic Empty State */
          <div className="glass-panel" style={{ gridColumn: '1 / -1', padding: '3.5rem 2rem', textAlign: 'center', borderRadius: '16px', border: '1px dashed var(--border-medium)' }}>
            <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'rgba(255, 255, 255, 0.05)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.75rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
              {sourceFilter === 'aws_api' ? <i className="fa-solid fa-cloud" style={{ color: '#FBBF24' }}></i> : <i className="fa-solid fa-filter"></i>}
            </div>
            <h3 style={{ color: 'var(--text-primary)', fontWeight: 800, fontSize: '1.15rem', marginBottom: '0.4rem', fontFamily: 'var(--font-display)' }}>
              {sourceFilter === 'aws_api' ? 'No AWS Cloud IoT Nodes Matched' : 'No Cattle Nodes Found'}
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', maxWidth: '440px', margin: '0 auto 1.25rem' }}>
              {sourceFilter === 'aws_api' 
                ? 'No AWS Cloud collars matched your active search query or health state filter.' 
                : 'No devices found matching your current filter settings. Reset filters to view all monitored herd cattle.'}
            </p>
            <button 
              className="btn btn-primary"
              onClick={() => { setSearchTerm(''); setSourceFilter('ALL'); setHealthFilter('ALL'); }}
              style={{ margin: '0 auto', fontSize: '0.8rem', padding: '0.5rem 1.25rem' }}
            >
              <i className="fa-solid fa-rotate-left"></i> Reset All Filters
            </button>
          </div>
        )}
      </div>

      {/* Dynamic Tag Registry Modal */}
      {isModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(5, 10, 20, 0.75)',
          backdropFilter: 'blur(8px)',
          zIndex: 9999,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '1rem'
        }}>
          <div style={{
            background: 'var(--bg-surface, #0f172a)',
            border: '1px solid var(--border-medium, #334155)',
            borderRadius: '12px',
            width: '100%',
            maxWidth: '520px',
            boxShadow: '0 20px 50px rgba(0, 0, 0, 0.5)',
            overflow: 'hidden'
          }}>
            {/* Modal Header */}
            <div style={{
              padding: '1.25rem 1.5rem',
              borderBottom: '1px solid var(--border-subtle, #1e293b)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: 'linear-gradient(to right, rgba(16, 185, 129, 0.08), rgba(6, 182, 212, 0.08))'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <div style={{
                  width: '34px',
                  height: '34px',
                  borderRadius: '8px',
                  background: 'rgba(16, 185, 129, 0.2)',
                  color: '#10b981',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <i className="fa-solid fa-tag"></i>
                </div>
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
                    {tagForm.device_id ? `Edit Tag Registry: Device #${tagForm.device_id}` : 'Register New Cow Device'}
                  </h3>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0, marginTop: '2px' }}>
                    Dynamic metadata mapping stored in PostgreSQL TagRegistry
                  </p>
                </div>
              </div>
              <button 
                onClick={() => setIsModalOpen(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.1rem' }}
              >
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>

            {/* Modal Body / Form */}
            <form onSubmit={handleSaveTag} style={{ padding: '1.5rem' }}>
              {statusMsg && (
                <div style={{
                  padding: '0.75rem 1rem',
                  borderRadius: '6px',
                  marginBottom: '1rem',
                  fontSize: '0.85rem',
                  background: statusMsg.type === 'error' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                  border: statusMsg.type === 'error' ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(16, 185, 129, 0.4)',
                  color: statusMsg.type === 'error' ? '#ef4444' : '#10b981',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}>
                  <i className={statusMsg.type === 'error' ? "fa-solid fa-triangle-exclamation" : "fa-solid fa-circle-check"}></i>
                  {statusMsg.text}
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase' }}>
                    Device ID <span style={{ color: '#ef4444' }}>*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 8, 17, 1"
                    className="search-input-box"
                    style={{ width: '100%', height: '38px' }}
                    value={tagForm.device_id}
                    onChange={(e) => setTagForm({ ...tagForm, device_id: e.target.value })}
                  />
                  <span style={{ fontSize: '0.675rem', color: 'var(--text-muted)' }}>Aws (1-8) or Gatewayless (17)</span>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase' }}>
                    Cow Name <span style={{ color: '#ef4444' }}>*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Kamdhenu, Gauri"
                    className="search-input-box"
                    style={{ width: '100%', height: '38px' }}
                    value={tagForm.name}
                    onChange={(e) => setTagForm({ ...tagForm, name: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase' }}>
                    Breed
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Gir, Sahiwal, Jersey"
                    className="search-input-box"
                    style={{ width: '100%', height: '38px' }}
                    value={tagForm.breed}
                    onChange={(e) => setTagForm({ ...tagForm, breed: e.target.value })}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase' }}>
                    Weight (kg)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. 450"
                    className="search-input-box"
                    style={{ width: '100%', height: '38px' }}
                    value={tagForm.weight}
                    onChange={(e) => setTagForm({ ...tagForm, weight: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase' }}>
                  Location / Pasture Zone
                </label>
                <input
                  type="text"
                  placeholder="e.g. Barn Alpha - Zone 4, Milking Shed"
                  className="search-input-box"
                  style={{ width: '100%', height: '38px' }}
                  value={tagForm.location}
                  onChange={(e) => setTagForm({ ...tagForm, location: e.target.value })}
                />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase' }}>
                  Notes / Description
                </label>
                <textarea
                  placeholder="Dynamic notes, lactation stage, health observations..."
                  className="search-input-box"
                  rows={2}
                  style={{ width: '100%', height: 'auto', resize: 'vertical', padding: '0.5rem 0.75rem' }}
                  value={tagForm.notes}
                  onChange={(e) => setTagForm({ ...tagForm, notes: e.target.value })}
                />
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button
                  type="button"
                  className="btn"
                  onClick={() => setIsModalOpen(false)}
                  style={{
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-muted)',
                    padding: '0 1rem',
                    height: '38px',
                    borderRadius: 'var(--radius-sm)'
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={submitting}
                  style={{
                    padding: '0 1.25rem',
                    height: '38px',
                    fontSize: '0.85rem',
                    fontWeight: 700,
                    gap: '0.5rem'
                  }}
                >
                  {submitting ? (
                    <><i className="fa-solid fa-spinner fa-spin"></i> SAVING...</>
                  ) : (
                    <><i className="fa-solid fa-floppy-disk"></i> SAVE TAG REGISTRY</>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
