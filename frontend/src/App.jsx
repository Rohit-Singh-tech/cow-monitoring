import React, { useState, useEffect, useRef, useCallback } from 'react';
import Navbar from './components/Navbar';
import TabBar from './components/TabBar';
import LiveCowMonitor from './components/LiveCowMonitor';
import Activity7Day from './components/Activity7Day';
import HerdOverview from './components/HerdOverview';
import HardwareSpecs from './components/HardwareSpecs';
import ProjectDocs from './components/ProjectDocs';
import AdminPanel from './components/AdminPanel';
import Login from './components/Login';
import './index.css';

import { API_BASE } from './config/api';

// Network helper with explicit timeout to prevent requests from hanging indefinitely
const fetchWithTimeout = async (url, options = {}, timeoutMs = 8000) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(timeoutId);
    return res;
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
};

const DEFAULT_PRELOAD_COWS = [
  { id: "aws-13", device_id: "13", source: "aws_api", tagNumber: "AWS 13", name: "AWS 13", breed: "Collar Node", location: "Paddock AWS", weight: "480 kg", healthStatus: "NO_DATA", health_risk_decision: "NO_DATA", currentActivity: "NO_DATA", activityName: "Connecting...", ruminationHoursToday: 0.0, monitoredHoursToday: 0.0, isStale: false },
  { id: "aws-12", device_id: "12", source: "aws_api", tagNumber: "AWS 12", name: "AWS 12", breed: "Collar Node", location: "Paddock AWS", weight: "480 kg", healthStatus: "NO_DATA", health_risk_decision: "NO_DATA", currentActivity: "NO_DATA", activityName: "Connecting...", ruminationHoursToday: 0.0, monitoredHoursToday: 0.0, isStale: false },
  { id: "aws-11", device_id: "11", source: "aws_api", tagNumber: "AWS 11", name: "AWS 11", breed: "Collar Node", location: "Paddock AWS", weight: "480 kg", healthStatus: "NO_DATA", health_risk_decision: "NO_DATA", currentActivity: "NO_DATA", activityName: "Connecting...", ruminationHoursToday: 0.0, monitoredHoursToday: 0.0, isStale: false },
  { id: "aws-15", device_id: "15", source: "aws_api", tagNumber: "AWS 15", name: "AWS 15", breed: "Collar Node", location: "Paddock AWS", weight: "480 kg", healthStatus: "NO_DATA", health_risk_decision: "NO_DATA", currentActivity: "NO_DATA", activityName: "Connecting...", ruminationHoursToday: 0.0, monitoredHoursToday: 0.0, isStale: false },
  { id: "aws-14", device_id: "14", source: "aws_api", tagNumber: "AWS 14", name: "AWS 14", breed: "Collar Node", location: "Paddock AWS", weight: "480 kg", healthStatus: "NO_DATA", health_risk_decision: "NO_DATA", currentActivity: "NO_DATA", activityName: "Connecting...", ruminationHoursToday: 0.0, monitoredHoursToday: 0.0, isStale: false },
  { id: "19", device_id: "19", source: "gatewayless", tagNumber: "TAG-19", name: "Cow9", breed: "Jersey", location: "Mohali", weight: "525 kg", healthStatus: "NO_DATA", health_risk_decision: "NO_DATA", currentActivity: "NO_DATA", activityName: "No Data Today", ruminationHoursToday: 0.0, monitoredHoursToday: 0.0, isStale: true },
  { id: "17", device_id: "17", source: "gatewayless", tagNumber: "TAG-17", name: "Cow7", breed: "Sahiwal", location: "Rupnagar", weight: "300 kg", healthStatus: "NO_DATA", health_risk_decision: "NO_DATA", currentActivity: "NO_DATA", activityName: "No Data Today", ruminationHoursToday: 0.0, monitoredHoursToday: 0.0, isStale: true },
  { id: "13", device_id: "13", source: "gatewayless", tagNumber: "TAG-13", name: "Cow3", breed: "Holstein-Friesian", location: "Rupnagar", weight: "420 kg", healthStatus: "NO_DATA", health_risk_decision: "NO_DATA", currentActivity: "NO_DATA", activityName: "No Data Today", ruminationHoursToday: 0.0, monitoredHoursToday: 0.0, isStale: true },
  { id: "14", device_id: "14", source: "gatewayless", tagNumber: "TAG-14", name: "Cow4", breed: "Rathi", location: "Rupnagar", weight: "390 kg", healthStatus: "NO_DATA", health_risk_decision: "NO_DATA", currentActivity: "NO_DATA", activityName: "No Data Today", ruminationHoursToday: 0.0, monitoredHoursToday: 0.0, isStale: true }
];

