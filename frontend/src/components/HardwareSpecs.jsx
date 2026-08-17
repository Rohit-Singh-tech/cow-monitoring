import React, { useState } from 'react';

const API_BASE = import.meta.env.MODE === 'production' ? 'https://cow-monitoring01.onrender.com' : '';

export default function HardwareSpecs({ currentCowId, currentData, onReloadData }) {
  const [terminalLogs, setTerminalLogs] = useState([
    { time: new Date().toLocaleTimeString(), text: '[DEVICE INIT] Collar Node nRF52832 online. BLE Beacon active.', type: 'warn' },
    { time: new Date().toLocaleTimeString(), text: '[LOG] Sampling 3-axis accelerometer @ 10 Hz (100ms window).', type: 'log' },
    { time: new Date().toLocaleTimeString(), text: '[LOG] On-Collar SPI Flash: Ring Buffer active.', type: 'log' }
  ]);

  const addTermLine = (text, type = 'log') => {
    setTerminalLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), text, type }]);
  };

  const handleSendDump = async () => {
    addTermLine('[BLE SYNC] Sending wireless data retrieval request...', 'sent');
    try {
      const res = await fetch(`${API_BASE}/api/ble/trigger-dump`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cowId: currentCowId })
      });
      const data = await res.json();
      if (data.success) {
        addTermLine('[ACK] Collar acknowledged! Streaming stored packets via BLE...', 'recv');
        addTermLine('[SYNC COMPLETE] Farm database updated with replayed readings.', 'warn');
        if (onReloadData) onReloadData(currentCowId);
      }
    } catch (e) {
      addTermLine('[ERROR] Communication with collar node failed.', 'warn');
    }
  };

  const handleSendReset = async () => {
    if (!window.confirm('⚠️ Are you sure you want to clear on-collar flash storage for this node?')) return;

    addTermLine('[RESET] Sending memory clear command...', 'sent');
    try {
      const res = await fetch(`${API_BASE}/api/ble/trigger-reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cowId: currentCowId })
      });
      const data = await res.json();
      if (data.success) {
        addTermLine('[ACK] Flash storage buffer reset to index 0.', 'warn');
        if (onReloadData) onReloadData(currentCowId);
      }
    } catch (e) {
      addTermLine('[ERROR] Failed to send reset signal.', 'warn');
    }
  };

  const hw = currentData?.deviceHardware || { flashUsagePercent: 43.5, flashUsedPackets: 14250, flashTotalPackets: 32768, batteryVoltage: 3.68, batteryPercent: 95 };

  return (
    <div>
      <div style={{ marginBottom: '1.25rem' }}>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', fontFamily: 'var(--font-display)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <i className="fa-solid fa-microchip" style={{ color: 'var(--accent-sky)' }}></i>
          HARDWARE SPECIFICATIONS & DIAGNOSTICS
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.825rem', marginTop: '0.15rem' }}>
          Gateway-less edge architecture, battery equations, and BLE memory specifications (AWaDH IIT Ropar).
        </p>
      </div>

      <div className="grid-2col">
        
        {/* Ring Buffer Graphic & Card */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-hard-drive" style={{ color: 'var(--accent-sky)' }}></i>
              ONBOARD SPI FLASH RING BUFFER
            </div>
            <span className="code-badge" style={{ background: 'rgba(6, 182, 212, 0.25)', color: 'var(--accent-cyan)', border: '1px solid rgba(56, 189, 248, 0.4)' }}>SPI Ring Buffer</span>
          </div>
          <div className="card-body" style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '1rem 0' }}>
              <div style={{ width: '130px', height: '130px', borderRadius: '50%', border: '8px solid rgba(56, 189, 248, 0.2)', borderTopColor: 'var(--accent-sky)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{hw.flashUsagePercent}%</div>
                <div style={{ fontSize: '0.7rem', color: 'var(--accent-sky)', fontWeight: 800, fontFamily: 'var(--font-mono)' }}>BUFFER OCCUPIED</div>
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.75rem', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                {hw.flashUsedPackets?.toLocaleString()} / {hw.flashTotalPackets?.toLocaleString()} Packets
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', background: 'var(--bg-elevated)', padding: '0.95rem 1.15rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.825rem' }}>
              <div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.725rem', fontWeight: 700 }}>Total Capacity:</div>
                <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-sky)', fontSize: '0.9rem' }}>8 MB (32,768 Packets)</strong>
              </div>
              <div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.725rem', fontWeight: 700 }}>Offline Retention:</div>
                <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-emerald)', fontSize: '0.9rem' }}>72.8 Hours (~3 Days)</strong>
              </div>
              <div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.725rem', fontWeight: 700 }}>Packet Format:</div>
                <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>256 Bytes (240B XYZ)</strong>
              </div>
              <div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.725rem', fontWeight: 700 }}>Buffer Policy:</div>
                <strong style={{ color: 'var(--accent-amber)', fontFamily: 'var(--font-mono)' }}>Circular Overwrite</strong>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.65rem', marginTop: '1rem' }}>
              <button className="btn btn-primary" onClick={handleSendDump} style={{ flex: 1, height: '36px' }}>
                <i className="fa-solid fa-cloud-arrow-down"></i> TRIGGER DUMP (0x5900BBCC)
              </button>
              <button className="btn btn-danger" onClick={handleSendReset} style={{ flex: 1, height: '36px' }}>
                <i className="fa-solid fa-rotate-left"></i> RESET BUFFER (0x5900FFFF)
              </button>
            </div>
          </div>
        </div>

        {/* Battery Estimation */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-battery-full" style={{ color: 'var(--accent-emerald)' }}></i>
              BATTERY LIFESPAN CALCULATION
            </div>
            <span className="code-badge" style={{ background: 'rgba(16, 185, 129, 0.25)', color: 'var(--accent-emerald)', border: '1px solid rgba(52, 211, 153, 0.4)' }}>{hw.batteryPercent}% ({hw.batteryVoltage}V)</span>
          </div>
          <div className="card-body" style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', padding: '1rem', borderRadius: 'var(--radius-sm)', textAlign: 'center', marginBottom: '0.85rem' }}>
              <h4 style={{ color: 'var(--accent-emerald)', fontSize: '0.9rem', fontWeight: 800, marginBottom: '0.25rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.45rem', fontFamily: 'var(--font-mono)' }}>
                <i className="fa-solid fa-calculator"></i> Runtime = Cell Capacity / Average Current
              </h4>
              <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                5400 mAh / 0.09816 mA = 55,012 Hours
              </p>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', background: 'var(--bg-elevated)', padding: '0.95rem 1.15rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.825rem' }}>
              <div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.725rem', fontWeight: 700 }}>Li-Ion Capacity:</div>
                <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>5400 mAh (3.7V)</strong>
              </div>
              <div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.725rem', fontWeight: 700 }}>Average Current Draw:</div>
                <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>98.16 µA (0.098 mA)</strong>
              </div>
              <div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.725rem', fontWeight: 700 }}>Operational Days:</div>
                <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>2,292 Days</strong>
              </div>
              <div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.725rem', fontWeight: 700 }}>Estimated Lifespan:</div>
                <strong style={{ color: 'var(--accent-emerald)', fontSize: '1rem', fontFamily: 'var(--font-mono)', fontWeight: 800 }}>~6.28 Years</strong>
              </div>
            </div>

            {/* Diagnostic Terminal */}
            <div style={{ marginTop: '0.95rem' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-primary)', fontWeight: 800, textTransform: 'uppercase', marginBottom: '0.35rem', fontFamily: 'var(--font-mono)' }}>
                UART / BLE REPLAY LOG TERMINAL
              </div>
              <div className="terminal-box">
                {terminalLogs.map((tl, i) => (
                  <div key={i} className={`terminal-line ${tl.type}`}>
                    <span style={{ color: 'var(--text-muted)', marginRight: '0.4rem', fontWeight: 600 }}>[{tl.time}]</span>
                    {tl.text}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Microcontroller & Sensor */}
        <div className="glass-panel">
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-microchip" style={{ color: 'var(--accent-sky)' }}></i>
              MICROCONTROLLER & SENSOR SPECS
            </div>
          </div>
          <div className="card-body">
            <ul style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.8', listStyleType: 'none', padding: 0, margin: 0, fontWeight: 500 }}>
              <li style={{ marginBottom: '0.6rem' }}><strong style={{ color: 'var(--text-primary)' }}>LIS3DH Accelerometer:</strong> Ultra low-power 3-axis motion sampling @ 10 Hz.</li>
              <li style={{ marginBottom: '0.6rem' }}><strong style={{ color: 'var(--text-primary)' }}>nRF52832 SoC:</strong> ARM Cortex-M4 with integrated BLE 5.0 radio transceiver.</li>
              <li><strong style={{ color: 'var(--text-primary)' }}>SPI Flash Storage:</strong> Non-volatile memory holding 256-byte telemetry chunks.</li>
            </ul>
          </div>
        </div>

        {/* Enclosure */}
        <div className="glass-panel">
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-shield-halved" style={{ color: 'var(--accent-emerald)' }}></i>
              PHYSICAL ENCLOSURE & PROTOCOLS
            </div>
          </div>
          <div className="card-body">
            <ul style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.8', listStyleType: 'none', padding: 0, margin: 0, fontWeight: 500 }}>
              <li style={{ marginBottom: '0.6rem' }}><strong style={{ color: 'var(--text-primary)' }}>IP67 Enclosure:</strong> Ruggedized, moisture and dirt sealed housing for cattle pasture.</li>
              <li style={{ marginBottom: '0.6rem' }}><strong style={{ color: 'var(--text-primary)' }}>Weight & Ergonomics:</strong> Lightweight neck harness causing zero bovine irritation.</li>
              <li><strong style={{ color: 'var(--text-primary)' }}>BLE 5.0 Wireless:</strong> High throughput burst transfers on demand.</li>
            </ul>
          </div>
        </div>

      </div>
    </div>
  );
}
