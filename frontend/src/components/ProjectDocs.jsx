import React from 'react';

export default function ProjectDocs() {
  return (
    <div class="glass-panel">
      <div class="card-header-box">
        <div class="card-title">
          <i class="fa-solid fa-book"></i>
          Gateway Less Cow Health Monitoring System - Technical Documentation Summary
        </div>
        <div class="meta-chip">AWaDH, IIT Ropar • GADVASU • NABARD</div>
      </div>
      <div class="card-body">
        
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>
          
          <div>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--primary-emerald)', marginBottom: '0.75rem' }}>
              Project Background & Gatewayless Architecture
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1rem', lineHeight: '1.6' }}>
              The Gateway Less Cow Health Monitoring System is a wearable livestock health and activity monitoring system designed to continuously collect movement-related data from cattle and transmit recorded information on demand using Bluetooth Low Energy. The system operates without requiring a dedicated field gateway, making it highly suitable for rural farms, dairy units, and livestock research sites.
            </p>

            <h4 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
              256-Byte Data Packet Layout (Section 6.5)
            </h4>
            
            <div class="table-responsive" style={{ marginBottom: '1.5rem' }}>
              <table class="custom-table">
                <thead>
                  <tr>
                    <th>Field Name</th>
                    <th>Size</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong>Header</strong></td>
                    <td>3 Bytes</td>
                    <td>Packet type & framing header</td>
                  </tr>
                  <tr>
                    <td><strong>XYZ Payload</strong></td>
                    <td>240 Bytes</td>
                    <td>80 acceleration samples x 3 axes (X, Y, Z @ 10 Hz)</td>
                  </tr>
                  <tr>
                    <td><strong>Original Packet ID</strong></td>
                    <td>2 Bytes</td>
                    <td>Sequence number when packet was recorded</td>
                  </tr>
                  <tr>
                    <td><strong>Current Packet ID</strong></td>
                    <td>2 Bytes</td>
                    <td>Transmitted sequence number placeholder</td>
                  </tr>
                  <tr>
                    <td><strong>Footer</strong></td>
                    <td>1 Byte</td>
                    <td>Boundary marker byte</td>
                  </tr>
                  <tr>
                    <td><strong>Unused / Reserved</strong></td>
                    <td>8 Bytes</td>
                    <td>Future metadata or alignment padding</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <h4 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
              Knock-Knock Security Signatures (Section 6.8)
            </h4>
            <div style={{ display: 'flex', gap: '1rem' }}>
              <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)', fontFamily: 'JetBrains Mono', fontSize: '0.85rem' }}>
                Data Dump Trigger: <strong style={{ color: 'var(--primary-emerald)' }}>0x59, 0x00, 0xBB, 0xCC</strong>
              </div>
              <div style={{ background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.3)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)', fontFamily: 'JetBrains Mono', fontSize: '0.85rem' }}>
                Memory Reset Trigger: <strong style={{ color: 'var(--danger-rose)' }}>0x59, 0x00, 0xFF, 0xFF</strong>
              </div>
            </div>

          </div>

          {/* Quick Specs Box */}
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1.5rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-glass)' }}>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--primary-cyan)', textTransform: 'uppercase', marginBottom: '1rem' }}>
              System Summary Specifications
            </h4>

            <ul style={{ listStyle: 'none', fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <li><strong style={{ color: 'var(--color-white)' }}>Project Title:</strong> Gateway Less Cow Health Monitoring System</li>
              <li><strong style={{ color: 'var(--color-white)' }}>Lead Org:</strong> AWaDH Hub, IIT Ropar</li>
              <li><strong style={{ color: 'var(--color-white)' }}>Primary Sensor:</strong> LIS3DH 3-Axis Accelerometer</li>
              <li><strong style={{ color: 'var(--color-white)' }}>Sampling Rate:</strong> 10 Hz / 100 ms interval</li>
              <li><strong style={{ color: 'var(--color-white)' }}>Controller:</strong> nRF52832 BLE SoC</li>
              <li><strong style={{ color: 'var(--color-white)' }}>Local Storage:</strong> 8 MB SPI Flash (32,768 Packets)</li>
              <li><strong style={{ color: 'var(--color-white)' }}>Logging Capacity:</strong> ~72.8 Hours continuous</li>
              <li><strong style={{ color: 'var(--color-white)' }}>Battery:</strong> 3.7V 5400 mAh Li-Ion</li>
              <li><strong style={{ color: 'var(--color-white)' }}>Avg Current Draw:</strong> 98.16 µA</li>
              <li><strong style={{ color: 'var(--color-white)' }}>Calculated Runtime:</strong> ~6.28 Years</li>
            </ul>
          </div>

        </div>

      </div>
    </div>
  );
}
