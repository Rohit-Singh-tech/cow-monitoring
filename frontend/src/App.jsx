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

const getInitialCachedCows = () => {
  try {
    const raw = localStorage.getItem('cached_cows');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch (_) {}
  return [];
};

export default function App() {
  const [cows, setCows] = useState(getInitialCachedCows);
  const [currentCowId, setCurrentCowId] = useState(() => {
    const initial = getInitialCachedCows();
    const active = initial.find(c => !c.isStale && ((c.monitoredHoursToday || 0) > 0 || (c.ruminationHoursToday || 0) > 0));
    return active ? active.id : (initial[0]?.id || '');
  });
  const [activeTab, setActiveTab] = useState('live');
  const [currentData, setCurrentData] = useState(null);
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
    setCows(prevCows => prevCows.map(c => {
      if (String(c.id) === String(cowData.cowId || cowData.id) || String(c.device_id) === String(cowData.device_id)) {
        const health = cowData.healthStatus || {};
        const act = cowData.currentActivity || {};
        const risk = health.health_risk_decision || c.health_risk_decision || 'HEALTHY';
        return {
          ...c,
          currentActivity: act.code || c.currentActivity,
          health_risk_decision: risk,
          healthStatus: (health.isHeatDetected || risk === 'HIGH_RISK') ? 'HIGH_RISK' : risk,
          ruminationHoursToday: health.ruminationHoursToday !== undefined ? health.ruminationHoursToday : c.ruminationHoursToday,
          lyingHoursToday: health.lyingHoursToday !== undefined ? health.lyingHoursToday : c.lyingHoursToday,
          feedingHoursToday: health.feedingHoursToday !== undefined ? health.feedingHoursToday : c.feedingHoursToday,
          movingHoursToday: health.movingHoursToday !== undefined ? health.movingHoursToday : c.movingHoursToday,
          estrusProbability: health.estrusProbabilityPercent !== undefined ? health.estrusProbabilityPercent : c.estrusProbability
        };
      }
      return c;
    }));
  };

  const fetchCows = useCallback(async () => {
    if (cowsFetchingRef.current) return;
    cowsFetchingRef.current = true;

    try {
      const res = await fetchWithTimeout(`${API_BASE}/api/cows`, {}, 12000);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.success && data.cows && data.cows.length > 0) {
        setCows(data.cows);
        try {
          localStorage.setItem('cached_cows', JSON.stringify(data.cows));
        } catch (_) {}
        setCurrentCowId(prev => {
          if (!prev) {
            const activeCow = data.cows.find(c => !c.isStale && ((c.monitoredHoursToday || 0) > 0 || (c.ruminationHoursToday || 0) > 0));
            return activeCow ? activeCow.id : data.cows[0].id;
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

  // 1. Fetch cow list — poll every 60s (cow list rarely changes)
  //    with error backoff: wait longer on consecutive failures
  useEffect(() => {
    if (!isAuthenticated) return;
    let isSubscribed = true;
    fetchCows();

    // Dynamic interval: 60s normal, back off on errors (max 5 min)
    const getInterval = () => {
      const errorCount = cowsErrorCountRef.current;
      if (errorCount === 0) return 60000;     // 60s normal
      if (errorCount < 3) return 60000;        // Still 60s for first few errors
      return Math.min(errorCount * 30000, 300000); // 30s per error, max 5 min
    };

    // Use a recursive setTimeout for dynamic intervals
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
  }, [isAuthenticated]); // Removed activeTab — no need to refetch cow list on tab change


  // Load 7-day & logs only if on 7day tab — fetch both in parallel for speed
  // Uses stale-while-revalidate: backend returns instantly (empty on first cold call),
  // then auto-retries after 15s to get the background-computed data.
  useEffect(() => {
    if (!currentCowId || activeTab !== '7day' || !isAuthenticated) return;
    let isSubscribed = true;
    let retryTimerId = null;
    let retryCount = 0;

    const fetch7Day = async (isRetry = false) => {
      if (!isRetry) setIs7DayLoading(true);
      try {
        // Fire both requests simultaneously — don't wait for one before starting other
        const [res7, resLogs] = await Promise.all([
          fetchWithTimeout(`${API_BASE}/api/cow/${currentCowId}/7day`, {}, 45000),
          fetchWithTimeout(`${API_BASE}/api/cow/${currentCowId}/activity-log?limit=250`, {}, 45000)
        ]);
        const [data7, dataLogs] = await Promise.all([res7.json(), resLogs.json()]);
        if (data7.success) setData7Day(data7);
        if (dataLogs.success) setLogs(dataLogs.logs || []);

        // If backend returned preliminary baseline, smoothly retry with exponential backoff (up to 4 retries)
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
    return () => {
      isSubscribed = false;
      if (retryTimerId) clearTimeout(retryTimerId);
    };
  }, [currentCowId, activeTab, isAuthenticated, refresh7DayTrigger]);

  // 2. Real-time Telemetry Stream Loop (with in-flight guard + error backoff)
  useEffect(() => {
    if (!currentCowId || activeTab !== 'live' || !isAuthenticated) return;

    let isSubscribed = true;
    const isAws = currentCowId && String(currentCowId).startsWith('aws-');
    // Generous 45s timeout for AWS cloud API to prevent premature AbortError
    const timeoutVal = isAws ? 45000 : 15000;

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

    // Dynamic interval: AWS devices poll every 30s (cloud API), DB devices every 15s
    const getInterval = () => {
      const errorCount = liveErrorCountRef.current;
      const baseInterval = isAws ? 30000 : 15000;
      if (errorCount === 0) return baseInterval;
      if (errorCount < 3) return baseInterval * 2;
      return Math.min(errorCount * 30000, 300000); // Max 5 min
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
