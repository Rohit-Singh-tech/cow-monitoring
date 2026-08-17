import React, { useState, useEffect, useRef } from 'react';
import Navbar from './components/Navbar';
import TabBar from './components/TabBar';
import LiveCowMonitor from './components/LiveCowMonitor';
import Activity7Day from './components/Activity7Day';
import HerdOverview from './components/HerdOverview';
import HardwareSpecs from './components/HardwareSpecs';
import ProjectDocs from './components/ProjectDocs';
import Login from './components/Login';
import './index.css';

const API_BASE = import.meta.env.MODE === 'production' ? 'https://cow-monitoring01.onrender.com' : '';

export default function App() {
  const [cows, setCows] = useState([]);
  const [currentCowId, setCurrentCowId] = useState('');
  const [activeTab, setActiveTab] = useState('live');
  const [currentData, setCurrentData] = useState(null);
  const [data7Day, setData7Day] = useState(null);
  const [logs, setLogs] = useState([]);
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

  // 1. Fetch cow list — poll every 60s (cow list rarely changes)
  //    with error backoff: wait longer on consecutive failures
  useEffect(() => {
    if (!isAuthenticated) return;
    let isSubscribed = true;

    const fetchCows = async () => {
      // Skip if a fetch is already in-flight
      if (cowsFetchingRef.current) return;
      cowsFetchingRef.current = true;

      try {
        const res = await fetch(`${API_BASE}/api/cows`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (isSubscribed && data.success && data.cows && data.cows.length > 0) {
          setCows(data.cows);
          setCurrentCowId(prev => {
            if (!prev) return data.cows[0].id;
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
    };

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

  // 2. Load individual cow data when cow selection changes
  useEffect(() => {
    if (!currentCowId || !isAuthenticated) return;
    let isSubscribed = true;

    const loadCowData = async (cowId) => {
      try {
        const resCurr = await fetch(`${API_BASE}/api/cow/${cowId}/current`);
        if (!resCurr.ok) throw new Error(`HTTP ${resCurr.status}`);
        const dataCurr = await resCurr.json();
        if (isSubscribed && dataCurr.success) {
          setCurrentData(dataCurr);
          if (dataCurr.accelBuffer) setAccelBuffer(dataCurr.accelBuffer);
          syncCowIntoList(dataCurr);
        }
      } catch (err) {
        console.error('Error loading cow data:', err);
      }
    };

    loadCowData(currentCowId);

    return () => {
      isSubscribed = false;
    };
  }, [currentCowId, isAuthenticated]);

  // Load 7-day & logs only if on 7day tab
  useEffect(() => {
    if (!currentCowId || activeTab !== '7day' || !isAuthenticated) return;

    const fetch7Day = async () => {
      try {
        const res7 = await fetch(`${API_BASE}/api/cow/${currentCowId}/7day`);
        const data7 = await res7.json();
        if (data7.success) setData7Day(data7);

        const resLogs = await fetch(`${API_BASE}/api/cow/${currentCowId}/activity-log?limit=50`);
        const dataLogs = await resLogs.json();
        if (dataLogs.success) setLogs(dataLogs.logs);
      } catch (err) {
        console.error('Error loading 7day data:', err);
      }
    };

    fetch7Day();
  }, [currentCowId, activeTab, isAuthenticated]);

  // 3. Real-time Telemetry Stream Loop (15s interval, with in-flight guard + error backoff)
  useEffect(() => {
    if (!currentCowId || activeTab !== 'live' || !isAuthenticated) return;

    let isSubscribed = true;

    const fetchLive = async () => {
      if (liveFetchingRef.current) return;
      liveFetchingRef.current = true;

      try {
        const res = await fetch(`${API_BASE}/api/cow/${currentCowId}/current`);
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

    // Dynamic interval: 15s normal, back off on errors
    const getInterval = () => {
      const errorCount = liveErrorCountRef.current;
      if (errorCount === 0) return 15000;       // 15s normal
      if (errorCount < 3) return 30000;          // 30s on first few errors
      return Math.min(errorCount * 30000, 300000); // Max 5 min
    };

    let timeoutId;
    const scheduleNext = () => {
      timeoutId = setTimeout(async () => {
        await fetchLive();
        if (isSubscribed) scheduleNext();
      }, getInterval());
    };
    scheduleNext();

    return () => {
      isSubscribed = false;
      clearTimeout(timeoutId);
    };
  }, [currentCowId, activeTab, isAuthenticated]);

  const handleSelectCow = (id) => {
    setCurrentCowId(id);
    setAccelBuffer({ x: [], y: [], z: [], mag: [], labels: [] });
    liveErrorCountRef.current = 0; // Reset error backoff on cow switch
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
            />
          )}

          {activeTab === 'herd' && (
            <HerdOverview
              cows={cows}
              onSelectCow={(id) => {
                handleSelectCow(id);
                setActiveTab('live');
              }}
            />
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
