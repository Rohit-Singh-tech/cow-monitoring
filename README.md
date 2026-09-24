# 🐄 Cow Health Monitoring System
### Autonomous Gateway-Less Livestock Telemetry, Edge Ring-Buffer Logging & Neural Diagnostic Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-19.2+-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-8.2+-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![LightGBM](https://img.shields.io/badge/LightGBM-4.0+-2E8B57?style=for-the-badge&logo=scikitlearn&logoColor=white)](https://lightgbm.readthedocs.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Render%20Cloud-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![AWS IoT](https://img.shields.io/badge/AWS-Lambda%20API-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)](https://aws.amazon.com/)

---

## 📌 Executive Summary

The **Cow Health Monitoring System** is a next-generation livestock precision health, behavior analysis, and estrus detection platform developed in partnership with:
* **AWaDH Hub (Agriculture & Water Technology Development Hub)**, Indian Institute of Technology (IIT) Ropar
* **GADVASU (Guru Angad Dev Veterinary and Animal Sciences University)**, Ludhiana
* **NABARD (National Bank for Agriculture and Rural Development)**

Traditional cattle monitoring relies on expensive, power-hungry continuous cellular links or long-range base stations (LoRaWAN gateways) installed throughout rural pastures. In remote or developing agricultural regions, cellular dead-zones and infrastructure costs frequently render standard IoT collars impractical.

This platform solves the infrastructure bottleneck with a **Gateway-Less Edge Datalogger Architecture**. Cattle collars record continuous high-frequency 3-axis motion to high-density onboard non-volatile SPI Flash memory. Data is harvested opportunistically via **Bluetooth Low Energy (BLE 5.0)** by farm workers using handheld smart devices or automated gates. The telematics are ingested by a dual-source backend cloud service (PostgreSQL & AWS Lambda), where an advanced **LightGBM machine learning pipeline** transforms raw accelerometer time-series into 17 granular behavioral classifications, estrus (heat) probabilities, and anomaly health metrics.

---

## 🏗️ System Architecture

```
                      ┌───────────────────────────────────────────────┐
                      │             COW WEARABLE COLLAR               │
                      │                                               │
                      │  ┌──────────────┐         ┌────────────────┐  │
                      │  │   LIS3DH     │ 10 Hz   │    nRF52832    │  │
                      │  │ 3-Axis Accel │────────▶│ ARM Cortex-M4  │  │
                      │  └──────────────┘ (XYZ)   │   SoC (BLE 5)  │  │
                      │                           └───────┬────────┘  │
                      │                                   │ SPI Bus   │
                      │                           ┌───────▼────────┐  │
                      │                           │ 8 MB SPI Flash │  │
                      │                           │  Ring Buffer   │  │
                      │                           │ (32,768 pkts)  │  │
                      │                           └────────────────┘  │
                      └───────────────────────┬───────────────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      │             DATA HARVEST / INGESTION          │
                      ▼                                               ▼
         ┌─────────────────────────┐                     ┌─────────────────────────┐
         │  Source 1: Render DB    │                     │   Source 2: AWS Cloud   │
         │  Opportunistic BLE Dump │                     │   Cellular / IoT Hub    │
         │  (Knock-Knock Protocol) │                     │   (Lambda API Gateway)  │
         └────────────┬────────────┘                     └────────────┬────────────┘
                      │                                               │
                      └───────────────────────┬───────────────────────┘
                                              ▼
                      ┌───────────────────────────────────────────────┐
                      │              FASTAPI BACKEND                  │
                      │                                               │
                      │  ┌─────────────────────────────────────────┐  │
                      │  │ 67-Dimensional Feature Extractor        │  │
                      │  │ (Stats, FFT Energy, SMA, Entropy)       │  │
                      │  └────────────────────┬────────────────────┘  │
                      │                       ▼                       │
                      │  ┌─────────────────────────────────────────┐  │
                      │  │ Machine Learning Inference Engine       │  │
                      │  │  • LightGBM Multi-Class Classifier     │  │
                      │  │  • LightGBM Estrus (Heat) Detector      │  │
                      │  │  • Isolation Forest Anomaly Detection   │  │
                      │  └────────────────────┬────────────────────┘  │
                      │                       ▼                       │
                      │  ┌─────────────────────────────────────────┐  │
                      │  │ High-Speed In-Memory Cache (Sub-15ms)   │  │
                      │  │ Dynamic 7-Day Rolling Window Aggregator │  │
                      │  └─────────────────────────────────────────┘  │
                      └───────────────────────┬───────────────────────┘
                                              │ REST API / JSON
                                              ▼
                      ┌───────────────────────────────────────────────┐
                      │           REACT 19 WEB DASHBOARD              │
                      │                                               │
                      │  • Live 10 Hz Real-Time Waveform Streaming    │
                      │  • 24-Hour Gapless Activity Transition Logs   │
                      │  • 7-Day Stacked Rumination/Feeding Profiles  │
                      │  • Estrus Probability & Health Risk Badges    │
                      │  • Hardware Diagnostics & BLE Memory Controls │
                      └───────────────────────────────────────────────┘
```

