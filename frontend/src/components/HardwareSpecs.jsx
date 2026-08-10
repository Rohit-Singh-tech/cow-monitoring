import React, { useState } from 'react';

const API_BASE = import.meta.env.MODE === 'production' ? 'https://cow-monitoring01.onrender.com' : '';

export default function HardwareSpecs({ currentCowId, currentData, onReloadData }) {
  const [terminalLogs, setTerminalLogs] = useState([
    { time: new Date().toLocaleTimeString(), text: '[SYSTEM INIT] Collar Node nRF52832 powered on. Entering BLE Scannable Beacon Mode.', type: 'warn' },
    { time: new Date().toLocaleTimeString(), text: '[LOG] Sampling LIS3DH accelerometer @ 10 Hz (100ms interval).', type: 'log' },
    { time: new Date().toLocaleTimeString(), text: '[LOG] SPI Flash Write Index: 14250 / 32768. Circular Ring Buffer ACTIVE.', type: 'log' }
  ]);

  const addTermLine = (text, type = 'log') => {
    setTerminalLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), text, type }]);
  };

  const handleSendDump = async () => {
    addTermLine('[BLE TRIGGER SENT] Broadcasting Data Dump Signature: 0x59 0x00 0xBB 0xCC...', 'sent');
    try {
      const res = await fetch(`${API_BASE}/api/ble/trigger-dump`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cowId: currentCowId })
      });
      const data = await res.json();
      if (data.success) {
        addTermLine('[NODE ACK] Knock-Knock Signature Verified! Switch to Data Replay Mode.', 'recv');
        addTermLine('[BLE REPLAY] Transmitting 2,500 SPI Flash Packets (640 KB) via Extended Advertising...', 'hex');
        addTermLine('[SYNC COMPLETE] Mobile database updated. Read Index advanced.', 'warn');
        if (onReloadData) onReloadData(currentCowId);
      }
    } catch (e) {
      addTermLine('[ERROR] Failed to communicate with BLE Node backend', 'warn');
    }
  };

  const handleSendReset = async () => {
    if (!window.confirm('⚠️ Are you sure you want to send Memory Reset Signature 0x59 0x00 0xFF 0xFF? This erases SPI Flash!')) return;

    addTermLine('[BLE RESET SENT] Broadcasting Reset Signature: 0x59 0x00 0xFF 0xFF...', 'sent');
    try {
      const res = await fetch(`${API_BASE}/api/ble/trigger-reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cowId: currentCowId })
      });
      const data = await res.json();
      if (data.success) {
        addTermLine('[NODE RESET ACK] Flash state sector erased. Write & Read Index reset to 0!', 'warn');
        if (onReloadData) onReloadData(currentCowId);
      }
    } catch (e) {
      addTermLine('[ERROR] Failed to send reset signature', 'warn');
    }
  };

  const hw = currentData?.deviceHardware || { flashUsagePercent: 43.5, flashUsedPackets: 14250, flashTotalPackets: 32768, batteryVoltage: 3.68, batteryPercent: 95 };

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '1.5rem' }}>
        
        {/* Ring Buffer graphic */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-hard-drive"></i>
              SPI Flash Circular Ring Buffer
            </div>
          </div>
          <div className="card-body" style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div className="ring-buffer-graphic">
              <div className="circle-ring">
                <div className="circle-ring-inner">
                  <div className="pct">{hw.flashUsagePercent}%</div>
                  <div className="lbl">Storage Filled</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    {hw.flashUsedPackets?.toLocaleString()} / {hw.flashTotalPackets?.toLocaleString()} Packets
                  </div>
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1.5rem', background: 'rgba(15, 23, 42, 0.6)', padding: '1.25rem', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem' }}>
              <div>
                <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Total Capacity:</div>
                <strong style={{ fontFamily: 'JetBrains Mono', color: 'var(--primary-cyan)' }}>8 MB (32,768 Pkts)</strong>
              </div>
              <div>
                <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Duration Limit:</div>
                <strong style={{ fontFamily: 'JetBrains Mono', color: 'var(--primary-emerald)' }}>72.8 Hrs (~3 Days)</strong>
              </div>
              <div>
                <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Packet Size:</div>
                <strong style={{ fontFamily: 'JetBrains Mono' }}>256 Bytes (240B XYZ)</strong>
              </div>
              <div>
                <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Overwrite Behavior:</div>
                <strong style={{ color: 'var(--warning-amber)' }}>Auto Wrap-around</strong>
              </div>
            </div>
          </div>
        </div>

        {/* Battery Math Calculation */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-battery-full"></i>
              Battery Life Equation
            </div>
          </div>
          <div className="card-body" style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div style={{ background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)', padding: '1.5rem', borderRadius: 'var(--radius-sm)', textAlign: 'center', marginBottom: '1.5rem' }}>
              <h4 style={{ color: 'var(--primary-emerald)', fontSize: '1.1rem', marginBottom: '0.5rem' }}>
                <i className="fa-solid fa-calculator"></i> Runtime = Capacity ÷ Current
              </h4>
              <p style={{ fontFamily: 'JetBrains Mono', fontSize: '0.95rem', color: '#a7f3d0', margin: 0 }}>
                5400 mAh ÷ 0.09816 mA = 55,012 Hours
              </p>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', background: 'rgba(15, 23, 42, 0.6)', padding: '1.25rem', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem' }}>
              <div>
                <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Battery Capacity:</div>
                <strong>5400 mAh (3.7V Li-Ion)</strong>
              </div>
              <div>
                <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Average Current:</div>
                <strong>98.16 µA (0.09816 mA)</strong>
              </div>
              <div>
                <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Total Runtime:</div>
                <strong>2,292 Days</strong>
              </div>
              <div>
                <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Estimated Lifespan:</div>
                <strong style={{ color: 'var(--primary-emerald)', fontSize: '1.1rem' }}>~6.28 Years</strong>
              </div>
            </div>
          </div>
        </div>

        {/* Microcontroller & Sensor */}
        <div className="glass-panel">
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-microchip"></i>
              Microcontroller & Sensor
            </div>
          </div>
          <div className="card-body">
            <ul style={{ fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: '1.8', listStyleType: 'none', padding: 0, margin: 0 }}>
              <li style={{ marginBottom: '0.75rem' }}><strong style={{ color: 'var(--primary-cyan)' }}>LIS3DH Accelerometer:</strong> 3-axis ultra low-power motion sensing @ 10 Hz.</li>
              <li style={{ marginBottom: '0.75rem' }}><strong style={{ color: 'var(--primary-cyan)' }}>nRF52832 MCU:</strong> ARM Cortex-M4 with integrated BLE radio.</li>
              <li><strong style={{ color: 'var(--primary-cyan)' }}>SPI Flash Memory:</strong> Non-volatile ring buffer storing 256-byte packets.</li>
            </ul>
          </div>
        </div>

        {/* Collar & Enclosure */}
        <div className="glass-panel">
          <div className="card-header-box">
            <div className="card-title">
              <i className="fa-solid fa-shield-cat"></i>
              Collar & Enclosure
            </div>
          </div>
          <div className="card-body">
            <ul style={{ fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: '1.8', listStyleType: 'none', padding: 0, margin: 0 }}>
              <li style={{ marginBottom: '0.75rem' }}><strong style={{ color: 'var(--accent-purple)' }}>Collar Mount:</strong> Lightweight, smooth-edged IP67 weather-resistant design.</li>
              <li style={{ marginBottom: '0.75rem' }}><strong style={{ color: 'var(--accent-purple)' }}>Animal Comfort:</strong> Rounded corners preventing friction or injury.</li>
              <li><strong style={{ color: 'var(--accent-purple)' }}>Gatewayless:</strong> Mobile app acts as temporary gateway on demand.</li>
            </ul>
          </div>
        </div>

      </div>
    </div>
  );
}
