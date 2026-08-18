# Cow Health Monitoring System - Detailed Project Summary

This document serves as a comprehensive technical summary of the entire Cow Health Monitoring system. It outlines the application architecture, all API endpoints, frontend screens, displayed parameters, and the machine learning models utilized to generate insights from raw telemetry data.

---

## 1. Machine Learning Engine (Backend)

The backend utilizes pre-trained machine learning models to decode raw 10Hz XYZ accelerometer and magnetometer data into behavioral and physiological insights. The `MLModelManager` orchestrates these models as a singleton process.

### Models & Extractors
*   **Feature Extractor (`extract_67_features`)**: 
    *   Takes raw XYZ arrays and computes 67 distinct statistical and frequency-domain features (mean, variance, skewness, kurtosis, FFT peaks, spectral entropy, correlations across axes, etc.).
*   **Activity Classification Model (`activity_model.pkl`)**: 
    *   **Architecture**: LightGBM Multi-class Classifier.
    *   **Purpose**: Classifies a given 8-second window of features into 17 distinct behavioral classes (e.g., `RUS` - Ruminating, `REL` - Lying Rest, `MOV` - Walking, `FEP` - Feeding).
*   **Estrus/Heat Detection Model (`heat_model.pkl`)**:
    *   **Architecture**: LightGBM Binary Classifier.
    *   **Purpose**: specifically trained on highly restless activity signatures and mounting behaviors to flag periods of high Estrus probability (in-heat).
*   **Anomaly Detection Model (`anomaly_model.pkl`)**:
    *   **Architecture**: Isolation Forest (Unsupervised).
    *   **Purpose**: Detects unusual physical movements (e.g., limping, falling, thrashing) that fall outside the learned boundaries of normal cow behavior, outputting an Anomaly Score.

---

## 2. API Endpoints

The backend is built with FastAPI and organized into several routers based on system functionality.

### Ingestion API (Hardware Layer)
*   **`POST /api/ingest/raw`**: Bulk ingestion endpoint for the Dataloggers. Accepts arrays of raw XYZ packets, saves them to SQLite/PostgreSQL, and triggers background ML inference via Celery/BackgroundTasks.
*   **`POST /api/ingest/packet`**: Ingests a single packet of telemetry data.
*   **`POST /api/ingest/predict`**: Pure inference endpoint. Takes raw data, extracts features, runs all ML models, and returns classifications without persisting data to the DB.

### Frontend Compatibility API (Web Dashboard)
*   **`GET /api/cows`**: Returns a list of all monitored cows/nodes along with high-level daily aggregates (used in Herd Overview).
*   **`GET /api/cow/{cow_id}/current`**: Returns real-time telemetry buffers (Raw X, Y, Z arrays) for live charting, alongside the very latest ML inferences, Health Risk logic, and current active behavior.
*   **`GET /api/cow/{cow_id}/7day`**: Returns the aggregated historical data over a continuous 7-day window. Missing days are zero-padded. Returns arrays for Rumination Hours, Feeding Hours, Lying Hours, Health Scores, and Estrus Indices.
*   **`GET /api/cow/{cow_id}/activity-log`**: Returns grouped chronological transition logs for the last 24 hours. The backend fetches raw packet inferences, groups contiguous activities (e.g. 20 packets of `RUS`), calculates precise time durations (8 seconds per packet), and backward-chains start and end times for gapless UI display.
*   **`POST /api/ble/trigger-dump`**: Triggers a simulated SPI Flash BLE memory dump (e.g., 2,500 packets) for demonstration/hardware testing.

### Admin & Config API
*   **`POST /api/auth/login`**: Authenticates an administrator and returns a JWT token.
*   **`GET /api/admin/users`**, **`POST /api/admin/users`**, **`DELETE /api/admin/users/{user_id}`**: CRUD operations for managing admin users.
*   **`POST /api/admin/tags`**, **`DELETE /api/admin/tags/{tag_id}`**: Maps physical IoT device hardware IDs (e.g. Node-17) to specific Cow IDs (e.g. Tag-17).
*   **`GET /api/config/activities`**: Returns the global mapping dictionary of Activity Codes (e.g. `RUS`) to human-readable names and UI hex colors.

---

## 3. Frontend Screens & Displayed Parameters

The React-based frontend visualizes the ML inferences and database aggregations using a dynamic, real-time UI.

### Global Elements
*   **Sidebar Navigation**: Links to Sys Diagnostics, 7-Day Logs, Node Directory, Hardware Specs, and Archives.
*   **Navbar**: Global target node selector dropdown, global connection status indicator, theme toggler (Dark/Light), and alert notification bell.

### Screen 1: System Diagnostics (`LiveCowMonitor.jsx`)
This is the primary real-time dashboard for a selected device.
*   **Header Card**: Displays current node/tag ID, Health Risk Badge (e.g. HIGH RISK, HEALTHY), current Activity state (e.g. "Ruminating"), and the ML Confidence percentage for that state.
*   **Critical Alert Banner**: Only displays if a critical risk (like Estrus or Illness) is detected.
*   **Telemetry KPI Tiles**:
    *   **Current Activity**: (e.g., RUS, MOV, REL).
    *   **Rumination Total**: Sum of rumination for the current day (target 8-10 hours).
    *   **Lying Rest Hours**: Total rest duration for the day.
    *   **Estrus Probability**: The real-time ML probability that the cow is in heat.
    *   **Packets Buffered**: Number of raw data packets ingested in the current polling window.
    *   **Isolation Forest Score**: The numerical anomaly score representing physical deviation.
*   **Live Charts**:
    *   **Raw XYZ Motion Telemetry**: A high-frequency (10 Hz) live streaming line chart plotting X, Y, and Z accelerometer values in real-time.
    *   **Actual Behavior Matrix (Today)**: A colored matrix/heatmap representing the frequency of different activities throughout the day.

### Screen 2: 7-Day Logs (`Activity7Day.jsx`)
Visualizes historical trends and transition timelines.
*   **Line/Bar Charts**:
    *   **7-Day Activity Time Allocation**: A stacked/grouped chart showing daily hours dedicated to Rumination, Lying, Feeding, and Movement over the continuous past 7 days.
    *   **Health Score & Estrus Index Trends**: A line chart tracking the overall 0-100 Health Score and 0-100 Estrus Index across the week.
*   **7-Day Average Distribution**: A summarized list calculating the exact average daily hours per activity class (REL, RUS, FEP, MOV) over the week.
*   **Recorded Activity Transition Logs**: A paginated table showing the exact gapless chronological transitions for the last 24 hours.
    *   **Parameters**: Log ID, Target Node, True Start Time, True End Time, Accurate Duration (in mins/hours), Activity Class (e.g. `RUS - Ruminating`), Category, Average Confidence (%), and SPI Packet ID boundaries.

### Screen 3: Herd Overview (`HerdOverview.jsx`)
A macro-level view of the entire farm.
*   **KPI Banners**: Total Monitored Cows, High Risk Nodes, Heat Alerts Active, and Herd Average Rumination.
*   **Herd Roster Table**: 
    *   **Parameters**: Node/Tag ID, Live Status (Active/Inactive), Heartbeat timestamp, Current ML Inference, Health Status (Healthy, Warning, High Risk), and Battery Voltage.

### Screen 4: Hardware Specs & Admin
*   **`HardwareSpecs.jsx`**: Displays technical architecture diagrams, PCB board layouts, and hardware engineering specifications of the physical dataloggers.
*   **`AdminPanel.jsx` / `NodeDirectory.jsx`**: Administrative tables for registering new users, removing users, pairing hardware devices to cows, and clearing out dead/unassigned nodes.