---

## ⚡ Hardware Specifications (Collar Edge Node)

| Specification Parameter | Value / Detail | Technical Rationale |
|:---|:---|:---|
| **Microcontroller / SoC** | Nordic Semiconductor `nRF52832` | 32-bit ARM Cortex-M4 CPU @ 64 MHz, 512 KB Flash, 64 KB RAM, 2.4 GHz multiprotocol radio supporting BLE 5.0. |
| **Motion Sensor** | STMicroelectronics `LIS3DH` | Ultra-low power tri-axial linear accelerometer, operating in Low Power Mode at 10 Hz sampling rate (100 ms period) across dynamic ranges $\pm 2g / \pm 4g$. |
| **Onboard Flash Memory** | Winbond 8 MB SPI Flash (64 Mbit) | Dedicated non-volatile memory managed as an automated circular overwrite ring buffer. Zero data loss during extended field separation. |
| **Storage Buffer Capacity** | **32,768 Packets** (256 bytes/packet) | Holds **72.8 Hours (~3.03 Days)** of continuous 10 Hz raw motion time-series data without requiring an active radio uplink. |
| **Power Supply** | 3.7V 5400 mAh Lithium-Ion cell | High-density rechargeable battery pack optimized for outdoor environmental extremes. |
| **Average Current Draw** | **98.16 µA (0.09816 mA)** | Ultra-deep sleep current between 10 Hz sample interrupts; burst radio transfers triggered only on BLE discovery. |
| **Theoretical Battery Life** | **~6.28 Years (2,292 Days)** | $\text{Lifespan} = \frac{5400\text{ mAh}}{0.09816\text{ mA}} = 55,012\text{ Operating Hours} \approx 6.28\text{ Years}$. |
| **Ingress Protection** | IP67 Hermetically Sealed | Waterproof, dustproof, and shock-resistant custom enclosure with chemical resistance against mud, manure, and rain. |
| **Animal Ergonomics** | Balanced Bovine Collar Harness | Lightweight, counter-weighted neck strap that remains stable without causing chafing, choking, or bovine distress. |

### 256-Byte Binary Packet Frame Layout (Specification 6.5)

Every 8.0-second observation window generates a standardized 256-byte binary payload:

```
+---------------+---------------------+-------------------+-------------------+----------+-------------------+
|  Header (3B)  |   XYZ Payload (240B)| Orig Pkt ID (2B)  | Curr Pkt ID (2B)  |Footer(1B)| Reserved/Pad (8B) |
+---------------+---------------------+-------------------+-------------------+----------+-------------------+
 0             2 3                 242 243             244 245             246 247    247 248               255
```

