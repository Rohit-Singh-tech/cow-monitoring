# Cow Health Monitoring System - Technical Project Summary & Latest Specifications

This document provides a comprehensive, production-aligned technical summary of the entire **Cow Health Monitoring System**. It reflects all latest architectural enhancements, dual-source telemetry integrations, dynamic data-driven algorithms, machine learning pipelines, and hardware specifications.

---

## 1. Machine Learning Engine (Backend)

The backend utilizes pre-trained machine learning models to decode raw 10 Hz $X, Y, Z$ accelerometer data into behavioral and physiological insights. The `MLModelManager` orchestrates these models as a RAM singleton process.

### Models & Extractors
*   **67-Dimensional Feature Extractor (`extract_67_features`)**:
    *   Takes raw $X, Y, Z$ arrays (80 samples @ 10 Hz = 8.0-second observation window) and computes 67 distinct statistical and frequency-domain features:
        *   **Axis-Specific (48 features)**: Mean, Std Dev, Variance, Min, Max, Range, Median, $Q_{25}$, $Q_{75}$, Absolute Mean, Energy ($\sum s_i^2$), Skewness, Kurtosis, Differential Mean ($\overline{\Delta s}$), Differential Std Dev, Differential Max.
        *   **Vector Magnitude ($\mathbf{Mag} = \sqrt{X^2 + Y^2 + Z^2}$) (10 features)**: Mean, Std, Var, Min, Max, Range, Median, $Q_{25}$, $Q_{75}$, Energy.
        *   **Dynamic Movement Jerk ($|\Delta \mathbf{Mag}|$) (4 features)**: Mean, Std, Max, Energy.
        *   **Global & Cross-Axial (5 features)**: Signal Magnitude Area (SMA), Cross-Axis Pearson Correlations ($r_{xy}, r_{xz}, r_{yz}$), and Histogram Shannon Entropy.
*   **Activity Classification Model (`activity_model.pkl`)**:
    *   **Architecture**: LightGBM Multi-Class Classifier trained on 889,376 rows (8,871 labeled windows).
    *   **Behavioral Classes (17 total)**: `RUS` (Ruminating), `REL` (Lying Rest), `RES` (Standing Rest), `MOV` (Walking/Active), `FEP` / `FED` / `FES` / `GRZ` (Feeding & Grazing), `DRN` (Drinking), `LCK` (Licking/Grooming), `URI` (Urinating), `DEF` (Defecating), `ATT` (Aggressive Head-Butting), `BMN` (Bellowing/Moaning), `SLT` (Salt Lick), `ETC` / `NAN` / `OTHER_ACTIVITY` (Unclassified Active).
*   **Estrus/Heat Detection Model (`heat_model.pkl`)**:
    *   **Architecture**: LightGBM Binary Classifier trained on 1,048,571 rows (10,484 labeled windows).
    *   **Alert Escalation**: Outputs continuous probability ($0.0 - 1.0$). Evaluated as **Normal** ($\le 0.40$), **Moderate** ($0.40 - 0.70$), or **High Heat Alert** ($> 0.70$).
*   **Anomaly Detection Model (`anomaly_model.pkl`)**:
    *   **Architecture**: Scikit-Learn Isolation Forest (Unsupervised) + Z-score feature deviation using `baseline_mean.pkl` and `baseline_std.pkl`.
    *   **Function**: Detects physical deviations (limping, trauma, sudden falls, weakness) outside learned healthy movement distributions.
*   **Health Risk Decision Logic**:
    *   Combines anomaly scoring, estrus probability, and rumination duration into three states: `HEALTHY`, `MONITOR`, or `HIGH_RISK`.

---

## 2. Hardware Specifications & Edge Protocol (Collar Node)

Developed in collaboration with **AWaDH Hub (IIT Ropar)**, **GADVASU**, and **NABARD**.

