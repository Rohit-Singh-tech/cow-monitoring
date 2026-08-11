# Cow Monitoring System - API Documentation

The backend service is built using FastAPI, which automatically generates interactive API documentation. You can access the live interactive Swagger UI and ReDoc directly on your hosted backend server:

- **Swagger UI**: `https://<your-backend-url>.onrender.com/docs`
- **ReDoc**: `https://<your-backend-url>.onrender.com/redoc`

Below is an overview of the key API endpoints available in the system.

---

## 1. Authentication & Admin
Used for the administrator dashboard and user management.

### `POST /api/auth/login`
Authenticates a user and returns a session token.

### `GET /api/admin/users`
Fetches a list of all registered administrative users.

### `POST /api/admin/users`
Registers a new administrator user.
**Payload:**
```json
{
  "username": "admin1",
  "email": "admin1@example.com",
  "password": "securepassword"
}
```

### `DELETE /api/admin/users/{user_id}`
Deletes a specific user by their database ID.

### `POST /api/admin/tags`
Registers a new BLE hardware tag and links it to a cow.
**Payload:**
```json
{
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "animal_id": "102",
  "description": "Optional notes"
}
```

### `DELETE /api/admin/tags/{tag_id}`
Removes a cow hardware tag from the registry.

---

## 2. Frontend Compatibility / Legacy Routes
These routes are directly consumed by the React frontend to populate the dashboard UI.

### `GET /api/cows`
Retrieves a herd overview with health metrics, estrus alerts, and rumination hours for all monitored cattle.

### `GET /api/cow/{cow_id}/current`
Fetches the live telemetry, raw XYZ accelerometer buffers, and ML health predictions for a specific cow.

### `GET /api/cow/{cow_id}/7day`
Retrieves a 7-day historical trend of behavior (rumination, feeding, resting, active hours) for the specified cow.

### `GET /api/cow/{cow_id}/activity-log`
Returns an activity log representing distinct behavioral states over a recent timeline.

### `POST /api/ble/trigger-dump`
Transmits a Knock-Knock signature to the BLE node instructing it to dump its SPI flash buffer.
**Payload:**
```json
{
  "cowId": "123"
}
```

### `POST /api/ble/trigger-reset`
Transmits a reset signature to the BLE node to erase the SPI flash memory.
**Payload:**
```json
{
  "cowId": "123"
}
```

---

## 3. Data Ingestion (IoT)
Endpoints used by the gateway or mobile app to push raw hardware telemetry into the database.

### `POST /api/v1/ingest` (or configured `API_V1_STR`)
Ingests raw BLE packet data from the LIS3DH sensors on the cow collars.

### `GET /health`
System health check endpoint used by Render to ensure the server and ML engine are loaded successfully.