* **Header (3 Bytes)**: Packet synchronization marker (`0xAA, 0x55, ...`) and packet type descriptor.
* **XYZ Payload (240 Bytes)**: 80 acceleration readings $\times$ 3 axes ($X, Y, Z$) sampled at 10 Hz ($80 \times 3 \times 1\text{ byte} = 240\text{ bytes}$).
* **Original Packet ID (2 Bytes)**: 16-bit monotonic sequence counter assigned at the exact moment of flash logging.
* **Current Packet ID (2 Bytes)**: 16-bit transmission index used for packet reordering and deduplication during BLE transfer.
* **Footer (1 Byte)**: Boundary verification byte (`0xEE` or checksum).
* **Reserved / Padding (8 Bytes)**: Word-alignment padding reserved for future environmental sensing (e.g., skin temperature, ambient humidity).

### BLE "Knock-Knock" Security Protocol (Specification 6.8)

To preserve battery life, the collar's BLE radio acts primarily as an advertising beacon. Data streaming and memory resets require authorized 4-byte command signatures:

* **Data Dump Trigger**: `0x59 0x00 0xBB 0xCC` — Causes the collar to replay unread SPI Flash memory blocks sequentially over BLE characteristic notifications.
* **Flash Reset Trigger**: `0x59 0x00 0xFF 0xFF` — Clears the ring buffer pointers and resets the write index to block 0 after verification of successful farm database synchronization.

---

## 🧠 Machine Learning Engine