*   **Microcontroller / Radio**: Nordic Semiconductor `nRF52832` (32-bit ARM Cortex-M4 @ 64 MHz, BLE 5.0).
*   **Motion Sensor**: STMicroelectronics `LIS3DH` ultra-low power 3-axis accelerometer operating at 10 Hz (100 ms sampling period).
*   **Onboard Flash Memory**: 8 MB SPI Flash (Winbond W25Q64FV) configured as a circular overwrite ring buffer.
    *   **Capacity**: 32,768 telemetry packets (256 bytes per packet).
    *   **Offline Retention**: **~72.8 Hours (~3.03 Days)** of continuous 10 Hz raw motion logging.
*   **Battery & Power Equation**:
    *   Cell: 3.7V, 5400 mAh Li-Ion rechargeable battery.
    *   Average Current Draw: **98.16 µA (0.09816 mA)** under duty-cycled operation.
    *   Operational Lifespan: $5400\text{ mAh} / 0.09816\text{ mA} = 55,012\text{ Hours} \approx \mathbf{6.28\text{ Years}}$ (2,292 Days).
*   **256-Byte Binary Packet Frame Layout**:
    *   Header: 3 Bytes (Frame synchronization & packet type)
    *   XYZ Payload: 240 Bytes (80 acceleration samples $\times$ 3 axes @ 10 Hz)
    *   Original Packet ID: 2 Bytes (Recording sequence counter)
    *   Current Packet ID: 2 Bytes (Transmission counter)
    *   Footer: 1 Byte (Frame boundary verification)
    *   Reserved / Padding: 8 Bytes (Future expansion & word alignment)
*   **Knock-Knock BLE Security Commands**:
    *   Data Dump Trigger: `0x59 0x00 0xBB 0xCC`
    *   Flash Memory Reset Trigger: `0x59 0x00 0xFF 0xFF`

---

## 3. Dual-Source Telemetry Architecture & Latest Dynamic Algorithms

The platform unifies two independent data streams into a single standardized data contract:

### Telemetry Pipeline 1: Render Cloud Database (`render_db`)
*   **Flow**: BLE upload $\rightarrow$ Bulk POST $\rightarrow$ PostgreSQL tables (`datalogger_headers`, `datalogger_points`, `ml_inferences`, `daily_cow_summaries`).
*   **Strict Day-Boundary & Packet Gap Splitting (Latest Enhancement)**:
    *   In `/api/cow/{id}/activity-log`, packets are strictly partitioned when `ts.date() != last_ts.date()` or when consecutive packet timestamps exhibit a gap $> 120$ seconds.
    *   Durations and chronological boundaries are calculated from exact header timestamps and packet sequence IDs.
    *   **Result**: Eliminates historical leakage from previous days. For example, if a node recorded 1h 36m today, only today's sessions are accumulated, preventing yesterday's sessions from inflating today's totals.

### Telemetry Pipeline 2: AWS Cloud IoT Gateway API (`aws_api`)
*   **Flow**: Cellular/Gateway nodes forward telemetry to AWS Lambda (`CowNeck_API_Function?deviceid={id}&startdate={start}&enddate={end}`).
*   **Payload**: 240 string integers representing 80 sequential readings of $X, Y, Z$ at 10 Hz.
*   **Dynamic 7-Day Rolling Window (Latest Enhancement)**:
    *   Date calculation is 100% dynamic relative to UTC today (`datetime.now(timezone.utc).date()`). No hardcoded dates exist in the codebase.
    *   Dynamically rolls a continuous 7-day range, zero-padding missing historical days.
    *   Sub-second response times powered by the pre-computed `_AWS_DAILY_SUMMARIES` cache.
*   **Zero-Telemetry & Offline Device Handling (Latest Enhancement)**:
    *   When an AWS device has 0 telemetry for today (or data is stale $> 24$ hours), `monitoredHoursToday` is strictly set to `0.0`, `isStale: True`, and current activity reflects `NO DATA / OFFLINE`.
    *   The frontend cleanly renders empty states for the 24-hour donut chart and "Today (24 Hours)" log table instead of leaking yesterday's historical activities.
