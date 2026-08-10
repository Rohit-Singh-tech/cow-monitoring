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

  // 1. Fetch initial cow list
  useEffect(() => {
    if (!isAuthenticated) return;
    fetch(`${API_BASE}/api/cows`)
      .then(res => res.json())
      .then(data => {
        if (data.success && data.cows && data.cows.length > 0) {
          setCows(data.cows);
          if (!currentCowId) {
            setCurrentCowId(data.cows[0].id);
          }
        }
      })
      .catch(err => console.error('Error fetching cows:', err));
  }, [isAuthenticated]);

  useEffect(() => {
    if (!currentCowId || !isAuthenticated) return;
    let isSubscribed = true;

    const loadCowData = async (cowId) => {
      try {
        const resCurr = await fetch(`${API_BASE}/api/cow/${cowId}/current`);
        const dataCurr = await resCurr.json();
        if (isSubscribed && dataCurr.success) {
          setCurrentData(dataCurr);
          if (dataCurr.accelBuffer) setAccelBuffer(dataCurr.accelBuffer);
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

        const resLogs = await fetch(`${API_BASE}/api/cow/${currentCowId}/activity-log`);
        const dataLogs = await resLogs.json();
        if (dataLogs.success) setLogs(dataLogs.logs);
      } catch (err) {
        console.error('Error loading 7day data:', err);
      }
    };

    fetch7Day();
  }, [currentCowId, activeTab, isAuthenticated]);

  // 3. Real-time Telemetry Stream Loop (5s interval)
  useEffect(() => {
    if (!currentCowId || activeTab !== 'live' || !isAuthenticated) return;

    let isSubscribed = true;
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/cow/${currentCowId}/current`);
        const data = await res.json();
        if (isSubscribed && data.success) {
          if (data.accelBuffer) setAccelBuffer(data.accelBuffer);
          if (data.healthStatus) setCurrentData(data);
        }
      } catch (e) { }
    }, 600000);

    return () => {
      isSubscribed = false;
      clearInterval(timer);
    };
  }, [currentCowId, activeTab, isAuthenticated]);

  const handleSelectCow = (id) => {
    setCurrentCowId(id);
    setAccelBuffer({ x: [], y: [], z: [], mag: [], labels: [] });
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
        alert(`⚡ BLE Data Dump Completed for Cow #${currentCowId}!\n2,500 packets replayed from SPI Flash.`);
        // Manually refresh data
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

  if (!isAuthenticated) {
    return <Login onLogin={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="app-container">
      {/* Left Sidebar */}
      <TabBar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
      />

      {/* Main Content Column */}
      <div className="main-column">
        {/* Top Navbar */}
        <Navbar
          cows={cows}
          currentCowId={currentCowId}
          onSelectCow={handleSelectCow}
          onTriggerDump={handleTriggerDump}
        />

        {/* Scrollable Content */}
        <main className="main-content">
          {activeTab === 'live' && (
            <LiveCowMonitor
              currentData={currentData}
              accelBuffer={accelBuffer}
            />
          )}

          {activeTab === '7day' && (
            <Activity7Day
              data7Day={data7Day}
              logs={logs}
              cowId={currentCowId}
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