The system uses trained machine learning models housed in the singleton `MLModelManager` ([`backend/app/ml/model_loader.py`](file:///d:/cow%20monitoring/backend/app/ml/model_loader.py)).

### 1. 67-Dimensional Feature Extraction (`extract_67_features`)
Each 8-second window of 10 Hz accelerometer data ($X, Y, Z$) is converted into a 67-dimensional statistical and spectral feature vector:

$$\mathbf{Mag} = \sqrt{X^2 + Y^2 + Z^2} \quad , \quad \mathbf{Movement} = |\Delta \mathbf{Mag}|$$

* **Axis-Specific Features (16 per axis $\times$ 3 axes = 48 features)**:
  * Mean, Standard Deviation, Variance, Min, Max, Range, Median, 25th Percentile ($Q_{25}$), 75th Percentile ($Q_{75}$), Absolute Mean, Energy ($\sum s_i^2$), Skewness, Kurtosis, Differential Mean ($\overline{\Delta s}$), Differential Standard Deviation, Differential Max.
* **Vector Magnitude Features (10 features)**:
  * Mean, Std, Var, Min, Max, Range, Median, $Q_{25}$, $Q_{75}$, Energy.
* **Dynamic Movement Jerk Features (4 features)**:
  * Mean, Std, Max, Energy of movement differentials.
* **Global & Cross-Axial Features (5 features)**:
  * **Signal Magnitude Area (SMA)**: $\frac{1}{N} \sum_{i=1}^N (|X_i| + |Y_i| + |Z_i|)$
  * **Cross-Axis Pearson Correlations**: $r_{xy}, r_{xz}, r_{yz}$
  * **Histogram Shannon Entropy**: $-\sum p_i \log_2(p_i)$ over magnitude distribution bins.

### 2. Behavioral Classification Model (`activity_model.pkl`)
* **Algorithm**: LightGBM Multi-Class Gradient Boosting Decision Tree.
* **Training Corpus**: 889,376 raw rows partitioned into 8,871 validated behavioral windows.
* **17 Behavioral Classes Supported**:
  * `RUS`: Ruminating in standing position (primary metric for digestive health and rumination monitoring)
  * `REL`: Resting in lying position
  * `RES`: Resting in standing position
  * `MOV`: Moving / Active walking
  * `FEP` / `FED` / `FES` / `GRZ`: Feeding (pasture, trough, silage, or field grazing)
  * `DRN`: Drinking water
  * `LCK`: Licking / self-grooming
  * `URI`: Urinating
  * `DEF`: Defecating
  * `ATT`: Attacking / aggressive head-butting
  * `BMN`: Bellowing / vocalization
  * `SLT`: Salt lick intake
  * `ETC` / `NAN` / `OTHER_ACTIVITY`: Unclassified transitions

### 3. Estrus (Heat) Detection Model (`heat_model.pkl`)
* **Algorithm**: LightGBM Binary Classifier.
* **Training Corpus**: 1,048,571 raw rows partitioned into 10,484 labeled estrus observation windows.
* **Inference Output**: Real-time continuous probability score ($0.0 - 1.0$).
* **Alert Escalation Thresholds**:
  * **Normal**: Estrus Probability $\le 0.40$
  * **Moderate**: $0.40 <$ Estrus Probability $\le 0.70$
  * **High Heat Alert**: Estrus Probability $> 0.70$ (Triggers critical banner and herd-level alert)

### 4. Unsupervised Anomaly Detection (`anomaly_model.pkl`)
* **Algorithm**: Scikit-Learn Isolation Forest.
* **Function**: Computes path length deviations from nominal behavioral clusters.
* **Z-Score Deviation Engine**: Cross-references features with `baseline_mean.pkl` and `baseline_std.pkl`. Flags abnormal kinematic signatures (lameness, slipping, trauma, acute distress, or falling).
* **Heuristic Risk Decision**: Combines anomaly flags, estrus level, and daily rumination totals into a unified state: `HEALTHY`, `MONITOR`, or `HIGH_RISK`.

---

## 🌐 Dual-Source Telemetry Architecture

The system simultaneously ingests and federates data from two independent telemetry pipelines:

### Source 1: Render Cloud Database (`render_db`)
* **Mechanism**: On-demand BLE dump from collar SPI Flash to mobile tablet $\rightarrow$ bulk POST to backend.
* **Storage**: Managed PostgreSQL running on Render (with SQLite fallback for local testbeds).
* **Tables**:
  * `datalogger_headers`: Metadata, device ID, packet sequence ID, packet count, recording timestamp.
  * `datalogger_points`: High-resolution 10 Hz $X, Y, Z$ coordinates linked to headers via Foreign Key cascade.
  * `ml_inferences`: Stores pre-computed activity codes, confidence scores, estrus probability, and anomaly scores per header.
  * `daily_cow_summaries`: Daily rollups of monitored hours, rumination hours, resting hours, feeding hours, and heat occurrences.
  * `tag_registry`: Maps physical hardware MAC / node addresses (`Node-17`) to bovine animal identifiers (`Tag-17`).

### Source 2: AWS Cloud IoT Gateway API (`aws_api`)
* **Mechanism**: Direct wireless/cellular gateway nodes forward encrypted telemetry to an AWS Lambda API endpoint.
* **API Route**: `GET /default/CowNeck_API_Function?deviceid={id}&startdate={start}&enddate={end}`
* **Payload Structure**: 240 string integers representing 80 sequential readings of $X, Y, Z$ at 10 Hz.
* **Resilience Features**:
  * **Dual-Tier RAM Caching**: In-memory LRU cache (`_AWS_CACHE`, `_AWS_DAILY_SUMMARIES`, `_AWS_ACTIVITY_LOGS_CACHE`) delivering sub-15ms dashboard response times.
  * **Persistent Fallback Snapshot**: Stored in `backend/app/services/.aws_telemetry_snapshot.json` to ensure continuous offline development even during upstream AWS downtime.
  * **Dynamic 7-Day Rolling Window**: Automatically calculates date ranges relative to the current UTC day, zero-padding missing intervals and isolating single-day metrics without historical leakage.

---

## 📡 API Endpoint Reference

Interactive API documentation is generated automatically by FastAPI:
* **Interactive Swagger UI**: `http://localhost:8000/docs`
* **ReDoc Documentation**: `http://localhost:8000/redoc`

### Ingestion & Machine Learning
| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/api/v1/ingest/raw` | Bulk ingestion for datalogger BLE dumps. Persists headers and points; triggers background ML inference. |
| `POST` | `/api/v1/ingest/packet` | Ingests a single 256-byte telemetry frame. |
| `POST` | `/api/v1/ingest/predict` | Pure stateless ML inference endpoint. Accepts $X, Y, Z$ arrays, extracts 67 features, and returns classifications without writing to DB. |

### Cattle Monitoring (Frontend Compatibility)
| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/api/cows` | Returns herd overview with daily rumination hours, current behavior, estrus alert badges, and source flags (`🗄️ DB` vs `☁️ AWS`). |
| `GET` | `/api/cow/{cow_id}/current` | Live telemetry buffer ($X, Y, Z$ waveforms at 10 Hz), current ML activity, confidence, anomaly score, and health risk. |
| `GET` | `/api/cow/{cow_id}/7day` | 7-day rolling window analytics: daily hours for Rumination, Feeding, Lying Rest, Moving, plus Health and Estrus indices. |
| `GET` | `/api/cow/{cow_id}/activity-log` | Gapless 24-hour chronological activity transition table with accurate start/end timestamps, duration, confidence, and packet IDs. |

### Hardware Diagnostics & BLE Commands
| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/api/ble/trigger-dump` | Simulates the BLE Knock-Knock data harvest trigger (`0x5900BBCC`). |
| `POST` | `/api/ble/trigger-reset` | Simulates the BLE flash memory clear command (`0x5900FFFF`). |
| `POST` | `/api/aws/clear-cache` | Clears all in-memory AWS telemetry caches and snapshots. |

### Admin & Configuration
| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/api/auth/login` | Authenticates administrator credentials and returns a JWT session token. |
| `GET` / `POST` | `/api/admin/users` | List and register administrative dashboard operators. |
| `POST` / `DELETE`| `/api/admin/tags` | Associate physical hardware collar IDs with bovine animal ear tag IDs. |
| `GET` | `/api/config/activities` | Returns global activity color palette, icon metadata, and category mappings. |
| `GET` | `/health` | Cloud provider health-check verifying DB connectivity and ML model loading in RAM. |

---

## 💻 Frontend Dashboard Specification

Built with **React 19**, **Vite 8**, **Chart.js**, and **TailwindCSS v4**, the web interface provides specialized views:

### 1. Live System Diagnostics (`LiveCowMonitor.jsx`)
* **Real-Time 10 Hz Motion Canvas**: High-frequency streaming line chart plotting raw tri-axial accelerometer waveforms ($X, Y, Z$).
* **Active Status Banner**: Dynamic color-coded badge indicating health status (`HEALTHY`, `MONITOR`, `HIGH_RISK`) and current activity (e.g., `RUS - Ruminating`) with ML confidence percentage.
* **Critical Alerts**: Prominent warnings displayed on estrus detection or anomalous motion signatures.
* **KPI Telemetry Matrix**:
  * **Today's Rumination Total**: Real-time accumulator vs. standard target (8–10 hours/day).
  * **Lying Rest Total**: Daily rest accumulator.
  * **Estrus Probability**: Real-time percentage with threshold indicator.
  * **Isolation Forest Anomaly Score**: Real-time kinematic deviation index.
  * **Packets Buffered**: Real-time ingestion counter.
* **Behavior Distribution Donut**: 24-hour proportional time breakdown across all 17 activity classes.

### 2. 7-Day Activity Trends & Transition Logs (`Activity7Day.jsx`)
* **7-Day Stacked Activity Breakdown**: Daily hours allocated to Rumination, Lying, Feeding, and Movement over a rolling continuous 7-day window.
* **Health & Estrus Longitudinal Tracking**: Multi-axis trend line plotting composite Health Score (0–100) and Estrus Index (0–100) across the week.
* **Weekly Average Distribution**: Calculated daily averages for rumination, rest, and feeding baselines.
* **Gapless 24-Hour Activity Transition Logs**:
  * Displays chronological behavior blocks for the current day.
  * Columns: Log ID, Target Node, Start Time, End Time, Duration (hours/minutes), Activity Name, Category, Average Confidence (%), and SPI Packet Range.

### 3. Herd Overview (`HerdOverview.jsx`)
* **Farm-Wide Telemetry**: High-level macro view of all registered cattle across both telemetry sources.
* **Source Filter**: Switch views between `All Sources`, `🗄️ Render Database`, or `☁️ AWS Cloud Collars`.
* **Summary KPI Banners**: Total Cattle Monitored, High-Risk Nodes Count, Active Heat Alerts, Herd Rumination Average.
* **Collar Roster Cards**: Individual node cards with live heartbeat timestamps, battery voltage, active behavior, and risk badges.

### 4. Hardware Specifications & Terminal (`HardwareSpecs.jsx`)
* **SPI Flash Ring Buffer Visualizer**: Interactive circular radial gauge tracking memory utilization (Used vs. Free of 32,768 packets).
* **Battery Equation Calculator**: Real-time lifespan math based on cell capacity (5400 mAh) and measured draw (98.16 µA).
* **UART / BLE Replay Log Terminal**: Simulated serial terminal displaying packet acknowledgments, BLE handshakes, and dump progress.

### 5. Node Directory & Administration (`AdminPanel.jsx`)
* **Hardware Tag Registry**: Form to pair and unpair hardware collar IDs with livestock tag numbers.
* **User Management**: Administrative control for operator accounts.
* **Activity Palette Config**: Customizable UI color mappings and behavior categories.

---

## 🚀 Installation & Local Development

### Prerequisites
* **Python**: 3.11, 3.12, or 3.13
* **Node.js**: 18.x or later (npm 9+)
* **Git**

---

### Step 1: Clone the Repository
```bash
git clone https://github.com/Rohit-Singh-tech/cow-monitoring.git
cd cow-monitoring
```

---

### Step 2: Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   # Windows PowerShell:
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Linux / macOS:
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Verify environment configuration:
   * Copy `.env.example` to `.env` (or configure default variables):
     ```ini
     DATABASE_URL=postgresql://user:password@host/dbname
     MODEL_PATH=../cow_ml_models
     AWS_COWNECK_API_URL=https://a03ztkg2f5.execute-api.us-east-1.amazonaws.com/default/CowNeck_API_Function
     ```
5. Launch the FastAPI server:
   ```bash
   python run.py
   ```
   * The backend will start on **`http://localhost:8000`**.
   * Test health check: `http://localhost:8000/health`
   * View Swagger docs: `http://localhost:8000/docs`

---

### Step 3: Frontend Setup
1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   * The dashboard will launch on **`http://localhost:5173`**.
   * Requests to `/api/*` are automatically proxied to `http://localhost:8000`.

---

## ☁️ Deployment Configuration (Render Cloud)

The repository includes a ready-to-use [`render.yaml`](file:///d:/cow%20monitoring/render.yaml) specification for multi-service deployment:

```yaml
services:
  # Backend Web Service (FastAPI)
  - type: web
    name: cow-logger-backend
    env: python
    rootDir: backend
    region: singapore
    plan: free
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python run.py"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.8
      - key: MODEL_PATH
        value: "../cow_ml_models"
      - key: DATABASE_URL
        sync: false

  # Frontend Static Site (React + Vite)
  - type: web
    name: cow-logger-frontend
    env: static
    rootDir: frontend
    region: singapore
    plan: free
    buildCommand: "npm install && npm run build"
    staticPublishPath: "./dist"
    envVars:
      - key: NODE_VERSION
        value: 18.17.0
    routes:
      - type: rewrite
        source: /api/*
        destination: https://cow-monitoring01.onrender.com/api/*
      - type: rewrite
        source: /*
        destination: /index.html
```

---

## 📂 Repository File Structure

```
cow-monitoring/
├── README.md                           # Master Project Documentation & Specifications
├── PROJECT_SUMMARY.md                  # Concise Technical Summary
├── render.yaml                         # Render.com Multi-Service Cloud Deployment Blueprint
├── Gateway_Less_Cow_Health_Monitoring_System.docx (1).pdf # Research & Hardware Foundation
│
├── cow_ml_models/                      # Trained Machine Learning Artifacts
│   ├── activity_model.pkl              # LightGBM 17-Class Behavioral Classifier
│   ├── heat_model.pkl                  # LightGBM Estrus (Heat) Probability Model
│   ├── anomaly_model.pkl               # Isolation Forest Anomaly Detection Model
│   ├── activity_encoder.pkl            # LabelEncoder for Activity Codes
│   ├── baseline_mean.pkl               # 67-Dimensional Feature Means for Normalization
│   ├── baseline_std.pkl                # 67-Dimensional Feature Standard Deviations
│   ├── anomaly_threshold.pkl           # Isolation Forest Outlier Decision Boundary
│   ├── deviation_threshold.pkl         # Z-Score Statistical Threshold
│   └── metadata.json                   # Model Training Metrics, Window Sizes, and Labels
│
├── backend/                            # FastAPI Backend Service
│   ├── run.py                          # Application Entrypoint (Uvicorn Launcher)
│   ├── requirements.txt                # Python Dependencies (FastAPI, LightGBM, SQLAlchemy)
│   ├── Dockerfile                      # Container Build Specification
│   ├── alembic/                        # Database Schema Migrations
│   └── app/
│       ├── main.py                     # App Factory, Lifespan Pre-Warming, CORS & Routers
│       ├── config.py                   # Pydantic Settings & Environment Variables
│       ├── database.py                 # SQLAlchemy Engine & SessionLocal Provider
│       ├── admin.py                    # SQLAdmin View Definitions
│       ├── ml/
│       │   ├── feature_extractor.py    # 67-Feature Extraction Engine
│       │   ├── model_loader.py         # Singleton MLModelManager & Inference Pipeline
│       │   └── worker.py               # Asynchronous Background Ingestion Worker
│       ├── models/
│       │   ├── datalogger.py           # DB Tables (Headers, Points, MLInference, DailySummary)
│       │   ├── tag_registry.py         # Hardware Collar to Animal ID Mappings
│       │   ├── user.py                 # Administrative Authentication Schema
│       │   └── ui_parameter.py         # Dynamic Activity Colors & Categories
│       ├── services/
│       │   ├── aws_service.py          # AWS Lambda Telemetry Ingestion, Caching & Parsing
│       │   └── .aws_telemetry_snapshot.json # Local Fallback Telemetry Snapshot
│       └── api/endpoints/
│           ├── cows.py                 # Herd Overview, Live Telemetry & 7-Day Analytics
│           ├── ingest.py               # IoT Datalogger Ingestion & Direct Prediction
│           ├── hardware.py             # BLE Dump & Memory Reset Triggers
│           ├── admin_api.py            # User CRUD & Tag Registry Management
│           ├── auth.py                 # JWT Authentication Endpoints
│           └── config.py               # Global Activity Metadata Configuration
│
└── frontend/                           # React 19 + Vite 8 Web Application
    ├── package.json                    # Frontend Dependencies & Scripts
    ├── vite.config.js                  # Vite Bundler Configuration
    ├── index.html                      # HTML5 Template with Semantic Structure
    └── src/
        ├── App.jsx                     # Root Component, View Routing & State Providers
        ├── index.css                   # Core Design System, HSL Theme Tokens & Utilities
        ├── components/
        │   ├── LiveCowMonitor.jsx      # System Diagnostics & 10 Hz Streaming Waveforms
        │   ├── Activity7Day.jsx        # 7-Day Trend Analytics & 24-Hour Transition Logs
        │   ├── HerdOverview.jsx        # Farm-Wide Macro Telemetry & Filtering
        │   ├── HardwareSpecs.jsx       # Ring Buffer Gauge, Battery Equations & BLE Terminal
        │   ├── AdminPanel.jsx          # Tag Registry, User Management & Node Directory
        │   ├── ProjectDocs.jsx         # In-App Technical Documentation Viewer
        │   ├── Navbar.jsx              # Global Collar Selector, Heartbeat & Theme Switcher
        │   └── TabBar.jsx              # Navigation Switcher
        └── assets/                     # Graphical Assets & Diagrams
```

---

## 🤝 Research & Institutional Collaboration

* **Agriculture and Water Technology Development Hub (AWaDH)**: Technology Innovation Hub at IIT Ropar funded by the Department of Science and Technology (DST), Government of India.
* **Guru Angad Dev Veterinary and Animal Sciences University (GADVASU)**: Clinical validation, bovine behavioral labeling, and veterinary field trials.
* **National Bank for Agriculture and Rural Development (NABARD)**: Rural agricultural innovation and development support.

---

## 📜 License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
