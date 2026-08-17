import React from 'react';

export default function ProjectDocs() {
  return (
    <div className="glass-panel">
      <div className="card-header-box">
        <div className="card-title">
          <i className="fa-solid fa-book"></i>
          Gateway Less Cow Health Monitoring System - Technical Documentation Summary
        </div>
        <div className="meta-chip">AWaDH, IIT Ropar • GADVASU • NABARD</div>
      </div>
      <div className="card-body">
        
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem' }}>
          
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.65rem', fontFamily: 'var(--font-display)' }}>
              Project Background & Architecture Summary
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.825rem', marginBottom: '1.15rem', lineHeight: '1.6' }}>
              The Gateway-Less Cow Health Monitoring System is a specialized wearable livestock health platform designed to continuously log movement data from cattle and wirelessly transfer recorded packets on demand using Bluetooth Low Energy. The system operates autonomously without requiring expensive field gateway towers, making it ideal for rural farms, dairy units, and livestock pasture sites.
            </p>

            <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem', fontFamily: 'var(--font-display)' }}>
              256-Byte Data Packet Layout (Specification 6.5)
            </h4>
            
            <div className="table-responsive" style={{ marginBottom: '1.25rem' }}>
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Field Name</th>
                    <th>Size</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong style={{ color: 'var(--accent-cyan)' }}>Header</strong></td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>3 Bytes</td>
                    <td>Packet type & framing header</td>
                  </tr>
                  <tr>
                    <td><strong style={{ color: 'var(--accent-cyan)' }}>XYZ Payload</strong></td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>240 Bytes</td>
                    <td>80 acceleration samples × 3 axes (X, Y, Z @ 10 Hz)</td>
                  </tr>
                  <tr>
                    <td><strong style={{ color: 'var(--accent-cyan)' }}>Original Packet ID</strong></td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>2 Bytes</td>
                    <td>Sequence number when packet was recorded</td>
                  </tr>
                  <tr>
                    <td><strong style={{ color: 'var(--accent-cyan)' }}>Current Packet ID</strong></td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>2 Bytes</td>
                    <td>Transmitted sequence number placeholder</td>
                  </tr>
                  <tr>
                    <td><strong style={{ color: 'var(--accent-cyan)' }}>Footer</strong></td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>1 Byte</td>
                    <td>Boundary marker byte</td>
                  </tr>
                  <tr>
                    <td><strong style={{ color: 'var(--text-muted)' }}>Unused / Reserved</strong></td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>8 Bytes</td>
                    <td>Future metadata or alignment padding</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem', fontFamily: 'var(--font-display)' }}>
              Knock-Knock Security Signatures (Specification 6.8)
            </h4>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <div style={{ background: 'var(--accent-emerald-subtle)', border: '1px solid var(--accent-emerald-border)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-xs)', fontFamily: 'var(--font-mono)', fontSize: '0.775rem' }}>
                Data Dump Trigger: <strong style={{ color: 'var(--accent-emerald)' }}>0x59, 0x00, 0xBB, 0xCC</strong>
              </div>
              <div style={{ background: 'var(--accent-rose-subtle)', border: '1px solid var(--accent-rose-border)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-xs)', fontFamily: 'var(--font-mono)', fontSize: '0.775rem' }}>
                Memory Reset Trigger: <strong style={{ color: 'var(--accent-rose)' }}>0x59, 0x00, 0xFF, 0xFF</strong>
              </div>
            </div>

          </div>

          {/* Quick Specs Box */}
          <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <h4 style={{ fontSize: '0.775rem', fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', marginBottom: '0.85rem', fontFamily: 'var(--font-mono)' }}>
              SYSTEM SPECIFICATIONS SUMMARY
            </h4>

            <ul style={{ listStyle: 'none', fontSize: '0.775rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.55rem', padding: 0 }}>
              <li><strong style={{ color: 'var(--text-primary)' }}>Project Title:</strong> Gateway Less Cow Health Monitoring</li>
              <li><strong style={{ color: 'var(--text-primary)' }}>Lead Org:</strong> AWaDH Hub, IIT Ropar</li>
              <li><strong style={{ color: 'var(--text-primary)' }}>Sensor:</strong> LIS3DH 3-Axis Accelerometer</li>
              <li><strong style={{ color: 'var(--text-primary)' }}>Sampling:</strong> 10 Hz / 100 ms interval</li>
              <li><strong style={{ color: 'var(--text-primary)' }}>Microcontroller:</strong> nRF52832 BLE 5.0 SoC</li>
              <li><strong style={{ color: 'var(--text-primary)' }}>Local Memory:</strong> 8 MB SPI Flash (32,768 Packets)</li>
              <li><strong style={{ color: 'var(--text-primary)' }}>Offline Capacity:</strong> ~72.8 Hours continuous</li>
              <li><strong style={{ color: 'var(--text-primary)' }}>Battery Cell:</strong> 3.7V 5400 mAh Li-Ion</li>
              <li><strong style={{ color: 'var(--text-primary)' }}>Current Draw:</strong> 98.16 µA average</li>
              <li><strong style={{ color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)' }}>Estimated Lifespan:</strong> ~6.28 Years</li>
            </ul>
          </div>

        </div>

      </div>
    </div>
  );
}