const DEFAULT_PRELOAD_CURRENT = null;

const getInitialCachedCows = () => {
  try {
    const raw = localStorage.getItem('cached_cows');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch (_) {}
  return DEFAULT_PRELOAD_COWS;
};

export default function App() {
  const [cows, setCows] = useState(getInitialCachedCows);
  const [currentCowId, setCurrentCowId] = useState(() => {
    const initial = getInitialCachedCows();
    const active = initial.find(c => !c.isStale && ((c.monitoredHoursToday || 0) > 0 || (c.ruminationHoursToday || 0) > 0));
    return active ? active.id : (initial[0]?.id || 'aws-13');
  });
  const [activeTab, setActiveTab] = useState('live');
  const [currentData, setCurrentData] = useState(DEFAULT_PRELOAD_CURRENT);
  const [data7Day, setData7Day] = useState(null);
  const [logs, setLogs] = useState([]);
  const [is7DayLoading, setIs7DayLoading] = useState(false);
  const [refresh7DayTrigger, setRefresh7DayTrigger] = useState(0);
  const [accelBuffer, setAccelBuffer] = useState({ x: [], y: [], z: [], mag: [], labels: [] });
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('auth_token'));

  // Initialize sidebar open on desktop, closed on mobile
  const [isSidebarOpen, setIsSidebarOpen] = useState(typeof window !== 'undefined' ? window.innerWidth > 768 : true);
  const [theme, setTheme] = useState(localStorage.getItem('cow_theme') || 'dark');

  // Refs to prevent concurrent fetches and implement error backoff
  const cowsFetchingRef = useRef(false);
  const liveFetchingRef = useRef(false);
  const cowsErrorCountRef = useRef(0);
  const liveErrorCountRef = useRef(0);

  useEffect(() => {
    if (theme === 'light') {
      document.documentElement.classList.add('light-theme');
    } else {
      document.documentElement.classList.remove('light-theme');
    }
    localStorage.setItem('cow_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  // Helper to sync single cow update into cows array
  const syncCowIntoList = (cowData) => {
    if (!cowData) return;
    const targetId = String(cowData.cowId || cowData.id || '').trim();
    const targetSource = cowData.source ? String(cowData.source).toLowerCase() : '';
    const targetDevId = String(cowData.device_id || '').trim();
    const isAwsTarget = targetSource.includes('aws') || targetId.startsWith('aws-');

    setCows(prevCows => prevCows.map(c => {
      const cId = String(c.id || '').trim();
      const cSource = c.source ? String(c.source).toLowerCase() : '';
      const cDevId = String(c.device_id || '').trim();
      const isAwsC = cSource.includes('aws') || cId.startsWith('aws-');

      // Prevent cross-domain pollution: AWS devices must never match DB devices
      const sameDomain = (isAwsTarget === isAwsC);
      const matchesId = targetId && cId === targetId;
      const matchesDevice = sameDomain && targetDevId && cDevId && (targetDevId === cDevId);

      if (matchesId || matchesDevice) {
        const health = cowData.healthStatus || {};
        const act = cowData.currentActivity || {};
        const risk = health.health_risk_decision || c.health_risk_decision || 'HEALTHY';
        return {
          ...c,
          currentActivity: act.code || c.currentActivity,
          activityName: act.name || c.activityName,
          health_risk_decision: risk,
          healthStatus: (health.isHeatDetected || risk === 'HIGH_RISK') ? 'HIGH_RISK' : risk,
          ruminationHoursToday: health.ruminationHoursToday !== undefined ? health.ruminationHoursToday : c.ruminationHoursToday,
          monitoredHoursToday: health.monitoredHoursToday !== undefined ? health.monitoredHoursToday : c.monitoredHoursToday,
          lyingHoursToday: health.lyingHoursToday !== undefined ? health.lyingHoursToday : c.lyingHoursToday,
          feedingHoursToday: health.feedingHoursToday !== undefined ? health.feedingHoursToday : c.feedingHoursToday,
          movingHoursToday: health.movingHoursToday !== undefined ? health.movingHoursToday : c.movingHoursToday,
          estrusProbability: health.estrusProbabilityPercent !== undefined ? health.estrusProbabilityPercent : c.estrusProbability,
          isStale: cowData.isStale !== undefined ? cowData.isStale : c.isStale
        };
      }
      return c;
    }));
  };

  const fetchCows = useCallback(async () => {
    if (cowsFetchingRef.current) return;
    cowsFetchingRef.current = true;

    try {
      const res = await fetchWithTimeout(`${API_BASE}/api/cows`, {}, 45000);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const cowList = Array.isArray(data) ? data : (data.cows || []);
      if (cowList.length > 0) {
        setCows(cowList);
        try {
          localStorage.setItem('cached_cows', JSON.stringify(cowList));
        } catch (_) {}
        setCurrentCowId(prev => {
          if (!prev) {
            const activeCow = cowList.find(c => !c.isStale && ((c.monitoredHoursToday || 0) > 0 || (c.ruminationHoursToday || 0) > 0));
            return activeCow ? activeCow.id : cowList[0].id;
          }
          return prev;
        });
        cowsErrorCountRef.current = 0; // Reset on success
      }
    } catch (err) {
      console.error('Error fetching cows:', err);
      cowsErrorCountRef.current += 1;
    } finally {
      cowsFetchingRef.current = false;
    }
  }, []);

  // 1. Fetch cow list — dynamic interval: 20s when viewing directory, 45s otherwise
  //    with error backoff: quick retry on cold starts, back off on persistent errors
  useEffect(() => {
    if (!isAuthenticated) return;
    let isSubscribed = true;
    fetchCows();

    const getInterval = () => {
      const errorCount = cowsErrorCountRef.current;
      if (errorCount === 0) return activeTab === 'herd' ? 20000 : 45000;
      if (errorCount < 3) return 3000;             // Rapid 3s retry on cold start
      return Math.min(errorCount * 10000, 60000);  // Cap at 60s
    };

    let timeoutId;
    const scheduleNext = () => {
      timeoutId = setTimeout(async () => {
        await fetchCows();
        if (isSubscribed) scheduleNext();
      }, getInterval());
    };
    scheduleNext();

    return () => {
      isSubscribed = false;
      clearTimeout(timeoutId);
    };
  }, [isAuthenticated, activeTab]);


  // Load 7-day & logs on 7day tab with auto-polling every 20s so as collar packets
  // arrive every minute, today's transition logs and hours update automatically in real-time!
  useEffect(() => {
    if (!currentCowId || activeTab !== '7day' || !isAuthenticated) return;
    let isSubscribed = true;
    let retryTimerId = null;
    let pollTimerId = null;
    let retryCount = 0;

    const fetch7Day = async (isRetry = false) => {
      if (!isRetry && !data7Day) setIs7DayLoading(true);
      try {
        const [res7, resLogs] = await Promise.all([
          fetchWithTimeout(`${API_BASE}/api/cow/${currentCowId}/7day`, {}, 45000),
          fetchWithTimeout(`${API_BASE}/api/cow/${currentCowId}/activity-log?limit=250`, {}, 45000)
        ]);
        const [data7, dataLogs] = await Promise.all([res7.json(), resLogs.json()]);
        if (isSubscribed && data7.success) setData7Day(data7);
        if (isSubscribed && dataLogs.success) setLogs(dataLogs.logs || []);

        const isEmpty7Day = !data7.monitoredHours || data7.monitoredHours.every(h => h === 0);
        const isEmptyLogs = !dataLogs.logs || dataLogs.logs.length === 0;
        const isAwsDevice = String(currentCowId).startsWith('aws-');
        if (isAwsDevice && (isEmpty7Day || isEmptyLogs) && isSubscribed && retryCount < 4) {
          retryCount += 1;
          const delay = retryCount === 1 ? 2500 : (retryCount === 2 ? 5000 : (retryCount === 3 ? 8000 : 12000));
          retryTimerId = setTimeout(() => { if (isSubscribed) fetch7Day(true); }, delay);
        }
      } catch (err) {
        console.error('Error loading 7day data:', err);
      } finally {
        if (isSubscribed) setIs7DayLoading(false);
      }
    };

    fetch7Day();

    // Auto-poll every 20 seconds while on 7-day tab to seamlessly capture every-minute incoming packets
    pollTimerId = setInterval(() => {
      if (isSubscribed) fetch7Day(true);
    }, 20000);

    return () => {
      isSubscribed = false;
      if (retryTimerId) clearTimeout(retryTimerId);
      if (pollTimerId) clearInterval(pollTimerId);
    };
  }, [currentCowId, activeTab, isAuthenticated, refresh7DayTrigger]);

  // 2. Real-time Telemetry Stream Loop (rapid 12s interval with in-flight guard + error backoff)
  useEffect(() => {
    if (!currentCowId || activeTab !== 'live' || !isAuthenticated) return;

    let isSubscribed = true;
    const timeoutVal = 45000;

    const fetchLive = async () => {
      if (liveFetchingRef.current) return;
      liveFetchingRef.current = true;

      try {
        const res = await fetchWithTimeout(`${API_BASE}/api/cow/${currentCowId}/current`, {}, timeoutVal);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (isSubscribed && data.success) {
          if (data.accelBuffer) setAccelBuffer(data.accelBuffer);
          setCurrentData(data);
          syncCowIntoList(data);
          liveErrorCountRef.current = 0;
        }
      } catch (e) {
        liveErrorCountRef.current += 1;
      } finally {
        liveFetchingRef.current = false;
      }
    };

    // Rapid 12s live telemetry polling so new packets arriving every minute appear immediately
    const getInterval = () => {
      const errorCount = liveErrorCountRef.current;
      const baseInterval = 12000;
      if (errorCount === 0) return baseInterval;
      if (errorCount < 3) return 3000;              // Rapid 3s retry on cold start or hiccup
      return Math.min(errorCount * 10000, 60000);   // Cap at 60s
    };

    let timeoutId;
    const scheduleNext = () => {
      timeoutId = setTimeout(async () => {
        await fetchLive();
        if (isSubscribed) scheduleNext();
      }, getInterval());
    };
    fetchLive().then(() => {
      if (isSubscribed) scheduleNext();
    });

    return () => {
      isSubscribed = false;
      clearTimeout(timeoutId);
    };
  }, [currentCowId, activeTab, isAuthenticated]);

  const handleSelectCow = (id) => {
    setCurrentCowId(id);
    setData7Day(null);
    setLogs([]);
    liveErrorCountRef.current = 0; // Reset error backoff on cow switch

    // Seed immediately with existing metadata from cow list so the UI stays responsive
    const existingCow = cows.find(c => String(c.id) === String(id));
    if (existingCow) {
      setCurrentData(prev => ({
        ...(prev || {}),
        ...existingCow,
        cowId: existingCow.id,
        device_id: existingCow.device_id,
        cowName: existingCow.name,
        tagNumber: existingCow.tagNumber,
        breed: existingCow.breed,
        location: existingCow.location,
        weight: existingCow.weight,
        isStale: existingCow.isStale,
        currentActivity: { code: existingCow.currentActivity, name: existingCow.activityName || 'Standing Rest' },
        healthStatus: {
          monitoredHoursToday: existingCow.monitoredHoursToday || 0,
          ruminationHoursToday: existingCow.ruminationHoursToday || 0,
          lyingHoursToday: existingCow.lyingHoursToday || 0,
          feedingHoursToday: existingCow.feedingHoursToday || 0,
          movingHoursToday: existingCow.movingHoursToday || 0,
          estrusProbabilityPercent: existingCow.estrusProbability || 0,
          health_risk_decision: existingCow.health_risk_decision || existingCow.healthStatus || 'HEALTHY'
        }
      }));
    }
  };

  const handleTriggerDump = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ble/trigger-dump`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cowId: currentCowId })
      });
      const data = await res.json();
      if (data.success) {
        alert(`⚡ BLE Data Dump Completed for Cow #${currentData?.device_id || currentCowId}!\n2,500 packets replayed from SPI Flash.`);
        fetch(`${API_BASE}/api/cow/${currentCowId}/current`)
          .then(r => r.json())
          .then(d => {
            if (d.success) {
              setCurrentData(d);
              if (d.accelBuffer) setAccelBuffer(d.accelBuffer);
            }
          });
      }
    } catch (e) {
      alert('Failed to execute BLE Data Dump.');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('username');
    setIsAuthenticated(false);
  };

  if (!isAuthenticated) {
    return <Login onLogin={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="app-container">
      {/* Translucent Pastoral Cow Background Watermark */}
      <div className="pastoral-bg-watermark"></div>

      {/* Left Sidebar */}
      <TabBar
        activeTab={activeTab}
        onSelectTab={(tab) => { 
          setActiveTab(tab); 
          if (window.innerWidth <= 768) setIsSidebarOpen(false); 
        }}
        onLogout={handleLogout}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      {/* Main Content Column */}
      <div className="main-column">
        {/* Top Navbar */}
        <Navbar
          cows={cows}
          currentCowId={currentCowId}
          onSelectCow={handleSelectCow}
          onTriggerDump={handleTriggerDump}
          onToggleMenu={() => setIsSidebarOpen(prev => !prev)}
          isSidebarOpen={isSidebarOpen}
          theme={theme}
          onToggleTheme={toggleTheme}
        />

        {/* Scrollable Content */}
        <main className="main-content">
          {activeTab === 'live' && (
            <LiveCowMonitor
              currentData={currentData}
              accelBuffer={accelBuffer}
              theme={theme}
            />
          )}

          {activeTab === '7day' && (
            <Activity7Day
              data7Day={data7Day}
              logs={logs}
              cowId={currentCowId}
              theme={theme}
              isLoading={is7DayLoading}
              onRefresh={() => setRefresh7DayTrigger(prev => prev + 1)}
            />
          )}

          {activeTab === 'herd' && (
            <HerdOverview
              cows={cows}
              onSelectCow={(id) => {
                handleSelectCow(id);
                setActiveTab('live');
              }}
              onRefreshCows={fetchCows}
            />
          )}

          {activeTab === 'tag_registry' && (
            <AdminPanel onRefreshCows={fetchCows} />
          )}

          {activeTab === 'hardware' && (
            <HardwareSpecs
              currentCowId={currentCowId}
              currentData={currentData}
              onReloadData={(id) => {
                fetch(`${API_BASE}/api/cow/${id}/current`)
                  .then(r => r.json())
                  .then(d => {
                    if (d.success) {
                      setCurrentData(d);
                      if (d.accelBuffer) setAccelBuffer(d.accelBuffer);
                    }
                  });
              }}
            />
          )}

          {activeTab === 'docs' && (
            <ProjectDocs />
          )}
        </main>
      </div>
    </div>
  );
}