*   **Extended Timeouts & Snapshot Resilience (Device #8 Fix)**:
    *   HTTP timeouts increased to `(5, 15)` to handle slow upstream AWS responses without dropping connections.
    *   Responses are merged with `_LAST_VALID_LOGS` snapshot and prevent empty responses `[]` from poisoning the cache, ensuring all historical records (Sep 22 + Sep 23) remain continuously visible.

### Performance & Caching Layer (Latest Enhancement)
*   **Startup Pre-Warming (`prewarm_caches`)**:
    *   FastAPI `lifespan` automatically runs an asynchronous pre-warming routine at server startup.
    *   Pre-loads DB herd overview, default cow (17), and all enabled AWS devices (`AWS_ENABLED_DEVICE_IDS = ["8", "7", "9", "1", "3", "4", "5", "6"]`).
    *   Delivers instantaneous sub-15ms response times for all initial dashboard requests.
*   **Cache Management**:
    *   Dedicated endpoint `POST /api/aws/clear-cache` clears all in-memory caches and snapshots on demand.

---

## 4. API Endpoints

The backend is built with FastAPI and organized into modular routers:

### Ingestion & Machine Learning
*   `POST /api/v1/ingest/raw`: Bulk ingestion for datalogger BLE dumps. Persists headers and points; triggers background ML inference.
*   `POST /api/v1/ingest/packet`: Ingests a single 256-byte telemetry frame.
*   `POST /api/v1/ingest/predict`: Pure stateless ML inference endpoint. Accepts $X, Y, Z$ arrays, extracts 67 features, and returns classifications without DB write.

### Frontend Compatibility / Web Dashboard
*   `GET /api/cows`: Returns herd overview with daily rumination hours, current behavior, estrus alert badges, and source badges (`🗄️ RENDER DB` vs `☁️ AWS COLLAR`).
*   `GET /api/cow/{cow_id}/current`: Returns real-time telemetry buffer ($X, Y, Z$ waveforms at 10 Hz), current ML activity, confidence, anomaly score, and health risk.
*   `GET /api/cow/{cow_id}/7day`: Returns dynamic 7-day rolling window analytics: daily hours for Rumination, Feeding, Lying Rest, Moving, plus Health and Estrus indices.
*   `GET /api/cow/{cow_id}/activity-log`: Returns gapless 24-hour chronological activity transition table with accurate start/end timestamps, duration, confidence, and packet IDs.

### Hardware Control & Diagnostics
*   `POST /api/ble/trigger-dump`: Sends the BLE Knock-Knock data retrieval trigger (`0x5900BBCC`).
*   `POST /api/ble/trigger-reset`: Sends the BLE memory reset trigger (`0x5900FFFF`).
*   `POST /api/aws/clear-cache`: Clears all AWS telemetry caches and snapshots.

### Admin & Configuration
*   `POST /api/auth/login`: Authenticates administrator and returns a JWT token.
*   `GET` / `POST` / `DELETE /api/admin/users`: CRUD for admin users.
*   `POST` / `DELETE /api/admin/tags`: Maps physical IoT device hardware IDs (e.g. Node-17) to Cow IDs (e.g. Tag-17).
*   `GET /api/config/activities`: Returns global mapping of Activity Codes to human-readable names and UI hex colors.
*   `GET /health`: Health-check endpoint verifying DB connectivity and ML model loading in RAM.

---

## 5. Frontend Screens & Displayed Parameters

Built with **React 19**, **Vite 8**, **Chart.js**, and **TailwindCSS v4**:

### Global Elements
*   **Sidebar Navigation**: Sys Diagnostics, 7-Day Logs, Herd Overview, Hardware Specs, Node Directory, and Project Docs.
*   **Navbar**: Global target cow dropdown with source prefixes (`[☁️ AWS]` vs `[🗄️ DB]`), connection heartbeat badge, and theme toggler.

### Screen 1: System Diagnostics (`LiveCowMonitor.jsx`)
*   **Header Card**: Target node/tag ID, Health Risk Badge (`HEALTHY`, `MONITOR`, `HIGH_RISK`), current Activity state (e.g., `RUS - Ruminating`), and ML Confidence percentage.
*   **Critical Alert Banner**: High-priority alert triggered on estrus detection or acute kinematic anomaly.
*   **Telemetry KPI Tiles**:
    *   **Current Activity**: Real-time behavioral classification.
    *   **Rumination Total**: Sum of rumination for the current day (target 8–10 hours).
    *   **Lying Rest Hours**: Total rest duration for the current day.
    *   **Estrus Probability**: Real-time percentage indicator with color grading.
    *   **Packets Buffered**: Number of raw telemetry packets ingested in the current polling window.
    *   **Isolation Forest Score**: Numerical anomaly score representing kinematic deviation.
*   **Live Visualizations**:
    *   **Raw XYZ Motion Telemetry**: High-frequency (10 Hz) live streaming line chart plotting $X, Y, Z$ accelerometer values in real-time.
    *   **Behavior Distribution Donut**: 24-hour proportional time breakdown across activity classes with clean empty state for zero-telemetry days.

### Screen 2: 7-Day Activity Trends & Transition Logs (`Activity7Day.jsx`)
*   **7-Day Activity Time Allocation**: Stacked bar chart showing daily hours dedicated to Rumination, Lying, Feeding, and Movement over the dynamic past 7 days.
*   **Health Score & Estrus Index Trends**: Multi-axis line chart tracking composite Health Score (0–100) and Estrus Index (0–100) across the week.
*   **7-Day Average Distribution**: Summarized daily average hours per activity class (REL, RUS, FEP, MOV) over the week.
*   **Recorded Activity Transition Logs**:
    *   Chronological, gapless table for the current day.
    *   **Columns**: Log ID, Target Node, Start Time, End Time, Accurate Duration (in mins/hours), Activity Class, Category, Average Confidence (%), and SPI Packet ID boundaries.

### Screen 3: Herd Overview (`HerdOverview.jsx`)
*   **Source Filter**: Filter by `All Sources`, `🗄️ Render Database`, or `☁️ AWS Cloud Collars`.
*   **KPI Banners**: Total Monitored Cows, High-Risk Nodes, Heat Alerts Active, and Herd Average Rumination.
*   **Herd Roster Cards**: Node/Tag ID, Source Badge (`🗄️ RENDER DB` / `☁️ AWS COLLAR`), Live Status, Heartbeat timestamp, Current ML Inference, Health Status, and Battery Voltage.

### Screen 4: Hardware Specs & Diagnostics (`HardwareSpecs.jsx`)
*   **SPI Flash Ring Buffer Visualizer**: Radial gauge tracking memory utilization (Used vs. Total of 32,768 Packets).
*   **Battery Lifespan Calculator**: Interactive calculation based on 5400 mAh capacity and 98.16 µA draw (~6.28 Years).
*   **UART / BLE Terminal**: Live interactive terminal demonstrating data dump (`0x5900BBCC`) and flash reset (`0x5900FFFF`) protocol execution.

### Screen 5: Node Directory & Admin (`AdminPanel.jsx`)
*   **Tag Registry Management**: Pair physical collar hardware MAC addresses with farm livestock IDs.
*   **User Management**: Add and manage dashboard operator accounts.
*   **Activity Palette**: Inspect and manage activity codes, UI colors, and classification categories.

### Screen 6: Project Documentation (`ProjectDocs.jsx`)
*   In-app technical viewer detailing project background, 256-byte packet layouts, institutional partnerships, and system specifications.
