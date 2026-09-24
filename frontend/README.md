# 🐄 Cow Health Monitoring - Frontend Web Dashboard

This directory contains the user interface for the **Cow Health Monitoring System**, built with **React 19**, **Vite 8**, **Chart.js**, and **TailwindCSS v4**.

For complete project-wide documentation, system architecture, hardware specifications, machine learning pipeline, and API references, please see the [Master README.md](file:///d:/cow%20monitoring/README.md).

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
npm install
```

### 2. Run Local Development Server
```bash
npm run dev
```
The application will launch on **`http://localhost:5173`**. In development mode, Vite automatically proxies `/api/*` requests to the FastAPI backend running on `http://localhost:8000`.

### 3. Build for Production
```bash
npm run build
```
Generates an optimized static bundle in the `dist/` directory, ready for deployment to Render, Vercel, or AWS S3.

---

## 🖥️ Screen Overview

* **System Diagnostics (`LiveCowMonitor.jsx`)**: Real-time 10 Hz streaming motion canvas ($X, Y, Z$ waveforms), 24-hour behavioral donut chart, KPI tiles (Rumination, Lying Rest, Estrus %, Anomaly Score), active state indicator, and critical health banners.
* **7-Day Activity Trends (`Activity7Day.jsx`)**: Stacked daily time allocation charts (Rumination, Feeding, Lying, Walking), 7-day Health Score & Estrus probability trends, weekly baseline averages, and a gapless 24-hour chronological activity transition log table.
* **Herd Overview (`HerdOverview.jsx`)**: Farm-wide macro monitoring, dual-source filtering (`🗄️ Render Database` vs `☁️ AWS Cloud Collars`), high-risk node alerts, active heat alerts, and herd-wide rumination averages.
* **Hardware Specs & Diagnostics (`HardwareSpecs.jsx`)**: Visual ring buffer gauge (32,768 packet capacity), 6.28-year battery lifespan calculation, and an interactive BLE replay terminal.
* **Admin Panel (`AdminPanel.jsx`)**: Node tag registry, MAC address pairing, user management, and activity palette configuration.
* **Project Documentation (`ProjectDocs.jsx`)**: Built-in interactive technical reference and packet layout specifications.
